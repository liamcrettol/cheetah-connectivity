"""Resumable CONTROLLED diagnostic: 45 pairs x 4 years, balanced VCF only.

Preserves production data. Missing candidate vegetation retains old resistance
only to hold support fixed; not final imputation or water policy. No circuits.
One bounded CostDistance per source; checkpoints retain CD/backlinks and paths.
Use --preflight to inspect all inputs without writing files or running solvers.
"""
import csv
import ctypes
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import time
import traceback
import uuid

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import arcpy
import numpy as np
from audit_downloaded_gee_validity import read_model, check_lattice, grid
from compare_vcf_v2_candidate_inputs import vegetation, ROOT, GDB, NAMES
from screen_existing_routes_vcf_v2 import screen, self_test

OUT = Path(r'C:\cheetah\diagnostics\vcf_v2_balanced_overnight_v1')
CORES = GDB / 'cheetah_core_primary_density051_min500'
YEARS = (2012, 2016, 2020, 2024)
PAIR_CSV = Path(r'C:\cheetah\reports\least_cost_paths_temporal_veg_balanced_2012.csv')
POLICY = 'DIAGNOSTIC ONLY: old resistance retained where candidate VCF is missing; no final water policy.'

def now():
    return dt.datetime.now().isoformat(timespec='seconds')

def log(message):
    print(f'[{now()}] {message}', flush=True)

def digest(value):
    return hashlib.sha256(value).hexdigest()

def array_hash(a):
    return digest(np.where(np.isfinite(a), a, -9999).astype('<f8').tobytes())

def atomic_json(path, obj):
    path = Path(path)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with temp.open('x', encoding='utf-8') as f:
        json.dump(obj, f, indent=2, allow_nan=False)
    os.replace(temp, path)

def endpoints(geom, pair, cores, sr):
    pts = [arcpy.PointGeometry(geom.firstPoint, sr), arcpy.PointGeometry(geom.lastPoint, sr)]
    scores = [pts[0].distanceTo(cores[pair[0]]) + pts[1].distanceTo(cores[pair[1]]),
              pts[1].distanceTo(cores[pair[0]]) + pts[0].distanceTo(cores[pair[1]])]
    if scores[1] < scores[0]:
        pts.reverse()
    if any(p.distanceTo(cores[c]) > .001 for p, c in zip(pts, pair)):
        raise ValueError(f'Endpoint outside assigned core: {pair}')
    return [(p.firstPoint.X, p.firstPoint.Y) for p in pts]

