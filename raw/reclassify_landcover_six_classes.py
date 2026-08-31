"""Create six-class MCD12Q1 context rasters from the approved crosswalk.

Run in ArcGIS Pro's Python window.  Source TIFFs are never changed.  Outputs
are written to the project working geodatabase and added to a map group.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import arcpy
from arcpy.sa import Raster, Reclassify, RemapValue


SOURCE_FOLDER = Path(
    r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah\rasters\gee_exports"
)
OUTPUT_GDB = Path(r"C:\cheetah\gdb\cheetah_working.gdb")
PROJECT_GROUP = "Cheetah project"
GROUP_NAME = "06 Land cover · six-class context"
SNAP_RASTER = r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah_connectivity.gdb\snapgrid_1km"
EXTENT_MASK = r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah_connectivity.gdb\extent_buffered"

# land-cover code -> project class value
# 1=open vegetation; 2=woody; 3=cropland; 4=built; 5=water; 6=bare
REMAP = RemapValue(
    [
        [0, 5], [1, 2], [2, 2], [3, 2], [4, 2], [5, 2], [6, 2],
        [7, 1], [8, 2], [9, 1], [10, 1], [11, 5], [12, 3], [13, 4],
        [14, 3], [15, 6], [16, 6], [17, "NODATA"],
    ]
)


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


def find_or_create_group(map_object):
    wanted = PROJECT_GROUP + "\\" + GROUP_NAME
    matches = [
        layer for layer in map_object.listLayers()
        if layer.isGroupLayer and layer.longName == wanted
    ]
    if len(matches) > 1:
        raise RuntimeError(f"More than one group named {wanted!r} exists.")
    if matches:
        return matches[0]
    parent_matches = [
        layer for layer in map_object.listLayers()
        if layer.isGroupLayer and layer.longName == PROJECT_GROUP
    ]
    if len(parent_matches) != 1:
        raise RuntimeError(f"Expected one group named {PROJECT_GROUP!r}; found {len(parent_matches)}.")
    return map_object.createGroupLayer(GROUP_NAME, parent_matches[0])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--map-name", default="Map")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Replace existing lc6 outputs. Omit this unless replacement is intended.",
    )
    args = parser.parse_args()

    if arcpy.CheckExtension("Spatial") != "Available":
        raise RuntimeError("Spatial Analyst is not available in this ArcGIS Pro session.")

    if not OUTPUT_GDB.exists():
        raise RuntimeError(f"Working geodatabase not found: {OUTPUT_GDB}")

    aprx = arcpy.mp.ArcGISProject("CURRENT")
    maps = aprx.listMaps(args.map_name)
    map_object = maps[0] if maps else aprx.activeMap
    if map_object is None:
        raise RuntimeError("No active map was found.")

    for path in (SNAP_RASTER, EXTENT_MASK):
        if not arcpy.Exists(path):
            raise RuntimeError(f"Required input is missing: {path}")

    arcpy.CheckOutExtension("Spatial")
    try:
        group = find_or_create_group(map_object)
        arcpy.env.overwriteOutput = args.replace
        arcpy.env.snapRaster = SNAP_RASTER
        arcpy.env.cellSize = SNAP_RASTER
        arcpy.env.extent = EXTENT_MASK
        arcpy.env.mask = EXTENT_MASK

        for year in (2012, 2016, 2020, 2024):
            source = SOURCE_FOLDER / f"lc_{year}_1km.tif"
            output = OUTPUT_GDB / f"lc6_{year}_1km"
            if not arcpy.Exists(str(source)):
                raise RuntimeError(f"Source raster not found: {source}")
            if arcpy.Exists(str(output)) and not args.replace:
                print(f"skipped existing: {output}")
                continue
            if arcpy.Exists(str(output)):
                replace_dataset(map_object, str(output))

            print(f"reclassifying: {source.name}")
            result = Reclassify(Raster(str(source)), "Value", REMAP, "NODATA")
            result.save(str(output))
            arcpy.management.BuildRasterAttributeTable(str(output), "Overwrite")
            added_layer = map_object.addDataFromPath(str(output))
            map_object.addLayerToGroup(group, added_layer, "BOTTOM")
            map_object.removeLayer(added_layer)
            print(f"created: {output}")

        aprx.save()
    finally:
        arcpy.env.snapRaster = None
        arcpy.env.cellSize = None
        arcpy.env.extent = None
        arcpy.env.mask = None
        arcpy.CheckInExtension("Spatial")

    print("Complete. Original lc_YYYY_1km.tif files were not changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
