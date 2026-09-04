"""ONE diagnostic path solve: balanced 2016, core 17 -> core 24.

Never overwrites production data or edits/saves the project. Uses a new dated
diagnostic GDB. Missing candidate VCF keeps OLD resistance for this test only.
No water/fence policy change, no batch, no Circuitscape. main(False) is read-only.
"""
import datetime as task_datetime
import hashlib
import json
import math
from pathlib import Path
import sys

HERE = str(Path(__file__).resolve().parent)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import arcpy
import numpy as np
from audit_downloaded_gee_validity import read_model, check_lattice, grid
from compare_vcf_v2_candidate_inputs import vegetation, ROOT, GDB, NAMES
from screen_existing_routes_vcf_v2 import screen, self_test

OLD = GDB / 'resistance_temporal_veg_balanced_2016'
OLD_V = GDB / 'vegetation_resistance_2016_1_10'
PATHS = GDB / 'least_cost_paths_temporal_veg_balanced_2016'
CORES = GDB / 'cheetah_core_primary_density051_min500'
MASK = Path(r'C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah_connectivity.gdb\extent_buffered')
VCF = ROOT / 'vcf_maskpreserved_common_v2_2016.tif'


def main(run_solver=True):
    self_test()
    arcpy.CheckOutExtension('Spatial')
    for path in (OLD, OLD_V, PATHS, CORES, MASK, VCF):
        if not arcpy.Exists(str(path)):
            raise FileNotFoundError(str(path))
    ref = arcpy.Raster(str(OLD))
    old = read_model(OLD, ref)
    old_v = read_model(OLD_V, ref)
    vcf = arcpy.Raster(str(VCF))
    check_lattice(vcf, ref)
    if (vcf.width, vcf.height) != (ref.width, ref.height) or list(vcf.bandNames) != NAMES:
        raise ValueError('Candidate VCF shape/bands changed')
    a = arcpy.RasterToNumPyArray(vcf, nodata_to_value=-9999).astype(float)
    a[a == -9999] = np.nan
    new_v, coverage = vegetation(*a[:3]), a[3]
    support = np.isfinite(old)
    if not np.isfinite(old_v[support]).all():
        raise ValueError('Old vegetation missing on old model support')
    replace = support & np.isfinite(new_v)
    candidate = old.copy()
    candidate[replace] += .2 * (new_v[replace] - old_v[replace])
    if not np.array_equal(np.isfinite(candidate), support) or np.any(candidate[support] <= 0):
        raise ValueError('Candidate changed the domain or contains nonpositive cost')
    for dataset in (PATHS, CORES, MASK):
        if arcpy.Describe(str(dataset)).spatialReference.factoryCode != ref.spatialReference.factoryCode:
            raise ValueError('CRS mismatch: ' + str(dataset))
    with arcpy.da.SearchCursor(str(PATHS), ['SHAPE@','COST_RAW','STATUS'], 'FROM_ID = 17 AND TO_ID = 24') as cursor:
        saved = list(cursor)
    if len(saved) != 1 or saved[0][2] != 'OK':
        raise ValueError('Expected exactly one successful saved 17 -> 24 route')
    old_geom, old_cost, _ = saved[0]
    if old_geom is None or old_geom.length <= 0 or not old_cost or old_cost <= 0:
        raise ValueError('Saved path geometry/cost invalid')
    with arcpy.da.SearchCursor(str(CORES), ['CORE_ID'], 'CORE_ID IN (17,24)') as cursor:
        core_ids = [int(row[0]) for row in cursor]
    if sorted(core_ids) != [17,24]:
        raise ValueError('Expected exactly one polygon per focal core')
    old_screen = screen(old_geom, old, candidate, coverage, ref)
    if not old_screen['complete_candidate_coverage']:
        raise ValueError('Saved route is not a fully costed feasible candidate route')
    if abs(old_screen['old_integral_comparable']/old_cost - 1) > 1e-4:
        raise ValueError('Stored old cost does not match diagnostic integration')
    # Every positive-cost prefix of an optimal route costs <= the full route.
    # The saved route is feasible under this unchanged domain. Its candidate
    # cost, plus 5% numerical safety margin, is therefore a search cost bound.
    # This is NOT a spatial corridor crop and is NOT a distance-in-meters limit.
    bound = float(old_screen['new_integral_comparable'] * 1.05)
    plan = {'year':2016, 'weighting':'balanced', 'from_core':17, 'to_core':24,
            'cost_distance_runs':1, 'model_cells':int(support.sum()),
            'fallback_cells_old_resistance_retained':int(np.count_nonzero(support & ~replace)),
            'maximum_accumulated_cost':bound, 'grid':grid(ref),
            'saved_old_route_cost':float(old_cost),
            'saved_route_under_candidate_cost':old_screen['new_integral_comparable'],
            'candidate_vcf_sha256':hashlib.sha256(VCF.read_bytes()).hexdigest(),
            'old_route_geometry_sha256':hashlib.sha256(bytes(old_geom.WKB)).hexdigest(),
            'diagnostic_only':'Missing candidate means retain old resistance. No final water/missing-land policy is inferred.'}
    print(json.dumps(plan,indent=2),flush=True)
    if not run_solver:
        print('PREFLIGHT PASSED. No files written and no solver run.',flush=True)
        return plan

    stamp = task_datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    folder = Path(r'C:\cheetah\diagnostics') / ('vcf_v2_pair17_24_2016_' + stamp)
    folder.mkdir(parents=True, exist_ok=False)
    gdb = folder / 'test.gdb'
    arcpy.management.CreateFileGDB(str(folder), gdb.name)
    def output(name):
        return str(gdb / name)
    with (folder / 'test_manifest.json').open('x',encoding='utf-8') as f:
        json.dump(plan,f,indent=2)
    print('Diagnostic outputs:',folder,flush=True)
    with arcpy.EnvManager(overwriteOutput=False, addOutputsToMap=False,
                          extent=ref.extent, snapRaster=str(OLD), cellSize=str(OLD),
                          outputCoordinateSystem=ref.spatialReference, mask=str(MASK),
                          workspace=str(gdb), scratchWorkspace=str(gdb),
                          parallelProcessingFactor='75%'):
        candidate_path = output('resistance_diagnostic_oldfallback')
        stored = np.where(support,candidate,-9999).astype('float32')
        raster = arcpy.NumPyArrayToRaster(stored, arcpy.Point(ref.extent.XMin,ref.extent.YMin),
                                         ref.meanCellWidth,ref.meanCellHeight,-9999)
        raster.save(candidate_path)
        arcpy.management.DefineProjection(candidate_path,ref.spatialReference)
        verified = read_model(candidate_path,ref)
        if not np.array_equal(np.isfinite(verified),support) or not np.allclose(verified[support],candidate[support],rtol=0,atol=2e-6):
            raise ValueError('Written candidate grid/domain/values failed verification')
        candidate = verified
        # Copy only the two selected core features to the diagnostic GDB;
        # source data and existing selections are not changed.
        token = 'vcf_pilot_' + stamp
        src = arcpy.management.MakeFeatureLayer(str(CORES),token+'_src','CORE_ID = 17').getOutput(0)
        dst = arcpy.management.MakeFeatureLayer(str(CORES),token+'_dst','CORE_ID = 24').getOutput(0)
        arcpy.management.CopyFeatures(src,output('source_core17'))
        arcpy.management.CopyFeatures(dst,output('destination_core24'))
        arcpy.management.CopyFeatures([old_geom],output('saved_old_route'))
        cd, backlink = output('cost_distance'),output('backlink')
        print('1/1 Cost-distance calculation: core 17, balanced 2016. Wait for completion.',flush=True)
        arcpy.sa.CostDistance(output('source_core17'),candidate_path,
                             maximum_distance=bound,out_backlink_raster=backlink).save(cd)
        print('Extracting the one route to core 24...',flush=True)
        new_path = output('candidate_route17_24')
        arcpy.sa.CostPathAsPolyline(output('destination_core24'),cd,backlink,new_path,'BEST_SINGLE','CORE_ID')
        fields = [f.name for f in arcpy.ListFields(new_path)]
        cost_field = next((f for f in fields if f.upper() in ('PATHCOST','PATH_COST')),None)
        if cost_field is None:
            raise ValueError('Cannot identify output path cost field')
        with arcpy.da.SearchCursor(new_path,['SHAPE@',cost_field]) as cursor:
            generated = list(cursor)
        if len(generated)!=1:
            raise ValueError('Expected exactly one candidate path')
        new_geom,new_cost = generated[0]
        if new_geom is None or new_cost is None or not math.isfinite(new_cost) or new_cost<=0:
            raise ValueError('Candidate path/cost invalid')
        feasible = screen(old_geom,old,candidate,coverage,ref)
        new_screen = screen(new_geom,old,candidate,coverage,ref)
        if not new_screen['complete_candidate_coverage']:
            raise ValueError('New path traverses unsupported model cells')
        if new_cost > feasible['new_integral_comparable']*1.0001:
            raise ValueError('New optimized route is more costly than saved feasible route; inspect test')
        if abs(new_screen['new_integral_comparable']/new_cost-1)>1e-4:
            raise ValueError('New path integration and solver cost disagree')
        unresolved = old + .2*(new_v-old_v)
        fallback_screen = screen(new_geom,old,unresolved,coverage,ref)
        result = dict(plan, candidate_path=str(new_path),
            old_length_km=old_geom.length/1000,new_length_km=new_geom.length/1000,
            optimized_new_cost=float(new_cost), optimized_cost_change_percent=(new_cost/old_cost-1)*100,
            improvement_over_old_route_on_candidate_percent=(1-new_cost/feasible['new_integral_comparable'])*100,
            new_route_fallback_length_m=fallback_screen['new_missing_m'],
            new_route_below95pct_coverage_length_m=fallback_screen['partial_below95_m'],
            new_route_under_old_cost=new_screen['old_integral_comparable'])
        for distance in (1000,5000):
            result[f'percent_new_route_within_{distance}m_of_old'] = 100*new_geom.intersect(old_geom.buffer(distance),2).length/new_geom.length
            result[f'percent_old_route_within_{distance}m_of_new'] = 100*old_geom.intersect(new_geom.buffer(distance),2).length/old_geom.length
        result['interpretation_limits'] = ['One pair/year/weight cannot establish network-wide robustness.',
            'Overlap distances are descriptive, not biological cutoffs.',
            'Old-value fallback preserves support for a controlled diagnostic; not final missing-data treatment.',
            'No production scenario, path, map or priority ranking was replaced.']
        with (folder/'comparison.json').open('x',encoding='utf-8') as f:
            json.dump(result,f,indent=2)
        print(json.dumps(result,indent=2),flush=True)
        print('DONE. Comparison:',folder/'comparison.json',flush=True)
        print('One diagnostic path only. Production data and map unchanged.',flush=True)


if __name__=='__main__':
    main()
