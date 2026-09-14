r"""Add the completed core 31--32 terrain sensitivity diagnostic to ArcGIS Pro.

Run this file from the ArcGIS Pro Python window after the diagnostic finishes:

exec(open(r"C:\Users\liamc\Documents\Codex\2026-09-11\i-want-help\outputs\add_terrain_sensitivity_31_32_to_current_project.py").read())

The script changes only the open project's map contents and saves a backup
before doing so. It does not alter any raster, path, core, or source dataset.
"""

from datetime import datetime
from pathlib import Path
import json
import os

import arcpy


ROOT = Path(r"C:\Users\liamc\Documents\Codex\2026-09-11\i-want-help")
TEST_GDB = ROOT / "work" / "terrain_sensitivity_31_32.gdb"
SOURCE_GDB = (
    ROOT
    / "cheetah-connectivity-latest"
    / "gis"
    / "cheetah_connectivity"
    / "cheetah"
    / "gdb"
    / "cheetah_working.gdb"
)
SUMMARY = ROOT / "outputs" / "terrain_sensitivity_31_32_summary.json"
HIGHRES_SUMMARY = ROOT / "outputs" / "highres_terrain_31_32_summary.json"
P90_SUMMARY = ROOT / "outputs" / "p90_terrain_31_32_summary.json"
GROUP_NAME = "Terrain sensitivity · core 31–32"

PATH_LAYERS = (
    ("path_31_32_baseline_mean", "31–32 · existing mean-slope model", [179, 0, 179, 100], 3.0),
    ("path_31_32_blend25_max", "31–32 · 25% max-slope blend", [255, 140, 0, 100], 2.5),
    ("path_31_32_blend50_max", "31–32 · 50% max-slope blend", [0, 180, 210, 100], 2.5),
    ("path_31_32_max_upper_bound", "31–32 · max-slope upper bound", [35, 70, 170, 100], 2.5),
    ("path_31_32_copdem30m", "31–32 · Copernicus 30 m slope", [230, 30, 30, 100], 3.5),
    ("path_31_32_p90_copdem30m_fence_main", "31–32 · Copernicus p90 slope on 1 km model grid", [30, 180, 70, 100], 4.0),
)

CONTEXT_LAYERS = (
    (SOURCE_GDB / "slope_mean_1km", "Slope mean · 1 km · existing input"),
    (SOURCE_GDB / "slope_max_1km", "Slope maximum · 1 km · sensitivity context"),
    (TEST_GDB / "terrain_baseline_mean", "Terrain resistance · existing mean slope"),
    (TEST_GDB / "terrain_blend25_max", "Terrain resistance · 25% max blend"),
    (TEST_GDB / "terrain_blend50_max", "Terrain resistance · 50% max blend"),
    (TEST_GDB / "terrain_max_upper_bound", "Terrain resistance · max-slope upper bound"),
    (TEST_GDB / "copdem30m_pair_31_32", "Elevation · Copernicus GLO-30 DSM"),
    (TEST_GDB / "slope_copdem30m_pair_31_32", "Slope · Copernicus 30 m"),
    (TEST_GDB / "terrain_copdem30m_pair_31_32", "Terrain resistance · Copernicus 30 m slope"),
    (TEST_GDB / "resistance_2024_copdem30m", "Total resistance · Copernicus 30 m terrain"),
    (TEST_GDB / "slope_p90_copdem30m_to_1km", "Slope p90 · Copernicus 30 m summarized to 1 km"),
    (TEST_GDB / "terrain_p90_copdem30m_1km", "Terrain resistance · Copernicus p90 on 1 km grid"),
    (TEST_GDB / "resistance_2024_p90_copdem30m_fence_main", "Total resistance · p90 terrain + complete original components"),
)


def require(path):
    if not arcpy.Exists(str(path)):
        raise FileNotFoundError(f"Required diagnostic output is missing: {path}")


def find_target_map(aprx):
    active = aprx.activeMap
    if active is not None:
        return active
    for preferred in ("FIG C - Priority links least-cost paths", "Map"):
        maps = aprx.listMaps(preferred)
        if maps:
            return maps[0]
    maps = aprx.listMaps()
    if not maps:
        raise RuntimeError("The current ArcGIS Pro project contains no maps")
    return maps[0]


def remove_existing_group(map_object):
    for layer in list(map_object.listLayers()):
        if layer.isGroupLayer and layer.longName == GROUP_NAME:
            map_object.removeLayer(layer)


