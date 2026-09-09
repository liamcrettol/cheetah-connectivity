"""Compare all completed weighting-sensitivity paths with the primary model."""

from pathlib import Path
import csv
import os

import arcpy

GDB = r"C:\cheetah\gdb\cheetah_working.gdb"
PRIMARY = os.path.join(GDB, "least_cost_paths_primary_combined_unfenced")
ALTERNATIVES = {
    "equal": os.path.join(GDB, "least_cost_paths_sensitivity_equal_shifted"),
    "infrastructure": os.path.join(GDB, "least_cost_paths_sensitivity_infrastructure_shifted"),
}
REPORT = Path(r"C:\cheetah\reports\full_weight_sensitivity_summary.csv")


def load(path):
    result = {}
    with arcpy.da.SearchCursor(path, ["FROM_ID", "TO_ID", "PATH_KM", "COST_RAW", "SHAPE@"]) as rows:
        for from_id, to_id, length_km, cost, shape in rows:
            result[tuple(sorted((int(from_id), int(to_id))))] = (
                float(length_km), None if cost is None else float(cost), shape
            )
    return result


def change(old, new):
    return "" if old in (None, 0) or new is None else 100.0 * (new - old) / old


def main():
    for dataset in (PRIMARY, *ALTERNATIVES.values()):
        if not arcpy.Exists(dataset):
            raise FileNotFoundError(dataset)
    primary = load(PRIMARY)
    if len(primary) != 45:
        raise RuntimeError(f"Expected 45 primary paths; found {len(primary)}")

    summary = []
    for model, path in ALTERNATIVES.items():
        alternative = load(path)
        if len(alternative) != 45:
            raise RuntimeError(f"Expected 45 {model} paths; found {len(alternative)}")
        for pair in sorted(primary):
            primary_km, primary_cost, primary_shape = primary[pair]
            alt_km, alt_cost, alt_shape = alternative[pair]
            overlap = 100.0 * alt_shape.intersect(primary_shape.buffer(5000), 2).length / alt_shape.length
            classification = "ROBUST" if overlap >= 80.0 else "WEIGHT_SENSITIVE"
            summary.append([
                model, pair[0], pair[1], overlap, change(primary_km, alt_km),
                change(primary_cost, alt_cost), classification,
            ])

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    with REPORT.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "weight_model", "from_core", "to_core",
            "alternative_within_5km_of_primary_percent", "path_length_change_percent",
            "cost_change_percent", "classification",
        ])
        writer.writerows(summary)

    sensitive = [row for row in summary if row[-1] == "WEIGHT_SENSITIVE"]
    sensitive_pairs = sorted({(row[1], row[2]) for row in sensitive})
    robust_pairs = 45 - len(sensitive_pairs)
    print(f"comparisons: {len(summary)}")
    print(f"core pairs robust under both alternative weight sets: {robust_pairs}")
    print(f"core pairs sensitive under at least one alternative: {len(sensitive_pairs)}")
    for pair in sensitive_pairs:
        details = [row for row in sensitive if (row[1], row[2]) == pair]
        text = ", ".join(f"{row[0]}={row[3]:.1f}%" for row in details)
        print(f"core {pair[0]} -> {pair[1]}: {text} within 5 km of primary")
    print(f"report: {REPORT}")
    print("No rasters, feature classes, or map layers were changed.")


if __name__ == "__main__":
    main()