def load_year(year, cores, pairs):
    oldpath = GDB / f'resistance_temporal_veg_balanced_{year}'
    ref = arcpy.Raster(str(oldpath))
    old = read_model(oldpath, ref)
    oldv = read_model(GDB / f'vegetation_resistance_{year}_1_10', ref)
    vcf = ROOT / f'vcf_maskpreserved_common_v2_{year}.tif'
    r = arcpy.Raster(str(vcf))
    check_lattice(r, ref)
    if (r.width, r.height) != (ref.width, ref.height) or list(r.bandNames) != NAMES:
        raise ValueError('Candidate grid/bands mismatch')
    if tuple(r.getRasterInfo().getNoDataValues()) != (-9999.0,) * 8:
        raise ValueError('Unexpected candidate NoData definition')
    a = arcpy.RasterToNumPyArray(r, nodata_to_value=-9999).astype(float)
    a[a == -9999] = np.nan
    support = np.isfinite(old)
    if not np.isfinite(oldv[support]).all() or np.any(old[support] <= 0):
        raise ValueError('Invalid saved resistance/vegetation')
    if not np.isfinite(a[3:]).all() or np.any(a[3:] < -1e-6) or np.any(a[3:] > 1.000001):
        raise ValueError('Invalid candidate coverage')
    for band in a[:3]:
        if not np.array_equal(np.isfinite(band), a[3] > 0):
            raise ValueError('Cover mask differs from common support')
        if np.any(band[np.isfinite(band)] < 0) or np.any(band[np.isfinite(band)] > 100.0001):
            raise ValueError('Cover values outside percentage range')
    if not np.allclose(np.sum(a[:3], axis=0)[a[3] > 0], 100, atol=.001, rtol=0):
        raise ValueError('Cover components do not sum to 100')
    if np.any(a[3] > a[4] + 1e-6) or np.any(a[4] > a[5] + 1e-6):
        raise ValueError('Coverage nesting failed')
    if not np.allclose(a[4], a[5]-a[6]-a[7], atol=1e-6, rtol=0):
        raise ValueError('Annual coverage accounting failed')
    coverage = a[3].copy()
    newv = vegetation(*a[:3])
    unresolved = old + .2 * (newv-oldv)
    candidate = np.where(support & np.isfinite(newv), unresolved, old).astype('float32').astype(float)
    if not np.array_equal(np.isfinite(candidate), support) or np.any(candidate[support] <= 0):
        raise ValueError('Candidate changed support or nonpositive costs')
    fc = GDB / f'least_cost_paths_temporal_veg_balanced_{year}'
    if arcpy.Describe(str(fc)).spatialReference.factoryCode != ref.spatialReference.factoryCode:
        raise ValueError('Route CRS mismatch')
    routes = {}
    fields = ['FROM_ID', 'TO_ID', 'SHAPE@', 'PATH_KM', 'COST_RAW', 'STATUS']
    with arcpy.da.SearchCursor(str(fc), fields) as cursor:
        for f, t, geom, length, cost, status in cursor:
            pair = tuple(sorted((int(f), int(t))))
            if pair in routes or status != 'OK' or geom is None or geom.length <= 0:
                raise ValueError('Duplicate or invalid saved route')
            if cost is None or not math.isfinite(cost) or cost <= 0 or abs(geom.length/1000-length) > 1e-5:
                raise ValueError('Saved route cost/length invalid')
            endpoints(geom, pair, cores, ref.spatialReference)
            check = screen(geom, old, candidate, coverage, ref)
            if not check['complete_candidate_coverage'] or abs(check['old_integral_comparable']/cost-1) > 1e-4:
                raise ValueError(f'Saved feasible route QC failed: {year} {pair}')
            routes[pair] = {'geom': geom, 'cost': float(cost), 'feasible': check['new_integral_comparable']}
    if set(routes) != pairs:
        raise ValueError('Saved pair sets differ across years')
    fingerprint = {'grid': grid(ref), 'old': array_hash(old), 'old_v': array_hash(oldv),
                   'candidate': array_hash(candidate), 'coverage': array_hash(coverage),
                   'vcf_file': digest(vcf.read_bytes()), 'support': digest(support.tobytes()),
                   'routes': {f'{p[0]}-{p[1]}': {'geometry': digest(bytes(v['geom'].WKB)), 'cost': v['cost']} for p,v in sorted(routes.items())},
                   'fallback_cells': int(np.count_nonzero(support & ~np.isfinite(newv)))}
    return ref, old, candidate, unresolved, coverage, routes, fingerprint

