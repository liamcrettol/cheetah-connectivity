"""Create major and minor GRIP4 road layers without changing the clipped source."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import arcpy


GDB = Path(r"C:\cheetah\gdb\cheetah_working.gdb")
ROADS = str(GDB / "roads_grip4")
MAJOR = str(GDB / "roads_grip4_major")
MINOR = str(GDB / "roads_grip4_minor")
BACKUP_FOLDER = Path(r"C:\cheetah\backups")
PROJECT_GROUP = "Cheetah project"
GROUP_NAME = "09 Roads · GRIP4"


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
    if not arcpy.Exists(ROADS):
        raise RuntimeError(f"Missing source roads layer: {ROADS}")
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    map_object = aprx.activeMap
    if map_object is None:
        raise RuntimeError("No active map was found.")
    group = find_group(map_object)
    BACKUP_FOLDER.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUP_FOLDER / f"{Path(aprx.filePath).stem}_before_road_split_{stamp}.aprx"
    aprx.saveACopy(str(backup))
    print(f"backup: {backup}")

    old_add_outputs = arcpy.env.addOutputsToMap
    arcpy.env.addOutputsToMap = False
    try:
        for output, clause, label in (
            (MAJOR, "GP_RTP IN (1, 2)", "major: highways + primary roads"),
            (MINOR, "GP_RTP IN (3, 4, 5)", "minor: secondary + tertiary + local roads"),
        ):
            replace_dataset(map_object, output)
            arcpy.conversion.ExportFeatures(ROADS, output, clause)
            print(f"created {label}: {int(arcpy.management.GetCount(output).getOutput(0)):,} features")
            add_to_group(map_object, group, output)
    finally:
        arcpy.env.addOutputsToMap = old_add_outputs
    aprx.save()
    print("Complete. The original roads_grip4 layer was unchanged.")


if __name__ == "__main__":
    main()
