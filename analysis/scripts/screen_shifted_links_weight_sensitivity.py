"""Run two alternative weighting models for the seven model-sensitive links."""

from pathlib import Path
import csv
import os
import sys

import arcpy

OUTPUTS = r"C:\Users\lcrettol\Documents\Codex\2026-08-25\i-am-working-on-this-spreadsheet\outputs"
if OUTPUTS not in sys.path:
    sys.path.insert(0, OUTPUTS)

import create_reference_least_cost_paths as workflow

PAIRS = [(1, 17), (27, 31), (27, 32), (27, 41), (28, 38), (43, 49), (45, 53)]
GDB = workflow.GDB
PRIMARY = os.path.join(GDB, "least_cost_paths_primary_combined_unfenced")
REPORT = Path(r"C:\cheetah\reports\shifted_link_weight_sensitivity.csv")

MODELS = [
    (
        "equal",
        os.path.join(GDB, "resistance_sensitivity_equal_unfenced"),
        os.path.join(GDB, "least_cost_paths_sensitivity_equal_shifted"),
        Path(r"C:\cheetah\reports\least_cost_paths_sensitivity_equal_shifted.csv"),
    ),
    (
        "infrastructure",
        os.path.join(GDB, "resistance_sensitivity_infrastructure_unfenced"),
        os.path.join(GDB, "least_cost_paths_sensitivity_infrastructure_shifted"),
        Path(r"C:\cheetah\reports\least_cost_paths_sensitivity_infrastructure_shifted.csv"),
    ),
]


def load_geometry(path):
    found = {}
    with arcpy.da.SearchCursor(path, ["FROM_ID", "TO_ID", "PATH_KM", "COST_RAW", "SHAPE@"]) as rows:
        for from_id, to_id, path_km, cost, shape in rows:
            key = tuple(sorted((int(from_id), int(to_id))))
            if key in {tuple(sorted(x)) for x in PAIRS}:
                found[key] = (float(path_km), None if cost is None else float(cost), shape)
    return found


def main():
    if not arcpy.Exists(PRIMARY):
        raise FileNotFoundError(PRIMARY)
    workflow.PAIRS_OVERRIDE = PAIRS
    for label, resistance, output, report in MODELS:
        print(f"running {label} weighting for {len(PAIRS)} shifted links")
        workflow.SCENARIO_LABEL = f"sensitivity_{label}"
        workflow.RESISTANCE = resistance
        workflow.OUTPUT = output
        workflow.REPORT = report
        workflow.main()

    primary = load_geometry(PRIMARY)
    summary = []
    for label, resistance, output, report in MODELS:
        alternative = load_geometry(output)
        for pair in sorted(primary):
            if pair not in alternative:
                summary.append([label, pair[0], pair[1], "", "", "", "MISSING"])
                continue
            primary_km, primary_cost, primary_shape = primary[pair]
            alt_km, alt_cost, alt_shape = alternative[pair]
            overlap = 100.0 * alt_shape.intersect(primary_shape.buffer(5000), 2).length / alt_shape.length
            length_change = 100.0 * (alt_km - primary_km) / primary_km
            cost_change = "" if primary_cost in (None, 0) or alt_cost is None else 100.0 * (alt_cost - primary_cost) / primary_cost
            classification = "ROBUST" if overlap >= 80 else "WEIGHT_SENSITIVE"
            summary.append([label, pair[0], pair[1], overlap, length_change, cost_change, classification])

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    with REPORT.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["weight_model", "from_core", "to_core", "alternative_within_5km_of_primary_percent", "path_length_change_percent", "cost_change_percent", "classification"])
        writer.writerows(summary)
    sensitive = [row for row in summary if row[-1] == "WEIGHT_SENSITIVE"]
    print(f"comparisons: {len(summary)}")
    print(f"weight-sensitive comparisons: {len(sensitive)}")
    for row in sensitive:
        print(f"{row[0]} core {row[1]} -> {row[2]}: {row[3]:.1f}% within 5 km of primary")
    print(f"summary: {REPORT}")
    print("Complete. Existing resistance surfaces and paths were unchanged.")


if __name__ == "__main__":
    main()