def preflight():
    self_test()
    arcpy.CheckOutExtension('Spatial')
    with PAIR_CSV.open(newline='', encoding='utf-8-sig') as f:
        listed = [tuple(sorted((int(r['from_core']), int(r['to_core'])))) for r in csv.DictReader(f)]
    pairs = set(listed)
    if len(pairs) != 45 or len(listed) != 45:
        raise ValueError('Expected exactly 45 unique canonical pairs')
    cores = {}
    with arcpy.da.SearchCursor(str(CORES), ['CORE_ID', 'SHAPE@']) as cursor:
        for cid, geom in cursor:
            if cid in cores or geom is None:
                raise ValueError('Duplicate or missing core geometry')
            cores[int(cid)] = geom
    if len(cores) != 23 or not set(sum((list(p) for p in pairs), [])).issubset(cores):
        raise ValueError('Core inventory mismatch')
    versions = arcpy.GetInstallInfo()
    plan = {'policy': POLICY, 'years': list(YEARS), 'pairs': [list(p) for p in sorted(pairs)],
            'core_hashes': {str(c): digest(bytes(g.WKB)) for c,g in sorted(cores.items())},
            'arcgis_version': versions.get('Version'), 'inputs': {},
            'scripts': {p.name: digest(p.read_bytes()) for p in [Path(__file__), HERE/'audit_downloaded_gee_validity.py', HERE/'compare_vcf_v2_candidate_inputs.py', HERE/'screen_existing_routes_vcf_v2.py']}}
    for year in YEARS:
        log(f'Preflight {year}: checking arrays, all 45 saved routes, endpoints and feasible cost bounds')
        values = load_year(year, cores, pairs)
        ref, *_, fp = values
        if ref.spatialReference.factoryCode != arcpy.Describe(str(CORES)).spatialReference.factoryCode:
            raise ValueError('Core CRS mismatch')
        if year != YEARS[0]:
            first = plan['inputs'][str(YEARS[0])]
            if fp['grid'] != first['grid'] or fp['support'] != first['support'] or fp['coverage'] != first['coverage']:
                raise ValueError('Grid/model support/common coverage differs across years')
        plan['inputs'][str(year)] = fp
        del values
    plan['cost_distance_runs_maximum'] = len({p[0] for p in pairs}) * len(YEARS)
    plan['comparisons_expected'] = len(pairs) * len(YEARS)
    log(f'PREFLIGHT PASSED: {plan["comparisons_expected"]} comparisons; at most {plan["cost_distance_runs_maximum"]} source solves')
    return plan, cores, pairs

def generated(path):
    names = [f.name for f in arcpy.ListFields(str(path))]
    field = next((n for n in names if n.upper() in ('PATHCOST', 'PATH_COST')), None)
    if field is None:
        raise ValueError('No solver path cost field: ' + str(path))
    with arcpy.da.SearchCursor(str(path), ['SHAPE@', field]) as cursor:
        rows = list(cursor)
    if len(rows) != 1 or rows[0][0] is None or rows[0][0].length <= 0:
        raise ValueError('Expected one positive-length solver path')
    geom, cost = rows[0]
    if cost is None or not math.isfinite(cost) or cost <= 0:
        raise ValueError('Invalid solver cost')
    return geom, float(cost)

def compare(year, pair, path, data, cores):
    ref, old, candidate, unresolved, coverage, routes, _ = data
    geom, cost = generated(path)
    saved = routes[pair]
    checked = screen(geom, old, candidate, coverage, ref)
    if not checked['complete_candidate_coverage'] or abs(checked['new_integral_comparable']/cost-1) > 1e-4:
        raise ValueError('Candidate integration does not match solver cost')
    if cost > saved['feasible'] * 1.0001:
        raise ValueError('Optimized path more costly than feasible saved route')
    exposure = screen(geom, old, unresolved, coverage, ref)
    e0 = endpoints(saved['geom'], pair, cores, ref.spatialReference)
    e1 = endpoints(geom, pair, cores, ref.spatialReference)
    result = {'year': year, 'from_core': pair[0], 'to_core': pair[1], 'candidate_path': str(path),
              'geometry_sha256': digest(bytes(geom.WKB)), 'old_cost': saved['cost'], 'new_cost': cost,
              'old_route_candidate_cost': saved['feasible'],
              'optimized_cost_change_pct': 100*(cost/saved['cost']-1),
              'old_length_km': saved['geom'].length/1000, 'new_length_km': geom.length/1000,
              'fallback_length_m': exposure['new_missing_m'],
              'below95pct_coverage_valid_length_m': exposure['partial_below95_m'],
              'source_endpoint_shift_km': math.dist(e0[0],e1[0])/1000,
              'destination_endpoint_shift_km': math.dist(e0[1],e1[1])/1000}
    for distance in (1000,5000):
        result[f'new_within_{distance}m_of_old_pct'] = 100*geom.intersect(saved['geom'].buffer(distance),2).length/geom.length
        result[f'old_within_{distance}m_of_new_pct'] = 100*saved['geom'].intersect(geom.buffer(distance),2).length/saved['geom'].length
    return result

