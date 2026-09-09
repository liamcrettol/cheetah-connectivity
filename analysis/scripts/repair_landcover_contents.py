"""Repair only the duplicated six-class land-cover map references."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import arcpy


PROJECT_GROUP = "Cheetah project"
SOURCE_GROUP = "05 Land cover · MCD12Q1"
OLD_GROUP = "05 Land cover · six-class context"
NEW_GROUP = "06 Land cover · six-class context"
BACKUP_FOLDER = Path(r"C:\cheetah\backups")


def exact_group(map_object, long_name: str):
    matches = [
        layer for layer in map_object.listLayers()
        if layer.isGroupLayer and layer.longName == long_name
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one group named {long_name!r}; found {len(matches)}.")
    return matches[0]


def direct_children(map_object, parent_long_name: str):
    prefix = parent_long_name + "\\"
    return [
        layer for layer in map_object.listLayers()
        if layer.longName.startswith(prefix)
        and layer.longName.count("\\") == parent_long_name.count("\\") + 1
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--map-name", default="Map")
    args = parser.parse_args()

    aprx = arcpy.mp.ArcGISProject("CURRENT")
    maps = aprx.listMaps(args.map_name)
    map_object = maps[0] if maps else aprx.activeMap
    if map_object is None:
        raise RuntimeError("No active map was found.")

    project_group = exact_group(map_object, PROJECT_GROUP)
    source_group = exact_group(map_object, PROJECT_GROUP + "\\" + SOURCE_GROUP)
    expected_names = {f"lc6_{year}_1km" for year in (2012, 2016, 2020, 2024)}
    nested_name = PROJECT_GROUP + "\\" + NEW_GROUP
    nested_matches = [
        layer for layer in map_object.listLayers()
        if layer.isGroupLayer and layer.longName == nested_name
    ]
    if len(nested_matches) > 1:
        raise RuntimeError(f"More than one nested {NEW_GROUP!r} group was found; no changes made.")

    BACKUP_FOLDER.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_FOLDER / f"{Path(aprx.filePath).stem}_before_contents_repair_{stamp}.aprx"
    aprx.saveACopy(str(backup_path))
    print(f"backup: {backup_path}")

    if nested_matches:
        # A prior interrupted run already created this group. Reuse it rather
        # than creating a second copy.
        new_group = nested_matches[0]
        print(f"reusing existing nested group: {nested_name}")
    else:
        old_group = exact_group(map_object, OLD_GROUP)
        old_children = direct_children(map_object, OLD_GROUP)
        if {layer.name for layer in old_children} != expected_names:
            raise RuntimeError("The existing six-class group does not contain exactly the four expected layers.")
        new_group = map_object.createGroupLayer(NEW_GROUP, project_group)
        for layer in old_children:
            map_object.addLayerToGroup(new_group, layer, "BOTTOM")

    if {layer.name for layer in direct_children(map_object, nested_name)} != expected_names:
        raise RuntimeError("The nested six-class group does not contain exactly the four expected layers.")

    # Remove only root-level duplicate references to the four lc6 output rasters.
    roots = [layer for layer in map_object.listLayers() if layer.longName == layer.name]
    for layer in roots:
        layer_name = layer.name  # ArcPy invalidates this object after removal.
        if layer_name in expected_names:
            map_object.removeLayer(layer)
            print(f"removed loose duplicate: {layer_name}")

    # The old root-level group now contains only duplicate references.
    for layer in list(map_object.listLayers()):
        if layer.isGroupLayer and layer.longName == OLD_GROUP:
            map_object.removeLayer(layer)
            print(f"removed old root group: {OLD_GROUP}")
    map_object.moveLayer(source_group, new_group, "AFTER")
    aprx.save()

    final_layers = map_object.listLayers()
    loose = [layer.name for layer in final_layers if layer.longName == layer.name and layer.name in expected_names]
    final_children = direct_children(map_object, PROJECT_GROUP + "\\" + NEW_GROUP)
    if loose or {layer.name for layer in final_children} != expected_names:
        raise RuntimeError("Repair saved, but post-check did not match the expected Contents layout.")

    print(f"created group: {PROJECT_GROUP}\\{NEW_GROUP}")
    print("Contents repair complete. No raster data were changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