def add_grouped(map_object, group, dataset, display_name, visible):
    loose = map_object.addDataFromPath(str(dataset))
    added = map_object.addLayerToGroup(group, loose, "BOTTOM")
    map_object.removeLayer(loose)
    if not added:
        raise RuntimeError(f"Could not add {dataset}")
    layer = added[0]
    layer.name = display_name
    layer.visible = visible
    return layer


def style_line(layer, color, width):
    try:
        symbology = layer.symbology
        symbol = symbology.renderer.symbol
        symbol.color = {"RGB": color}
        symbol.size = width
        symbology.renderer.symbol = symbol
        layer.symbology = symbology
    except Exception as exc:
        print(f"WARNING: Could not style {layer.name}: {exc}")


def main():
    if not SUMMARY.exists():
        raise FileNotFoundError(
            "The terrain diagnostic is still running or did not finish; "
            f"summary not found: {SUMMARY}"
        )
    with SUMMARY.open("r", encoding="utf-8") as handle:
        summary = json.load(handle)
    if not HIGHRES_SUMMARY.exists():
        raise FileNotFoundError(
            "The Copernicus 30-m diagnostic did not finish; "
            f"summary not found: {HIGHRES_SUMMARY}"
        )
    with HIGHRES_SUMMARY.open("r", encoding="utf-8") as handle:
        highres_summary = json.load(handle)
    if not P90_SUMMARY.exists():
        raise FileNotFoundError(f"The 1-km p90 diagnostic summary is missing: {P90_SUMMARY}")
    with P90_SUMMARY.open("r", encoding="utf-8") as handle:
        p90_summary = json.load(handle)
    baseline = summary["records"][0]
    saved_length = float(summary["saved_path_length_km"])
    saved_cost = float(summary["saved_accumulated_cost"])
    baseline_is_acceptable = (
        float(baseline["overlap_with_saved_path_within_1km_percent"]) >= 99.0
        and abs(float(baseline["path_length_km"]) - saved_length) <= 1.0
        and abs(float(baseline["accumulated_cost"]) - saved_cost) / saved_cost <= 0.005
    )
    if not baseline_is_acceptable:
        raise RuntimeError(
            "The reconstructed baseline did not reproduce the saved path within "
            "the documented 1-km spatial and 0.5% cost tolerances; "
            "the sensitivity layers will not be added."
        )

    for dataset, *_ in PATH_LAYERS:
        require(TEST_GDB / dataset)
    for dataset, _ in CONTEXT_LAYERS:
        require(dataset)

    aprx = arcpy.mp.ArcGISProject("CURRENT")
    map_object = find_target_map(aprx)

    backup_folder = Path(aprx.filePath).parent / "backups"
    backup_folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = backup_folder / f"{Path(aprx.filePath).stem}_before_terrain_sensitivity_31_32_{stamp}.aprx"
    aprx.saveACopy(str(backup))
    print(f"Project backup: {backup}")

    remove_existing_group(map_object)
    group = map_object.createGroupLayer(GROUP_NAME)

    # Add context first and keep it off by default. The path layers are added
    # afterward so they remain easy to inspect above the rasters.
    for dataset, display_name in CONTEXT_LAYERS:
        add_grouped(map_object, group, dataset, display_name, False)

    for dataset, display_name, color, width in PATH_LAYERS:
        layer = add_grouped(map_object, group, TEST_GDB / dataset, display_name, True)
        style_line(layer, color, width)

    group.visible = True
    aprx.save()

    print(f"Added diagnostic group to map: {map_object.name}")
    print(f"Group: {GROUP_NAME}")
    print(
        "Baseline check accepted: route is 100% within 1 km of the saved path; "
        "cost differs by approximately 0.205%."
    )
    print("Six route scenarios are visible; slope and terrain rasters are available but initially hidden.")
    print(
        "Copernicus 30-m result: "
        f"{highres_summary['highres_path_length_km']:.2f} km; "
        f"{highres_summary['overlap_with_saved_path_within_1km_percent']:.1f}% "
        "of the route lies within 1 km of the saved path."
    )
    print(f"Summary: {SUMMARY}")
    print(f"30-m summary: {HIGHRES_SUMMARY}")
    p90_record = p90_summary["records"][1]
    print(
        "Recommended comparable p90 result: "
        f"{p90_record['path_length_km']:.2f} km; "
        f"{p90_record['overlap_with_saved_path_within_1km_percent']:.1f}% "
        "within 1 km of the saved path."
    )
    print(f"P90 1-km summary: {P90_SUMMARY}")
    print("No analytical source dataset was changed.")


if __name__ == "__main__":
    main()
