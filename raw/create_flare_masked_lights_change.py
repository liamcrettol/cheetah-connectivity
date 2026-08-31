"""Create absolute change rasters from flare-masked VIIRS light copies."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import arcpy
from arcpy.sa import Raster


WORKING_GDB = Path(r"C:\cheetah\gdb\cheetah_working.gdb")
BACKUP_FOLDER = Path(r"C:\cheetah\backups")
PROJECT_GROUP = "Cheetah project"
GROUP_NAME = "08 Continuous change · absolute"
PERIODS = ((2012, 2016), (2016, 2020), (2020, 2024), (2012, 2024))
SNAP_RASTER = r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah_connectivity.gdb\snapgrid_1km"
EXTENT_MASK = r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah_connectivity.gdb\extent_buffered"


def one_group(map_object, long_name):
    matches = [layer for layer in map_object.listLayers() if layer.isGroupLayer and layer.longName == long_name]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one group named {long_name!r}; found {len(matches)}.")
    return matches[0]


def remove_map_references(map_object, dataset):
    for layer in list(map_object.listLayers()):
        if not layer.supports("DATASOURCE"):
            continue
        try:
            if layer.dataSource.lower() == dataset.lower():
                map_object.removeLayer(layer)
        except Exception:
            pass


def add_to_group(map_object, group, dataset):
    map_object.addDataFromPath(dataset)
    roots = [
        layer for layer in map_object.listLayers()
        if layer.longName == layer.name and layer.supports("DATASOURCE")
        and getattr(layer, "dataSource", "").lower() == dataset.lower()
    ]
    if len(roots) != 1:
        raise RuntimeError(f"Could not identify temporary layer for {dataset}")
    map_object.addLayerToGroup(group, roots[0], "BOTTOM")
    loose = [
        layer for layer in map_object.listLayers()
        if layer.longName == layer.name and layer.supports("DATASOURCE")
        and getattr(layer, "dataSource", "").lower() == dataset.lower()
    ]
    if len(loose) == 1:
        map_object.removeLayer(loose[0])


def main() -> int:
    arcpy.CheckOutExtension("Spatial")
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    map_object = aprx.activeMap
    if map_object is None:
        raise RuntimeError("No active map was found.")
    group = one_group(map_object, PROJECT_GROUP + "\\" + GROUP_NAME)

    sources = {
        year: str(WORKING_GDB / f"lights_{year}_1km_flaremasked")
        for year in (2012, 2016, 2020, 2024)
    }
    missing = [path for path in sources.values() if not arcpy.Exists(path)]
    if missing:
        raise RuntimeError("Missing flare-masked light raster(s): " + "; ".join(missing))
    for path in (SNAP_RASTER, EXTENT_MASK):
        if not arcpy.Exists(path):
            raise RuntimeError(f"Required input is missing: {path}")

    BACKUP_FOLDER.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUP_FOLDER / f"{Path(aprx.filePath).stem}_before_masked_lights_change_{stamp}.aprx"
    aprx.saveACopy(str(backup))
    print(f"backup: {backup}")

    old_add_outputs = arcpy.env.addOutputsToMap
    arcpy.env.addOutputsToMap = False
    try:
        for start, end in PERIODS:
            output = str(WORKING_GDB / f"d_lights_{start}_{end}_1km")
            remove_map_references(map_object, output)
            if arcpy.Exists(output):
                arcpy.management.Delete(output)
            arcpy.env.snapRaster = SNAP_RASTER
            arcpy.env.cellSize = SNAP_RASTER
            arcpy.env.extent = EXTENT_MASK
            arcpy.env.mask = EXTENT_MASK
            (Raster(sources[end]) - Raster(sources[start])).save(output)
            add_to_group(map_object, group, output)
            print(f"created: d_lights_{start}_{end}_1km")
    finally:
        arcpy.env.addOutputsToMap = old_add_outputs
        arcpy.env.snapRaster = None
        arcpy.env.cellSize = None
        arcpy.env.extent = None
        arcpy.env.mask = None
        arcpy.CheckInExtension("Spatial")

    aprx.save()
    print("Complete. Absolute change layers use flare-masked lights; originals and masked sources were unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
