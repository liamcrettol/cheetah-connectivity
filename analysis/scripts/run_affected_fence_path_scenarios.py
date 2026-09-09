"""Recalculate five fence-crossing links and assemble complete scenario networks."""

from pathlib import Path
import importlib
import csv
import os
import sys

import arcpy

OUTPUTS = r"C:\Users\lcrettol\Documents\Codex\2026-08-25\i-am-working-on-this-spreadsheet\outputs"
if OUTPUTS not in sys.path:
    sys.path.insert(0, OUTPUTS)

import create_reference_least_cost_paths as workflow
workflow = importlib.reload(workflow)  # ArcGIS Python persists imported modules between runs.

GDB = workflow.GDB
PAIRS = [(1, 13), (1, 17), (9, 13), (13, 17), (27, 30)]
PRIMARY = os.path.join(GDB, "least_cost_paths_primary_combined_unfenced")
SUMMARY = Path(r"C:\cheetah\reports\fence_path_scenario_comparison.csv")

SCENARIOS = [
    ("fence_main", "resistance_primary_fence_main_combined"),
    ("fence_nearbarrier", "resistance_primary_fence_nearbarrier_combined"),
    ("kruger_documented", "resistance_primary_kruger_documented_combined"),
    ("kruger_conservative", "resistance_primary_kruger_conservative_combined"),
]


def key(a, b):
    return tuple(sorted((int(a), int(b))))


def load(path):
    result = {}
    with arcpy.da.SearchCursor(path, ["FROM_ID", "TO_ID", "PATH_KM", "COST_RAW", "STATUS", "SHAPE@"]) as rows:
        for from_id, to_id, path_km, cost, status, shape in rows:
            result[key(from_id, to_id)] = (float(path_km), None if cost is None else float(cost), status, shape)
    return result


def remove_refs(map_object, dataset):
    target = os.path.normcase(os.path.normpath(dataset))
    for layer in list(map_object.listLayers()):
        try:
            if layer.supports("DATASOURCE") and os.path.normcase(os.path.normpath(layer.dataSource)) == target:
                map_object.removeLayer(layer)
        except Exception:
            pass


def assemble_complete(map_object, group, label, partial_path):
    primary = load(PRIMARY)
    partial = load(partial_path)
    complete = os.path.join(GDB, f"least_cost_paths_{label}_complete")
    remove_refs(map_object, complete)
    if arcpy.Exists(complete):
        arcpy.management.Delete(complete)
    arcpy.management.CreateFeatureclass(GDB, Path(complete).name, "POLYLINE", template=PRIMARY, spatial_reference=arcpy.Describe(PRIMARY).spatialReference)
    with arcpy.da.InsertCursor(complete, ["SHAPE@", "FROM_ID", "TO_ID", "SCENARIO", "PATH_KM", "COST_RAW", "STATUS"]) as cursor:
        for pair in sorted(primary):
            path_km, cost, status, shape = partial.get(pair, primary[pair])
            cursor.insertRow([shape, pair[0], pair[1], label, path_km, cost, status])
    loose = map_object.addDataFromPath(complete)
    grouped = map_object.addLayerToGroup(group, loose, "BOTTOM")
    map_object.removeLayer(loose)
    if grouped:
        grouped[0].visible = False
    return complete


def main():
    if not arcpy.Exists(PRIMARY):
        raise FileNotFoundError(PRIMARY)
    workflow.PAIRS_OVERRIDE = PAIRS
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    maps = aprx.listMaps("Map")
    map_object = maps[0] if maps else aprx.activeMap
    group = workflow.get_group(map_object)
    completed = []

    for label, resistance_name in SCENARIOS:
        partial = os.path.join(GDB, f"least_cost_paths_{label}_affected")
        workflow.SCENARIO_LABEL = label
        workflow.RESISTANCE = os.path.join(GDB, resistance_name)
        workflow.OUTPUT = partial
        workflow.REPORT = Path(r"C:\cheetah\reports") / f"least_cost_paths_{label}_affected.csv"
        print(f"running {label} for {len(PAIRS)} affected pairs")
        workflow.main()
        completed.append((label, assemble_complete(map_object, group, label, partial)))

    primary = load(PRIMARY)
    rows = []
    for label, complete in completed:
        scenario = load(complete)
        for pair in sorted(primary):
            p_km, p_cost, _, p_shape = primary[pair]
            s_km, s_cost, _, s_shape = scenario[pair]
            overlap = 100.0 * s_shape.intersect(p_shape.buffer(5000), 2).length / s_shape.length
            cost_change = "" if p_cost in (None, 0) or s_cost is None else 100.0 * (s_cost - p_cost) / p_cost
            changed = pair in {key(*x) for x in PAIRS}
            rows.append([label, pair[0], pair[1], int(changed), overlap, s_km - p_km, cost_change])

    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    with SUMMARY.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["scenario", "from_core", "to_core", "recalculated", "scenario_path_within_5km_of_primary_percent", "path_length_change_km", "cost_change_percent"])
        writer.writerows(rows)
    aprx.save()
    print(f"complete scenario networks: {len(completed)}")
    print(f"summary: {SUMMARY}")
    print("Complete. Forty unaffected paths per scenario were carried forward unchanged; existing datasets were preserved.")


if __name__ == "__main__":
    main()
