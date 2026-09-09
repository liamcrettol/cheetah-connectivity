"""Smoke-test overnight extraction using EXISTING pilot cost-distance only.

Creates one new diagnostic route and report; never runs CostDistance.
"""
from pathlib import Path
import uuid
import json
import arcpy
import run_vcf_v2_balanced_overnight as w

def main():
    arcpy.CheckOutExtension('Spatial')
    cores = {int(c):g for c,g in arcpy.da.SearchCursor(str(w.CORES),['CORE_ID','SHAPE@'])}
    pairs = {tuple(sorted((int(a),int(b)))) for a,b in arcpy.da.SearchCursor(str(w.GDB/'least_cost_paths_temporal_veg_balanced_2016'),['FROM_ID','TO_ID'])}
    data = w.load_year(2016,cores,pairs)
    ref = data[0]
    pilot = Path(r'C:\cheetah\diagnostics\vcf_v2_pair17_24_2016_20260903_155703_741091\test.gdb')
    for name in ('cost_distance','backlink'):
        w.read_model(pilot/name,ref)
    folder = Path(r'C:\cheetah\diagnostics')/('overnight_extraction_smoke_'+uuid.uuid4().hex[:10])
    folder.mkdir()
    gdb = folder/'test.gdb'
    arcpy.management.CreateFileGDB(str(folder),gdb.name)
    with arcpy.EnvManager(overwriteOutput=False, addOutputsToMap=False, mask=None,
        extent=ref.extent, cellSize=ref.meanCellWidth, snapRaster=str(w.GDB/'resistance_temporal_veg_balanced_2016'),
        outputCoordinateSystem=ref.spatialReference,workspace=str(gdb),scratchWorkspace=str(gdb)):
        arcpy.management.CopyFeatures([cores[24]],str(gdb/'destination'))
        arcpy.sa.CostPathAsPolyline(str(gdb/'destination'),str(pilot/'cost_distance'),str(pilot/'backlink'),
            str(gdb/'route'),'BEST_SINGLE',arcpy.Describe(str(gdb/'destination')).OIDFieldName)
        result = w.compare(2016,(17,24),gdb/'route',data,cores)
        assert abs(result['optimized_cost_change_pct']-1.0403360665147465)<1e-8
        assert abs(result['new_length_km']-33.071067811865476)<1e-5
        with (folder/'result.json').open('x') as f: json.dump(result,f,indent=2)
    print('EXTRACTION SMOKE TEST PASSED: copied geometry destination, solver field, route cost, endpoints and overlap.')
    print('No new cost-distance calculation. Output:',folder)

if __name__ == '__main__': main()