def summarize(rows, expected):
    if not rows:
        return
    rows = sorted(rows, key=lambda r:(r['year'],r['from_core'],r['to_core']))
    temp = OUT / 'comparisons.csv.tmp'
    with temp.open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    os.replace(temp, OUT/'comparisons.csv')
    temporal = []
    for pair in sorted({(r['from_core'],r['to_core']) for r in rows}):
        byyear = {r['year']:r for r in rows if (r['from_core'],r['to_core']) == pair}
        if 2012 in byyear and 2024 in byyear:
            a,b = byyear[2012],byyear[2024]
            original = 100*(b['old_cost']/a['old_cost']-1)
            candidate = 100*(b['new_cost']/a['new_cost']-1)
            temporal.append({'from_core':pair[0], 'to_core':pair[1], 'old_2012_2024_change_pct':original,
                             'candidate_2012_2024_change_pct':candidate,
                             'difference_percentage_points':candidate-original,
                             'sign_differs_no_tolerance': bool(np.sign(original) != np.sign(candidate)),
                             'endpoint_year_paths_use_fallback': a['fallback_length_m']>.001 or b['fallback_length_m']>.001})
    atomic_json(OUT/'temporal_comparison.json', {'pairs':temporal,'caveat':'Sign differences are arithmetic, not significance tests. Domain remains diagnostic.'})
    text = ['# Corrected VCF balanced-model diagnostic', '', f'Completed comparisons: {len(rows)}/{expected}', '', POLICY, '',
            'No production model, project, priority ranking or Circuitscape output was replaced.', '',
            f'Candidate routes touching old-value fallback: {sum(r["fallback_length_m"]>.001 for r in rows)}',
            f'Median absolute optimized cost change: {np.median([abs(r["optimized_cost_change_pct"]) for r in rows]):.3f}%',
            f'Median new-route length within 1 km of old: {np.median([r["new_within_1000m_of_old_pct"] for r in rows]):.2f}%', '',
            'Overlap distances and 95% coverage are descriptive, not biological cutoffs. No path exposure does not prove missing cells cannot influence routing.',
            'Endpoint choices can change within fixed cores. This tests only balanced weights, not low/high weights or current flow.',
            'Temporal results are controlled diagnostic comparisons, not final paper results.']
    tmp = OUT/'SUMMARY.md.tmp'; tmp.write_text('\n'.join(text)+'\n',encoding='utf-8'); os.replace(tmp,OUT/'SUMMARY.md')

