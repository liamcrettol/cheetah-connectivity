"""Create absolute and proportional change rasters for built-up and VCF layers.

Nighttime lights are intentionally excluded until gas flares have been masked.
For proportional change, zero-valued baseline pixels are NoData because a
percentage change from zero is undefined. Original source rasters are untouched.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import arcpy
from arcpy.sa import Raster, SetNull


SOURCE_FOLDER = Path(
    r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah\rasters\gee_exports"
)
OUTPUT_GDB = Path(r"C:\cheetah\gdb\cheetah_working.gdb")
BACKUP_FOLDER = Path(r"C:\cheetah\backups")
PROJECT_GROUP = "Cheetah project"
LANDCOVER_GROUP = "06 Land cover · six-class context"
ABSOLUTE_GROUP = "08 Continuous change · absolute"
PROPORTIONAL_GROUP = "08 Continuous change · proportional"
YEARS = (2012, 2016, 2020, 2024)
PAIRS = ((2012, 2016), (2016, 2020), (2020, 2024), (2012, 2024))
VARIABLES = ("built", "vcf_tree", "vcf_nontree", "vcf_bare")
SNAP_RASTER = r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah_connectivity.gdb\snapgrid_1km"
EXTENT_MASK = r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah_connectivity.gdb\extent_buffered"


def one_group(map_object, long_name: str):
    matches = [
        layer for layer in map_object.listLayers()
        if layer.isGroupLayer and layer.longName == long_name
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one group named {long_name!r}; found {len(matches)}.")
    return matches[0]


def find_or_create_nested_group(map_object, parent, name: str):
    wanted = parent.longName + "\\" + name
    matches = [layer for layer in map_object.listLayers() if layer.isGroupLayer and layer.longName == wanted]
    if len(matches) > 1:
        raise RuntimeError(f"More than one group named {wanted!r} exists.")
    return matches[0] if matches else map_object.createGroupLayer(name, parent)


def is_in_group(map_object, group, dataset: str) -> bool:
    wanted_prefix = group.longName + "\\"
    return any(
        layer.longName.startswith(wanted_prefix)
        and layer.supports("DATASOURCE")
        and getattr(layer, "dataSource", "").lower() == dataset.lower()
        for layer in map_object.listLayers()
    )


def add_to_group(map_object, group, dataset: str):
    if is_in_group(map_object, group, dataset):
        return
    map_object.addDataFromPath(dataset)
    # addLayerToGroup creates another map reference. Remove only the temporary
    # root reference afterward, using a fresh map-layer lookup.
    temporary = [
        layer for layer in map_object.listLayers()
        if layer.longName == layer.name
        and layer.supports("DATASOURCE")
        and getattr(layer, "dataSource", "").lower() == dataset.lower()
    ]
    if len(temporary) != 1:
        raise RuntimeError(f"Could not identify one temporary map reference for {dataset}")
    map_object.addLayerToGroup(group, temporary[0], "BOTTOM")
    # Re-find the root reference after grouping. ArcPy can retarget the Layer
    # object passed into addLayerToGroup, so removing that original object may
    # otherwise remove the grouped copy and leave the loose one behind.
    roots_after = [
        layer for layer in map_object.listLayers()
        if layer.longName == layer.name
        and layer.supports("DATASOURCE")
        and getattr(layer, "dataSource", "").lower() == dataset.lower()
    ]
    if len(roots_after) != 1:
        raise RuntimeError(f"Could not identify one loose map reference for {dataset} after grouping")
    map_object.removeLayer(roots_after[0])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--map-name", default="Map")
    parser.add_argument("--replace", action="store_true", help="Replace existing change rasters.")
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

    project_group = one_group(map_object, PROJECT_GROUP)
    landcover_group = one_group(map_object, PROJECT_GROUP + "\\" + LANDCOVER_GROUP)
    absolute_group = find_or_create_nested_group(map_object, project_group, ABSOLUTE_GROUP)
    proportional_group = find_or_create_nested_group(map_object, project_group, PROPORTIONAL_GROUP)
    map_object.moveLayer(landcover_group, absolute_group, "AFTER")
    map_object.moveLayer(absolute_group, proportional_group, "AFTER")

    BACKUP_FOLDER.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUP_FOLDER / f"{Path(aprx.filePath).stem}_before_change_layers_{stamp}.aprx"
    aprx.saveACopy(str(backup))
    print(f"backup: {backup}")

    for path in (SNAP_RASTER, EXTENT_MASK):
        if not arcpy.Exists(path):
            raise RuntimeError(f"Required input is missing: {path}")

    arcpy.CheckOutExtension("Spatial")
    try:
        arcpy.env.snapRaster = SNAP_RASTER
        arcpy.env.cellSize = SNAP_RASTER
        arcpy.env.extent = EXTENT_MASK
        arcpy.env.mask = EXTENT_MASK

        for variable in VARIABLES:
            for earlier, later in PAIRS:
                source_earlier = SOURCE_FOLDER / f"{variable}_{earlier}_1km.tif"
                source_later = SOURCE_FOLDER / f"{variable}_{later}_1km.tif"
                if not arcpy.Exists(str(source_earlier)) or not arcpy.Exists(str(source_later)):
                    raise RuntimeError(f"Missing source raster pair: {source_earlier.name}, {source_later.name}")

                baseline = Raster(str(source_earlier))
                comparison = Raster(str(source_later))
                absolute_output = str(OUTPUT_GDB / f"d_{variable}_{earlier}_{later}_1km")
                proportional_output = str(OUTPUT_GDB / f"p_{variable}_{earlier}_{later}_1km")

                for output, expression, group, label in (
                    (absolute_output, comparison - baseline, absolute_group, "absolute"),
                    (proportional_output, SetNull(baseline <= 0, ((comparison - baseline) / baseline) * 100), proportional_group, "proportional"),
                ):
                    if arcpy.Exists(output) and not args.replace:
                        print(f"keeping existing {label}: {Path(output).name}")
                    else:
                        if arcpy.Exists(output):
                            for layer in list(map_object.listLayers()):
                                if not layer.supports("DATASOURCE"):
                                    continue
                                try:
                                    if layer.dataSource.lower() == output.lower():
                                        map_object.removeLayer(layer)
                                except Exception:
                                    pass
                            arcpy.management.Delete(output)
                        expression.save(output)
                        print(f"created {label}: {Path(output).name}")
                    add_to_group(map_object, group, output)

        aprx.save()
    finally:
        arcpy.env.snapRaster = None
        arcpy.env.cellSize = None
        arcpy.env.extent = None
        arcpy.env.mask = None
        arcpy.CheckInExtension("Spatial")

    print("Complete. Lights were not processed; original input rasters were not changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
