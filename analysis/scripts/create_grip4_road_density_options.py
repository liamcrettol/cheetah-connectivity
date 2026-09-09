"""Create 5 km and 10 km GRIP4 road-density options on the 1 km analysis grid."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import arcpy
from arcpy.sa import KernelDensity


GDB = Path(r"C:\cheetah\gdb\cheetah_working.gdb")
ROADS = str(GDB / "roads_grip4")
SNAP_RASTER = r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah_connectivity.gdb\snapgrid_1km"
EXTENT_MASK = r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah_connectivity.gdb\extent_buffered"
BACKUP_FOLDER = Path(r"C:\cheetah\backups")
PROJECT_GROUP = "Cheetah project"
GROUP_NAME = "09 Roads · GRIP4"
OPTIONS = ((5000, "roaddens_5km_1km"), (10000, "roaddens_10km_1km"))


def remove_map_references(map_object, dataset):
    for layer in list(map_object.listLayers()):
        if not layer.supports("DATASOURCE"):
            continue
        try:
            if layer.dataSource.lower() == dataset.lower():
                map_object.removeLayer(layer)
        except Exception:
            pass


def find_group(map_object):
    wanted = PROJECT_GROUP + "\\" + GROUP_NAME
    groups = [layer for layer in map_object.listLayers() if layer.isGroupLayer and layer.longName == wanted]
    if len(groups) != 1:
        raise RuntimeError(f"Expected one group named {wanted!r}; found {len(groups)}.")
    return groups[0]


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


def main():
    for path in (ROADS, SNAP_RASTER, EXTENT_MASK):
        if not arcpy.Exists(path):
            raise RuntimeError(f"Required input is missing: {path}")
    arcpy.CheckOutExtension("Spatial")
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    map_object = aprx.activeMap
    if map_object is None:
        raise RuntimeError("No active map was found.")
    group = find_group(map_object)
    BACKUP_FOLDER.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUP_FOLDER / f"{Path(aprx.filePath).stem}_before_road_density_options_{stamp}.aprx"
    aprx.saveACopy(str(backup))
    print(f"backup: {backup}")

    old_add_outputs = arcpy.env.addOutputsToMap
    arcpy.env.addOutputsToMap = False
    try:
        arcpy.env.snapRaster = SNAP_RASTER
        arcpy.env.cellSize = SNAP_RASTER
        arcpy.env.extent = EXTENT_MASK
        arcpy.env.mask = EXTENT_MASK
        for radius_m, name in OPTIONS:
            output = str(GDB / name)
            remove_map_references(map_object, output)
            if arcpy.Exists(output):
                arcpy.management.Delete(output)
            print(f"calculating {radius_m // 1000} km road density")
            KernelDensity(
                ROADS, None, SNAP_RASTER, radius_m,
                "SQUARE_KILOMETERS", "DENSITIES", "PLANAR"
            ).save(output)
            add_to_group(map_object, group, output)
            print(f"created: {name}")
    finally:
        arcpy.env.addOutputsToMap = old_add_outputs
        arcpy.env.snapRaster = None
        arcpy.env.cellSize = None
        arcpy.env.extent = None
        arcpy.env.mask = None
        arcpy.CheckInExtension("Spatial")
    aprx.save()
    print("Complete. Both density options were created; the road inputs were unchanged.")


if __name__ == "__main__":
    main()
