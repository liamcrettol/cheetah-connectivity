"""Set the selected 5 km road density and create distance-to-road rasters."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import arcpy
from arcpy.sa import EucDistance


GDB = Path(r"C:\cheetah\gdb\cheetah_working.gdb")
SELECTED_DENSITY = str(GDB / "roaddens_5km_1km")
MAJOR_ROADS = str(GDB / "roads_grip4_major")
MINOR_ROADS = str(GDB / "roads_grip4_minor")
SNAP_RASTER = r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah_connectivity.gdb\snapgrid_1km"
EXTENT_MASK = r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah_connectivity.gdb\extent_buffered"
BACKUP_FOLDER = Path(r"C:\cheetah\backups")
PROJECT_GROUP = "Cheetah project"
GROUP_NAME = "09 Roads · GRIP4"
OUTPUTS = (
    ("roaddens_1km", "density"),
    ("dist_road_major_1km", "major"),
    ("dist_road_minor_1km", "minor"),
)


def remove_map_references(map_object, dataset):
    for layer in list(map_object.listLayers()):
        if not layer.supports("DATASOURCE"):
            continue
        try:
            if layer.dataSource.lower() == dataset.lower():
                map_object.removeLayer(layer)
        except Exception:
            pass


def replace_dataset(map_object, dataset):
    remove_map_references(map_object, dataset)
    if arcpy.Exists(dataset):
        arcpy.management.Delete(dataset)


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
    for path in (SELECTED_DENSITY, MAJOR_ROADS, MINOR_ROADS, SNAP_RASTER, EXTENT_MASK):
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
    backup = BACKUP_FOLDER / f"{Path(aprx.filePath).stem}_before_road_distance_{stamp}.aprx"
    aprx.saveACopy(str(backup))
    print(f"backup: {backup}")

    old_add_outputs = arcpy.env.addOutputsToMap
    arcpy.env.addOutputsToMap = False
    try:
        arcpy.env.snapRaster = SNAP_RASTER
        arcpy.env.cellSize = SNAP_RASTER
        arcpy.env.extent = EXTENT_MASK
        arcpy.env.mask = EXTENT_MASK

        density_output = str(GDB / "roaddens_1km")
        replace_dataset(map_object, density_output)
        arcpy.management.CopyRaster(SELECTED_DENSITY, density_output)
        add_to_group(map_object, group, density_output)
        print("selected 5 km density: roaddens_1km")

        for source, name in ((MAJOR_ROADS, "dist_road_major_1km"), (MINOR_ROADS, "dist_road_minor_1km")):
            output = str(GDB / name)
            replace_dataset(map_object, output)
            EucDistance(source, cell_size=SNAP_RASTER).save(output)
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
    print("Complete. The 5 km density is the selected default; source roads and the 10 km option were retained.")


if __name__ == "__main__":
    main()
