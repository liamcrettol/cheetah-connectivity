"""Project/clip HydroRIVERS + HydroLAKES, combine into a water mask, and
compute distance-to-water (Step 09.4).

Rivers and permanent water polygons are rasterized separately (can't Merge
lines and polygons into one feature class), combined into a single binary
water mask, then Euclidean Distance runs on that mask.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import arcpy
from arcpy.sa import Con, EucDistance, IsNull, Raster


RIVERS_SHP = r"C:\cheetah\raw\hydrosheds\HydroRIVERS_v10_af_shp\HydroRIVERS_v10_af_shp\HydroRIVERS_v10_af.shp"
LAKES_SHP = r"C:\cheetah\raw\hydrosheds\HydroLAKES_polys_v10_shp\HydroLAKES_polys_v10_shp\HydroLAKES_polys_v10.shp"
WORKING_GDB = Path(r"C:\cheetah\gdb\cheetah_working.gdb")
BACKUP_FOLDER = Path(r"C:\cheetah\backups")
SNAP_RASTER = r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah_connectivity.gdb\snapgrid_1km"
EXTENT_MASK = r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah_connectivity.gdb\extent_buffered"
PROJECT_GROUP = "Cheetah project"
GROUP_NAME = "09 Hydrology · HydroSHEDS"


def one_group(map_object, long_name: str):
    matches = [layer for layer in map_object.listLayers() if layer.isGroupLayer and layer.longName == long_name]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one group named {long_name!r}; found {len(matches)}.")
    return matches[0]


def find_or_create_group(map_object, parent):
    long_name = parent.longName + "\\" + GROUP_NAME
    matches = [layer for layer in map_object.listLayers() if layer.isGroupLayer and layer.longName == long_name]
    if len(matches) > 1:
        raise RuntimeError(f"More than one group named {long_name!r} exists.")
    return matches[0] if matches else map_object.createGroupLayer(GROUP_NAME, parent)


def remove_map_references(map_object, dataset: str):
    for layer in list(map_object.listLayers()):
        if not layer.supports("DATASOURCE"):
            continue
        try:
            if layer.dataSource.lower() == dataset.lower():
                map_object.removeLayer(layer)
        except Exception:
            pass


def replace_dataset(map_object, dataset: str):
    remove_map_references(map_object, dataset)
    if arcpy.Exists(dataset):
        arcpy.management.Delete(dataset)


def add_to_group(map_object, group, dataset: str):
    added_layer = map_object.addDataFromPath(dataset)
    map_object.addLayerToGroup(group, added_layer, "BOTTOM")
    # addLayerToGroup can retarget the passed-in object to the new grouped
    # copy, so re-find any loose root copy fresh before removing it. If the
    # dataSource string format doesn't match cleanly for this data type,
    # there's simply nothing to clean up here.
    loose = [
        layer for layer in list(map_object.listLayers())
        if layer.longName == layer.name and layer.supports("DATASOURCE")
        and getattr(layer, "dataSource", "").lower() == dataset.lower()
    ]
    for stray in loose:
        map_object.removeLayer(stray)


def main() -> int:
    for path in (RIVERS_SHP, LAKES_SHP, SNAP_RASTER, EXTENT_MASK):
        if not arcpy.Exists(path):
            raise RuntimeError(f"Required input is missing: {path}")
    if not WORKING_GDB.exists():
        raise RuntimeError(f"Working geodatabase not found: {WORKING_GDB}")

    if arcpy.CheckExtension("Spatial") != "Available":
        raise RuntimeError("Spatial Analyst is not available in this ArcGIS Pro session.")
    arcpy.CheckOutExtension("Spatial")

    aprx = arcpy.mp.ArcGISProject("CURRENT")
    map_object = aprx.activeMap
    if map_object is None:
        raise RuntimeError("No active map was found.")
    project_group = one_group(map_object, PROJECT_GROUP)
    group = find_or_create_group(map_object, project_group)

    BACKUP_FOLDER.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUP_FOLDER / f"{Path(aprx.filePath).stem}_before_water_distance_{stamp}.aprx"
    aprx.saveACopy(str(backup))
    print(f"backup: {backup}")

    try:
        arcpy.env.snapRaster = SNAP_RASTER
        arcpy.env.cellSize = SNAP_RASTER
        arcpy.env.extent = EXTENT_MASK
        arcpy.env.mask = EXTENT_MASK
        arcpy.env.outputCoordinateSystem = arcpy.Describe(SNAP_RASTER).spatialReference

        # --- rivers: project + clip to the buffered extent ---
        rivers_clipped = str(WORKING_GDB / "hydrorivers_af_clipped")
        replace_dataset(map_object, rivers_clipped)
        print("clipping HydroRIVERS (this reprojects on the fly via Pairwise Clip)...")
        arcpy.analysis.PairwiseClip(RIVERS_SHP, EXTENT_MASK, rivers_clipped)
        add_to_group(map_object, group, rivers_clipped)
        print(f"created: {Path(rivers_clipped).name}")

        # --- lakes: project + clip to the buffered extent ---
        # HydroLAKES is a single ~820MB global file (no continental split like
        # HydroRIVERS), so this step is the slow one. Pairwise Clip handles it.
        lakes_clipped = str(WORKING_GDB / "hydrolakes_clipped")
        replace_dataset(map_object, lakes_clipped)
        print("clipping HydroLAKES (global file, this will take a few minutes)...")
        arcpy.analysis.PairwiseClip(LAKES_SHP, EXTENT_MASK, lakes_clipped)
        add_to_group(map_object, group, lakes_clipped)
        print(f"created: {Path(lakes_clipped).name}")

        # --- rasterize each to a binary water mask on the snap grid ---
        rivers_raster = str(WORKING_GDB / "_water_rivers_grid")
        lakes_raster = str(WORKING_GDB / "_water_lakes_grid")
        replace_dataset(map_object, rivers_raster)
        replace_dataset(map_object, lakes_raster)
        arcpy.conversion.PolylineToRaster(
            rivers_clipped, "OBJECTID", rivers_raster, "MAXIMUM_LENGTH", cellsize=SNAP_RASTER
        )
        arcpy.conversion.PolygonToRaster(
            lakes_clipped, "OBJECTID", lakes_raster, "MAXIMUM_AREA", cellsize=SNAP_RASTER
        )

        # --- combine into one binary mask: water = 1 where either source has data ---
        water_mask = str(WORKING_GDB / "water_mask_1km")
        replace_dataset(map_object, water_mask)
        combined = Con(~(IsNull(Raster(rivers_raster)) & IsNull(Raster(lakes_raster))), 1)
        combined.save(water_mask)
        arcpy.management.Delete(rivers_raster)
        arcpy.management.Delete(lakes_raster)
        add_to_group(map_object, group, water_mask)
        print("created: water_mask_1km")

        # --- distance to nearest water ---
        dist_output = str(WORKING_GDB / "dist_water_1km")
        replace_dataset(map_object, dist_output)
        EucDistance(water_mask, cell_size=SNAP_RASTER).save(dist_output)
        add_to_group(map_object, group, dist_output)
        print("created: dist_water_1km")

        aprx.save()
    finally:
        arcpy.env.snapRaster = None
        arcpy.env.cellSize = None
        arcpy.env.extent = None
        arcpy.env.mask = None
        arcpy.env.outputCoordinateSystem = None
        arcpy.CheckInExtension("Spatial")

    print("Complete. dist_water_1km is a resource/context variable per the protocol,")
    print("not treated as a barrier -- most of these rivers are seasonal.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