def run():
    OUT.mkdir(parents=True, exist_ok=True)
    lock = OUT/'RUNNING.lock'
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise RuntimeError(f'Another run or stale lock exists: {lock}. Do not start a second worker. Check the PID recorded in that file.')
    with os.fdopen(fd,'w') as f:
        f.write(str(os.getpid()))
    rows = []
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
        atomic_json(OUT/'STATUS.json', {'state':'preflight','pid':os.getpid(),'time':now()})
        plan, cores, pairs = preflight()
        manifest = OUT/'manifest.json'
        if manifest.exists():
            if json.loads(manifest.read_text()) != plan:
                raise ValueError('Inputs, scripts or ArcGIS version changed. Refusing to reuse stale checkpoints. Preserve this folder and choose a NEW output folder.')
        else:
            atomic_json(manifest,plan)
        if shutil.disk_usage(OUT).free < 20*1024**3:
            raise RuntimeError('Less than 20 GB free on output drive. No solver started.')
        for year in YEARS:
            data = load_year(year,cores,pairs)
            ref, old, candidate, unresolved, coverage, routes, fingerprint = data
            if fingerprint != plan['inputs'][str(year)]:
                raise ValueError('Input changed since preflight')
            yearfolder = OUT/str(year); yearfolder.mkdir(exist_ok=True)
            # Float32 is intentional: matches the checked one-pair pilot.
            candidate_ready = yearfolder/'candidate_ready.json'
            with arcpy.EnvManager(overwriteOutput=False, addOutputsToMap=False, mask=None,
                                  snapRaster=str(GDB/f'resistance_temporal_veg_balanced_{year}'),
                                  extent=ref.extent, cellSize=ref.meanCellWidth,
                                  outputCoordinateSystem=ref.spatialReference, parallelProcessingFactor='75%'):
                if candidate_ready.exists():
                    cp = Path(json.loads(candidate_ready.read_text())['path'])
                else:
                    cgdb = yearfolder/('candidate_'+uuid.uuid4().hex[:10]+'.gdb')
                    arcpy.management.CreateFileGDB(str(yearfolder),cgdb.name)
                    cp = cgdb/'resistance_oldfallback'
                    arcpy.NumPyArrayToRaster(np.where(np.isfinite(candidate),candidate,-9999).astype('float32'),
                        arcpy.Point(ref.extent.XMin,ref.extent.YMin),ref.meanCellWidth,ref.meanCellHeight,-9999).save(str(cp))
                    arcpy.management.DefineProjection(str(cp),ref.spatialReference)
                if array_hash(read_model(cp,ref)) != fingerprint['candidate']:
                    raise ValueError('Stored diagnostic candidate failed value/grid check')
                atomic_json(candidate_ready,{'path':str(cp)})
                for src in sorted({p[0] for p in pairs}):
                    sourcefolder = yearfolder/f'source_{src}'; sourcefolder.mkdir(exist_ok=True)
                    expected = sorted(p for p in pairs if p[0] == src)
                    done = sourcefolder/'complete.json'
                    if done.exists():
                        checkpoint = json.loads(done.read_text())
                        if {(r['from_core'],r['to_core']) for r in checkpoint} != set(expected) or len(checkpoint)!=len(expected):
                            raise ValueError('Completed checkpoint pair set invalid')
                        for item in checkpoint:
                            geom,cost = generated(item['candidate_path'])
                            if digest(bytes(geom.WKB)) != item['geometry_sha256'] or cost != item['new_cost']:
                                raise ValueError('Completed path changed since checkpoint')
                        rows.extend(checkpoint); summarize(rows,plan['comparisons_expected'])
                        log(f'{year} source {src}: verified completed checkpoint; skipped')
                        continue
                    bound = max(routes[p]['feasible'] for p in expected)*1.05
                    # Saved routes are feasible; with positive costs this is an
                    # upper bound for every destination optimum, not a spatial crop.
                    ready = sourcefolder/'distance_ready.json'
                    if ready.exists():
                        record = json.loads(ready.read_text())
                        if record['bound'] != bound:
                            raise ValueError('Checkpoint cost bound changed')
                        sgdb = Path(record['gdb'])
                        for name in ('distance','backlink'):
                            rr = arcpy.Raster(str(sgdb/name)); check_lattice(rr,ref)
                            if rr.width != ref.width or rr.height != ref.height:
                                raise ValueError('Checkpoint raster dimensions changed')
                            if array_hash(read_model(sgdb/name,ref)) != record['raster_hashes'][name]:
                                raise ValueError('Checkpoint distance/backlink values changed')
                        log(f'{year} source {src}: reusing completed cost-distance surface')
                    else:
                        if shutil.disk_usage(OUT).free < 5*1024**3:
                            raise RuntimeError('Less than 5 GB free; stopped before next solve. Checkpoints preserved.')
                        sgdb = sourcefolder/('attempt_'+uuid.uuid4().hex[:10]+'.gdb')
                        arcpy.management.CreateFileGDB(str(sourcefolder),sgdb.name)
                        arcpy.management.CopyFeatures([cores[src]],str(sgdb/'source'))
                        atomic_json(OUT/'STATUS.json',{'state':'cost_distance','year':year,'source':src,'bound':bound,'completed_comparisons':len(rows),'expected':180,'pid':os.getpid(),'time':now()})
                        log(f'{year} source {src}: START cost-distance; {len(expected)} destinations; completed {len(rows)}/180')
                        start = time.monotonic()
                        with arcpy.EnvManager(workspace=str(sgdb),scratchWorkspace=str(sgdb)):
                            arcpy.sa.CostDistance(str(sgdb/'source'),str(cp),maximum_distance=bound,out_backlink_raster=str(sgdb/'backlink')).save(str(sgdb/'distance'))
                        raster_hashes = {name:array_hash(read_model(sgdb/name,ref)) for name in ('distance','backlink')}
                        atomic_json(ready,{'gdb':str(sgdb),'bound':bound,'seconds':time.monotonic()-start,'raster_hashes':raster_hashes})
                        log(f'{year} source {src}: FINISHED cost-distance in {(time.monotonic()-start)/60:.1f} minutes')
                    completed = []
                    for pair in expected:
                        receipt = sourcefolder/f'pair_{pair[0]}_{pair[1]}.json'
                        if receipt.exists():
                            r = json.loads(receipt.read_text())
                            geom,cost = generated(r['candidate_path'])
                            if digest(bytes(geom.WKB)) != r['geometry_sha256'] or cost != r['new_cost']:
                                raise ValueError('Path checkpoint changed')
                        else:
                            token = uuid.uuid4().hex[:10]
                            dst = sgdb/f'dst_{pair[1]}_{token}'; path = sgdb/f'route_{pair[1]}_{token}'
                            arcpy.management.CopyFeatures([cores[pair[1]]],str(dst))
                            with arcpy.EnvManager(workspace=str(sgdb),scratchWorkspace=str(sgdb)):
                                arcpy.sa.CostPathAsPolyline(str(dst),str(sgdb/'distance'),str(sgdb/'backlink'),str(path),'BEST_SINGLE',arcpy.Describe(str(dst)).OIDFieldName)
                            r = compare(year,pair,path,data,cores)
                            atomic_json(receipt,r)
                        if (r['year'],r['from_core'],r['to_core']) != (year,*pair):
                            raise ValueError('Wrong pair checkpoint identity')
                        completed.append(r)
                        log(f'{year} {pair[0]}-{pair[1]}: verified route; cost change {r["optimized_cost_change_pct"]:+.2f}%')
                    atomic_json(done,completed)
                    rows.extend(completed); summarize(rows,plan['comparisons_expected'])
                    atomic_json(OUT/'STATUS.json',{'state':'checkpoint','completed_comparisons':len(rows),'expected':180,'pid':os.getpid(),'time':now()})
            del data
        if len(rows)!=180 or len({(r['year'],r['from_core'],r['to_core']) for r in rows})!=180:
            raise ValueError('Final completeness verification failed')
        atomic_json(OUT/'STATUS.json',{'state':'COMPLETE','completed_comparisons':180,'expected':180,'time':now(),'policy':POLICY})
        log('COMPLETE: 180 verified comparisons. Read SUMMARY.md. Production data and Circuitscape unchanged.')
    except BaseException as exc:
        atomic_json(OUT/'STATUS.json',{'state':'STOPPED','error':str(exc),'completed_comparisons_this_session':len(rows),'time':now()})
        traceback.print_exc()
        raise
    finally:
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
        lock.unlink(missing_ok=True)

if __name__ == '__main__':
    if '--preflight' in sys.argv:
        preflight()
    else:
        run()
