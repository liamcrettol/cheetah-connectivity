"""Evaluate density and minimum-area definitions for cheetah core patches.

Creates aligned candidate core rasters for top 10%, 20%, and 30% density,
using 500 km2 as the primary minimum. Reports 100/500/1000 km2 sensitivity.
Original baseline evidence is preserved.
"""

from datetime import datetime
from pathlib import Path
import csv
import os

import arcpy
import numpy as np
from arcpy.sa import Con, ExtractByMask, Lookup, Raster, RegionGroup, SetNull

SOURCE = r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah\raw\dryad_weise2017\cheetahsouthernafricadensity.tif"
GDB = r"C:\cheetah\gdb\cheetah_working.gdb"
SNAP = r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah_connectivity.gdb\snapgrid_1km"
MASK = r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah_connectivity.gdb\extent_buffered"
ALIGNED = os.path.join(GDB, "cheetah_density_aligned_1km")
BACKUPS = Path(r"C:\cheetah\backups")
REPORTS = Path(r"C:\cheetah\reports")
PARENT = "Cheetah project"
GROUP = "14 Connectivity cores · candidates"
TOP_PERCENTAGES = (10, 20, 30)
AREA_TESTS_KM2 = (100, 500, 1000)
PRIMARY_MINIMUM_KM2 = 500


def signature(path):
    d = arcpy.Describe(path)
    return (int(arcpy.management.GetRasterProperties(path,"COLUMNCOUNT").getOutput(0)),
            int(arcpy.management.GetRasterProperties(path,"ROWCOUNT").getOutput(0)),
            round(float(d.meanCellWidth),6), round(float(d.meanCellHeight),6),
            tuple(round(v,3) for v in (d.extent.XMin,d.extent.YMin,d.extent.XMax,d.extent.YMax)))


def remove_refs(map_object, dataset):
    target=os.path.normcase(os.path.normpath(dataset))
    for layer in list(map_object.listLayers()):
        try:
            if layer.supports("DATASOURCE") and os.path.normcase(os.path.normpath(layer.dataSource)) == target:
                map_object.removeLayer(layer)
        except Exception: pass


def replace(map_object, dataset):
    remove_refs(map_object,dataset)
    if arcpy.Exists(dataset): arcpy.management.Delete(dataset)


def add_grouped(map_object, target_group, dataset, visible=False):
    loose=map_object.addDataFromPath(dataset)
    added=map_object.addLayerToGroup(target_group,loose,"BOTTOM")
    map_object.removeLayer(loose)
    if not added: raise RuntimeError(f"Could not group {dataset}")
    added[0].visible=visible


def main():
    arcpy.CheckOutExtension("Spatial")
    for path in (SOURCE,GDB,SNAP,MASK):
        if not arcpy.Exists(path): raise FileNotFoundError(path)
    aprx=arcpy.mp.ArcGISProject("CURRENT")
    maps=aprx.listMaps("Map"); m=maps[0] if maps else aprx.activeMap
    parents=[x for x in m.listLayers() if x.isGroupLayer and x.longName==PARENT]
    if len(parents)!=1: raise RuntimeError(f"Expected one {PARENT!r} group; found {len(parents)}")
    wanted=PARENT+"\\"+GROUP
    groups=[x for x in m.listLayers() if x.isGroupLayer and x.longName==wanted]
    target_group=groups[0] if groups else m.createGroupLayer(GROUP,parents[0])

    BACKUPS.mkdir(parents=True,exist_ok=True); REPORTS.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now().strftime("%Y%m%d_%H%M%S")
    backup=BACKUPS/f"{Path(aprx.filePath).stem}_before_core_thresholds_{stamp}.aprx"
    aprx.saveACopy(str(backup)); print(f"backup: {backup}")

    arcpy.env.overwriteOutput=True; arcpy.env.snapRaster=SNAP; arcpy.env.cellSize=SNAP
    arcpy.env.extent=SNAP; arcpy.env.mask=MASK
    arcpy.env.outputCoordinateSystem=arcpy.Describe(SNAP).spatialReference

    temporary=os.path.join(GDB,"tmp_cheetah_density_projected")
    for path in (temporary,ALIGNED): replace(m,path)
    arcpy.management.ProjectRaster(SOURCE,temporary,arcpy.Describe(SNAP).spatialReference,"BILINEAR","1000 1000")
    ExtractByMask(temporary,MASK,"INSIDE").save(ALIGNED)
    if arcpy.Exists(temporary): arcpy.management.Delete(temporary)
    if signature(ALIGNED)!=signature(SNAP): raise RuntimeError(f"Density alignment failed: {signature(ALIGNED)} != {signature(SNAP)}")

    sentinel=-3.0e38
    values=arcpy.RasterToNumPyArray(ALIGNED,nodata_to_value=sentinel).astype(np.float32,copy=False)
    positive=values[(values>0)&(values>sentinel/2)&np.isfinite(values)]
    if positive.size==0: raise RuntimeError("Aligned density contains no positive cells")

    cell_area_km2=(float(arcpy.Describe(SNAP).meanCellWidth)*float(arcpy.Describe(SNAP).meanCellHeight))/1_000_000.0
    report_rows=[]
    outputs=[]
    for top in TOP_PERCENTAGES:
        threshold=float(np.percentile(positive,100-top))
        candidate=Con(Raster(ALIGNED)>=threshold,1)
        regions=RegionGroup(candidate,"EIGHT","WITHIN","NO_LINK")
        region_path=os.path.join(GDB,f"tmp_core_regions_top{top}")
        if arcpy.Exists(region_path): arcpy.management.Delete(region_path)
        regions.save(region_path); arcpy.management.BuildRasterAttributeTable(region_path,"OVERWRITE")
        patch_areas=[]
        with arcpy.da.SearchCursor(region_path,["COUNT"]) as cursor:
            patch_areas=[float(row[0])*cell_area_km2 for row in cursor]
        for minimum in AREA_TESTS_KM2:
            kept=[area for area in patch_areas if area>=minimum]
            report_rows.append([top,threshold,minimum,len(patch_areas),len(kept),sum(kept),min(kept) if kept else 0,max(kept) if kept else 0])
        count_raster=Lookup(region_path,"COUNT")
        minimum_cells=PRIMARY_MINIMUM_KM2/cell_area_km2
        output=os.path.join(GDB,f"core_top{top}_min500km2_1km")
        replace(m,output); SetNull(count_raster<minimum_cells,Raster(region_path)).save(output)
        arcpy.management.BuildRasterAttributeTable(output,"OVERWRITE")
        outputs.append(output); print(f"created candidate: core_top{top}_min500km2_1km; density threshold {threshold}")
        arcpy.management.Delete(region_path)

    for output in outputs: add_grouped(m,target_group,output,visible=Path(output).name=="core_top20_min500km2_1km")
    target_group.visible=True
    report=REPORTS/"cheetah_core_threshold_tradeoffs.csv"
    with report.open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f); w.writerow(["top_density_percent","density_threshold","minimum_patch_km2","patches_before_filter","patches_retained","retained_area_km2","smallest_retained_km2","largest_retained_km2"]); w.writerows(report_rows)
    aprx.save()
    print(f"positive density cells evaluated: {positive.size}")
    print(f"primary minimum patch: {PRIMARY_MINIMUM_KM2} km2")
    print(f"report: {report}")
    print("Complete. Original density evidence and resistance surfaces were unchanged.")

if __name__=="__main__": main()
