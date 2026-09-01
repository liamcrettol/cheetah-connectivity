"""Safely tidy the Cheetah project's ArcGIS Pro Contents pane.

This changes map-layer organization and visibility only. It never deletes GIS
datasets. Root-level layer references are removed only when the same data source
already exists inside Cheetah project.
"""

from datetime import datetime
from pathlib import Path
import json
import os

import arcpy


MAP_NAME = "Map"
PARENT_NAME = "Cheetah project"
BACKUP_FOLDER = Path(r"C:\cheetah\backups")
REPORT_PATH = Path(r"C:\cheetah\reports\contents_cleanup.json")

# Existing names are preserved so earlier workflow scripts continue to work.
ORDER = [
    "01 Project framework",
    "02 Baseline evidence",
    "03 Built-up · GHSL",
    "04 Nighttime lights · VIIRS",
    "08 Nighttime lights · flare mask",
    "08 Nighttime lights · flare mask source",
    "08 Nighttime lights · flare-masked",
    "05 Land cover · MCD12Q1",
    "06 Land cover · six-class context",
    "06 Vegetation · tree cover",
    "07 Vegetation · non-tree",
    "08 Vegetation · bare",
    "08 Continuous change · absolute",
    "08 Continuous change · proportional",
    "09 Roads · GRIP4",
    "09 Hydrology · HydroSHEDS",
    "09 Terrain · SRTM",
    "10 Livestock exposure · GLW4 2020",
    "11 Veterinary fences · reference",
    "11 Veterinary fences · scenarios",
    "12 Resistance components · standardized",
    "13 Resistance surfaces · scenarios",
    "99 Other",
]


def safe_name(layer):
    try:
        return layer.name
    except Exception:
        return "<unsupported layer>"


def safe_source(layer):
    try:
        if layer.supports("DATASOURCE"):
            return os.path.normcase(os.path.normpath(layer.dataSource))
    except Exception:
        pass
    return ""


def direct_children(map_object, parent):
    prefix = parent.longName + "\\"
    depth = parent.longName.count("\\") + 1
    result = []
    for layer in map_object.listLayers():
        try:
            if layer.longName.startswith(prefix) and layer.longName.count("\\") == depth:
                result.append(layer)
        except Exception:
            continue
    return result


def set_collapsed(layer):
    # Supported in current ArcGIS Pro CIM; failure is harmless on other builds.
    try:
        cim = layer.getDefinition("V3")
        if hasattr(cim, "expanded"):
            cim.expanded = False
            layer.setDefinition(cim)
    except Exception:
        pass


def destination_for(name):
    """Return the existing workflow group for newer root-level outputs."""
    text = name.lower()
    if text.startswith("livestock_"):
        return "10 Livestock exposure · GLW4 2020"
    if text.startswith(("dem_srtm_", "slope_mean_", "slope_max_", "terrain_resistance_")):
        return "09 Terrain · SRTM"
    if text.startswith(("roads_grip4", "roaddens_", "dist_road_")):
        return "09 Roads · GRIP4"
    if text.startswith(("hydrorivers", "hydrolakes", "water_", "dist_water_")):
        return "09 Hydrology · HydroSHEDS"
    if text.startswith("p_"):
        return "08 Continuous change · proportional"
    if text.startswith("d_"):
        return "08 Continuous change · absolute"
    if text.startswith("lights_") and "flaremasked" in text:
        return "08 Nighttime lights · flare-masked"
    if text.startswith(("fence_presence_", "fence_multiplier_")):
        return "11 Veterinary fences · scenarios"
    if text.startswith(("pressure_built_", "pressure_lights_", "pressure_roads_", "pressure_livestock_", "pressure_human_")):
        return "12 Resistance components · standardized"
    if text.startswith(("resistance_base_", "resistance_scenario_")):
        return "13 Resistance surfaces · scenarios"
    if text.startswith("built_") and "aligned" in text:
        return "03 Built-up · GHSL"
    if text.startswith("vcf_tree_") and "aligned" in text:
        return "06 Vegetation · tree cover"
    if text.startswith("vcf_nontree_") and "aligned" in text:
        return "07 Vegetation · non-tree"
    if text.startswith("vcf_bare_") and "aligned" in text:
        return "08 Vegetation · bare"
    return None


