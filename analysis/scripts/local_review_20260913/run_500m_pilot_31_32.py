"""Bounded 500 m local-grid pilot for core link 31--32."""
from pathlib import Path
import json, math
import arcpy
import numpy as np
from arcpy.sa import Con, CostDistance, CostPathAsPolyline, ExtractByMask, Raster

ROOT=Path(r"C:\Users\liamc\Documents\Codex\2026-09-11\i-want-help")
GDB=ROOT/"work"/"terrain_sensitivity_31_32.gdb"
MASK=GDB/"pair_31_32_analysis_mask"
SLOPE30=GDB/"slope_copdem30m_pair_31_32"
BASE=GDB/"resistance_2024_baseline_mean"
TERRAIN=GDB/"terrain_baseline_mean"
CORES=ROOT/"work"/"resistances_package_audit"/"commondata"/"cheetah_working.gdb"/"cheetah_core_primary_density051_min500"
SAVED=ROOT/"work"/"resistances_package_audit"/"commondata"/"cheetah_working.gdb"/"conservation_priority_paths_temporal"
OUT=GDB/"resistance_2024_pilot_500m_31_32"
P90=GDB/"slope_p90_copdem30m_to_500m_31_32"
PATH=GDB/"path_31_32_pilot_500m"
SUMMARY=ROOT/"outputs"/"pilot_500m_31_32_summary.json"

for p in (MASK,SLOPE30,BASE,TERRAIN,CORES,SAVED):
    if not arcpy.Exists(str(p)): raise FileNotFoundError(p)
ref=Raster(str(BASE)); src=Raster(str(SLOPE30)); cell=500.0; me=arcpy.Describe(str(MASK)).extent
arcpy.env.overwriteOutput=True; arcpy.env.outputCoordinateSystem=ref.spatialReference; arcpy.env.mask=str(MASK); arcpy.env.extent=me; arcpy.env.parallelProcessingFactor="75%"
a=arcpy.RasterToNumPyArray(src,nodata_to_value=-9999).astype('float32'); a[a<=-9990]=np.nan
x0=ref.extent.XMin+math.floor((me.XMin-ref.extent.XMin)/cell)*cell; x1=ref.extent.XMin+math.ceil((me.XMax-ref.extent.XMin)/cell)*cell
y0=ref.extent.YMin+math.floor((me.YMin-ref.extent.YMin)/cell)*cell; y1=ref.extent.YMin+math.ceil((me.YMax-ref.extent.YMin)/cell)*cell
nr,nc=int(round((y1-y0)/cell)),int(round((x1-x0)/cell)); sx=float(src.meanCellWidth); sy=float(src.meanCellHeight)
xs=src.extent.XMin+(np.arange(src.width)+.5)*sx; ys=src.extent.YMax-(np.arange(src.height)+.5)*sy; out=np.full((nr,nc),-9999,dtype='float32')
for r in range(nr):
    yy1=y1-r*cell; yy0=yy1-cell; ir=np.flatnonzero((ys>=yy0)&(ys<yy1))
    for c in range(nc):
        xx0=x0+c*cell; xx1=xx0+cell; ic=np.flatnonzero((xs>=xx0)&(xs<xx1))
        if ir.size and ic.size:
            v=a[np.ix_(ir,ic)]
            if np.isfinite(v).any(): out[r,c]=np.nanpercentile(v,90)
if arcpy.Exists(str(P90)): arcpy.management.Delete(str(P90))
arcpy.NumPyArrayToRaster(out,arcpy.Point(x0,y0),cell,cell,-9999).save(str(P90)); arcpy.management.DefineProjection(str(P90),ref.spatialReference)
arcpy.env.snapRaster=str(P90); arcpy.env.cellSize=str(P90)
base500=GDB/"pilot_base_500m"; terr500=GDB/"pilot_terrain_mean_500m"
for p in (base500,terr500,OUT,PATH):
    if arcpy.Exists(str(p)): arcpy.management.Delete(str(p))
arcpy.management.Resample(str(BASE),str(base500),500,"BILINEAR"); arcpy.management.Resample(str(TERRAIN),str(terr500),500,"BILINEAR")
terrain_p90=1+9*Con(Raster(str(P90))<=10,0,Con(Raster(str(P90))>=30,1,(Raster(str(P90))-10)/20))
(ExtractByMask(Raster(str(base500))-0.2*Raster(str(terr500))+0.2*terrain_p90,str(MASK))).save(str(OUT))
arcpy.management.MakeFeatureLayer(str(CORES),'pilot_src','CORE_ID=31'); arcpy.management.MakeFeatureLayer(str(CORES),'pilot_dst','CORE_ID=32')
cd=GDB/'pilot_cd_500m'; bl=GDB/'pilot_bl_500m'
CostDistance('pilot_src',str(OUT),out_backlink_raster=str(bl)).save(str(cd)); CostPathAsPolyline('pilot_dst',str(cd),str(bl),str(PATH),'BEST_SINGLE','CORE_ID')
with arcpy.da.SearchCursor(str(PATH),['SHAPE@']) as cur: geom=next(cur)[0]
where='(FROM_ID=31 AND TO_ID=32) OR (FROM_ID=32 AND TO_ID=31)'
with arcpy.da.SearchCursor(str(SAVED),['SHAPE@','PATH_KM','COST_RAW'],where) as cur: saved_geom,saved_len,saved_cost=next(cur)
summary={'pair':[31,32],'method':'30 m Copernicus slope 90th percentile aggregated to 500 m; original non-terrain resistance resampled to 500 m','path_feature_class':str(PATH),'resistance_raster':str(OUT),'saved_path_length_km':float(saved_len),'pilot_path_length_km':geom.length/1000,'saved_cost_raw':float(saved_cost),'pilot_cost':None,'overlap_with_saved_path_within_1km_percent':100*geom.intersect(saved_geom.buffer(1000),2).length/geom.length,'overlap_with_saved_path_within_5km_percent':100*geom.intersect(saved_geom.buffer(5000),2).length/geom.length}
with arcpy.da.SearchCursor(str(PATH),['PATHCOST']) as cur:
    try: summary['pilot_cost']=float(next(cur)[0])
    except Exception: pass
SUMMARY.parent.mkdir(parents=True,exist_ok=True); SUMMARY.write_text(json.dumps(summary,indent=2),encoding='utf-8'); print(json.dumps(summary,indent=2))
