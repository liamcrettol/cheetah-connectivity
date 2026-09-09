"""Finalize primary cheetah core patches for connectivity analysis.

Definition: Weise density raster value >=51 (approximately 0.51 cheetahs per
100 km2), eight-neighbor contiguity, and minimum contiguous area 500 km2.
"""

from datetime import datetime
from pathlib import Path
import csv
import os

import arcpy
from arcpy.sa import Con, Lookup, Raster, RegionGroup, SetNull

DENSITY=r"C:\cheetah\gdb\cheetah_working.gdb\cheetah_density_aligned_1km"
GDB=r"C:\cheetah\gdb\cheetah_working.gdb"
SNAP=r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah_connectivity.gdb\snapgrid_1km"
MASK=r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah_connectivity.gdb\extent_buffered"
CORE_RASTER=os.path.join(GDB,"cheetah_core_primary_density051_min500_1km")
CORE_POLYGONS=os.path.join(GDB,"cheetah_core_primary_density051_min500")
THRESHOLD_STORED=51
THRESHOLD_BIOLOGICAL=0.51
MINIMUM_KM2=500
BACKUPS=Path(r"C:\cheetah\backups")
REPORTS=Path(r"C:\cheetah\reports")
PARENT="Cheetah project"
GROUP="14 Connectivity cores · selected"


def remove_refs(m,dataset):
    target=os.path.normcase(os.path.normpath(dataset))
    for layer in list(m.listLayers()):
        try:
            if layer.supports("DATASOURCE") and os.path.normcase(os.path.normpath(layer.dataSource))==target:
                m.removeLayer(layer)
        except Exception: pass


def replace(m,dataset):
    remove_refs(m,dataset)
    if arcpy.Exists(dataset): arcpy.management.Delete(dataset)


def add_grouped(m,target,dataset,visible):
    loose=m.addDataFromPath(dataset); added=m.addLayerToGroup(target,loose,"BOTTOM"); m.removeLayer(loose)
    if not added: raise RuntimeError(f"Could not group {dataset}")
    added[0].visible=visible


def main():
    arcpy.CheckOutExtension("Spatial")
    for path in (DENSITY,GDB,SNAP,MASK):
        if not arcpy.Exists(path): raise FileNotFoundError(path)
    aprx=arcpy.mp.ArcGISProject("CURRENT"); maps=aprx.listMaps("Map"); m=maps[0] if maps else aprx.activeMap
    parents=[x for x in m.listLayers() if x.isGroupLayer and x.longName==PARENT]
    if len(parents)!=1: raise RuntimeError(f"Expected one {PARENT!r} group; found {len(parents)}")
    wanted=PARENT+"\\"+GROUP; groups=[x for x in m.listLayers() if x.isGroupLayer and x.longName==wanted]
    target=groups[0] if groups else m.createGroupLayer(GROUP,parents[0])

    BACKUPS.mkdir(parents=True,exist_ok=True); REPORTS.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now().strftime("%Y%m%d_%H%M%S"); backup=BACKUPS/f"{Path(aprx.filePath).stem}_before_primary_cores_{stamp}.aprx"
    aprx.saveACopy(str(backup)); print(f"backup: {backup}")
    arcpy.env.overwriteOutput=True; arcpy.env.snapRaster=SNAP; arcpy.env.cellSize=SNAP
    arcpy.env.extent=SNAP; arcpy.env.mask=MASK; arcpy.env.outputCoordinateSystem=arcpy.Describe(SNAP).spatialReference

    temporary=os.path.join(GDB,"tmp_primary_core_regions")
    for path in (temporary,CORE_RASTER,CORE_POLYGONS): replace(m,path)
    candidate=Con(Raster(DENSITY)>=THRESHOLD_STORED,1)
    RegionGroup(candidate,"EIGHT","WITHIN","NO_LINK").save(temporary)
    arcpy.management.BuildRasterAttributeTable(temporary,"OVERWRITE")
    cell_area=(float(arcpy.Describe(SNAP).meanCellWidth)*float(arcpy.Describe(SNAP).meanCellHeight))/1_000_000.0
    minimum_cells=MINIMUM_KM2/cell_area
    SetNull(Lookup(temporary,"COUNT")<minimum_cells,Raster(temporary)).save(CORE_RASTER)
    arcpy.management.BuildRasterAttributeTable(CORE_RASTER,"OVERWRITE")
    arcpy.conversion.RasterToPolygon(CORE_RASTER,CORE_POLYGONS,"NO_SIMPLIFY","Value","SINGLE_OUTER_PART")
    arcpy.management.AddField(CORE_POLYGONS,"CORE_ID","LONG")
    arcpy.management.AddField(CORE_POLYGONS,"AREA_KM2","DOUBLE")
    arcpy.management.AddField(CORE_POLYGONS,"DENS_MIN","DOUBLE")
    arcpy.management.CalculateField(CORE_POLYGONS,"CORE_ID","!gridcode!","PYTHON3")
    arcpy.management.CalculateGeometryAttributes(CORE_POLYGONS,[["AREA_KM2","AREA_GEODESIC"]],area_unit="SQUARE_KILOMETERS")
    arcpy.management.CalculateField(CORE_POLYGONS,"DENS_MIN",str(THRESHOLD_BIOLOGICAL),"PYTHON3")

    rows=[]
    with arcpy.da.SearchCursor(CORE_POLYGONS,["CORE_ID","AREA_KM2"]) as cursor:
        rows=sorted([(int(core),float(area)) for core,area in cursor])
    report=REPORTS/"primary_cheetah_cores.csv"
    with report.open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f); w.writerow(["core_id","area_km2","minimum_density_cheetahs_per_100km2","minimum_patch_km2","connectivity_rule"])
        for core,area in rows: w.writerow([core,area,THRESHOLD_BIOLOGICAL,MINIMUM_KM2,"eight-neighbor"])
    if arcpy.Exists(temporary): arcpy.management.Delete(temporary)

    add_grouped(m,target,CORE_RASTER,False); add_grouped(m,target,CORE_POLYGONS,True); target.visible=True
    # Candidate alternatives remain available but are hidden.
    for layer in m.listLayers():
        try:
            if layer.isGroupLayer and layer.longName==PARENT+"\\14 Connectivity cores · candidates": layer.visible=False
        except Exception: pass
    aprx.save()
    print(f"retained cores: {len(rows)}")
    print(f"total retained area: {sum(area for _,area in rows):.2f} km2")
    print(f"raster: {CORE_RASTER}"); print(f"polygons: {CORE_POLYGONS}"); print(f"report: {report}")
    print("Complete. Baseline density, candidate thresholds, and resistance surfaces were unchanged.")

if __name__=="__main__": main()