def main():
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    maps = aprx.listMaps(MAP_NAME)
    map_object = maps[0] if maps else aprx.activeMap
    if map_object is None:
        raise RuntimeError("No active map was found.")

    parents = [
        layer for layer in map_object.listLayers()
        if layer.isGroupLayer and layer.longName == PARENT_NAME
    ]
    if len(parents) != 1:
        raise RuntimeError(f"Expected one root group {PARENT_NAME!r}; found {len(parents)}.")
    parent = parents[0]

    BACKUP_FOLDER.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUP_FOLDER / f"{Path(aprx.filePath).stem}_before_contents_tidy_{stamp}.aprx"
    aprx.saveACopy(str(backup))
    print(f"backup: {backup}")

    # Move newer outputs that were added at map root into their intended
    # workflow groups. addLayerToGroup creates the nested reference; removing
    # the original reference does not delete or alter the underlying dataset.
    groups_by_name = {}
    for layer in direct_children(map_object, parent):
        try:
            if layer.isGroupLayer:
                groups_by_name.setdefault(layer.name, layer)
        except Exception:
            continue
    moved = []
    # Reparent known workflow groups that are still loose at map root.
    for layer in list(map_object.listLayers()):
        try:
            if layer.isGroupLayer and layer.longName == layer.name and layer.name in ORDER:
                name = layer.name
                map_object.addLayerToGroup(parent, layer, "BOTTOM")
                map_object.removeLayer(layer)
                moved.append({"layer": name, "destination": PARENT_NAME})
                print(f"moved group into {PARENT_NAME}: {name}")
        except Exception:
            continue

    # Refresh group references after moving loose groups.
    groups_by_name = {}
    for layer in direct_children(map_object, parent):
        try:
            if layer.isGroupLayer:
                groups_by_name.setdefault(layer.name, layer)
        except Exception:
            continue

    for layer in list(map_object.listLayers()):
        try:
            is_root = layer.longName == layer.name
            is_group = layer.isGroupLayer
            name = layer.name
        except Exception:
            continue
        destination = destination_for(name) if is_root and not is_group else None
        if destination and destination in groups_by_name:
            map_object.addLayerToGroup(groups_by_name[destination], layer, "BOTTOM")
            map_object.removeLayer(layer)
            moved.append({"layer": name, "destination": destination})
            print(f"moved into {destination}: {name}")

    # Remove only loose references whose exact source is already represented
    # beneath the project group. Values needed after removal are saved first.
    nested_sources = {
        safe_source(layer) for layer in map_object.listLayers()
        if "\\" in getattr(layer, "longName", "") and safe_source(layer)
    }
    removed = []
    for layer in list(map_object.listLayers()):
        try:
            is_root = layer.longName == layer.name
            is_group = layer.isGroupLayer
        except Exception:
            continue
        source = safe_source(layer)
        if is_root and not is_group and source and source in nested_sources:
            name = safe_name(layer)
            map_object.removeLayer(layer)
            removed.append(name)
            print(f"removed loose duplicate reference: {name}")

    # Remove repeated references to the same dataset within the same group.
    # Only map references are removed; the underlying datasets remain intact.
    nested_duplicates = []
    for candidate_group in [x for x in map_object.listLayers() if getattr(x, "isGroupLayer", False)]:
        seen = set()
        for layer in list(direct_children(map_object, candidate_group)):
            try:
                if layer.isGroupLayer:
                    continue
            except Exception:
                continue
            source = safe_source(layer)
            if not source:
                continue
            if source in seen:
                name = safe_name(layer)
                map_object.removeLayer(layer)
                nested_duplicates.append({"layer": name, "group": safe_name(candidate_group)})
                print(f"removed duplicate reference from {safe_name(candidate_group)}: {name}")
            else:
                seen.add(source)

    children = direct_children(map_object, parent)
    groups_by_name = {}
    for layer in children:
        try:
            if layer.isGroupLayer:
                groups_by_name.setdefault(layer.name, layer)
        except Exception:
            continue
    ordered = [groups_by_name[name] for name in ORDER if name in groups_by_name]

    # Put the known workflow groups into one contiguous, predictable sequence.
    if ordered:
        current_children = direct_children(map_object, parent)
        if current_children and current_children[0] is not ordered[0]:
            map_object.moveLayer(current_children[0], ordered[0], "BEFORE")
        previous = ordered[0]
        for group in ordered[1:]:
            map_object.moveLayer(previous, group, "AFTER")
            previous = group

    # Default working view after model assembly: show only final scenarios and
    # the basemap/other section. Individual scenarios start off except base.
    for group in ordered:
        group.visible = group.name in {"13 Resistance surfaces · scenarios", "99 Other"}
        set_collapsed(group)
        if group.name == "13 Resistance surfaces · scenarios":
            for layer in direct_children(map_object, group):
                try:
                    layer.visible = layer.name == "resistance_base_unfenced_1_10"
                except Exception:
                    pass
    parent.visible = True
    set_collapsed(parent)
    aprx.save()

    final_order = [safe_name(layer) for layer in direct_children(map_object, parent)]
    report = {
        "completed_at": datetime.now().isoformat(timespec="seconds"),
        "backup": str(backup),
        "moved_root_layers": moved,
        "removed_duplicate_references": removed,
        "removed_nested_duplicate_references": nested_duplicates,
        "final_direct_child_order": final_order,
        "datasets_deleted": 0,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"organized groups: {len(ordered)}")
    print(f"new root layers moved into groups: {len(moved)}")
    print(f"loose duplicate references removed: {len(removed)}")
    print(f"nested duplicate references removed: {len(nested_duplicates)}")
    print(f"report: {REPORT_PATH}")
    print("Complete. No GIS datasets were deleted or altered.")


if __name__ == "__main__":
    main()
