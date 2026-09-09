"""Compare superseded and revised unfenced least-cost paths without editing GIS data."""

from pathlib import Path
import csv
import os

import arcpy

GDB = r"C:\cheetah\gdb\cheetah_working.gdb"
OLD = os.path.join(GDB, "least_cost_paths_reference_unfenced")
NEW = os.path.join(GDB, "least_cost_paths_primary_combined_unfenced")
REPORT = Path(r"C:\cheetah\reports\reference_path_model_revision_comparison.csv")
BUFFER_METERS = 5000.0


def load(path):
    result = {}
    with arcpy.da.SearchCursor(path, ["FROM_ID", "TO_ID", "PATH_KM", "COST_RAW", "SHAPE@"]) as rows:
        for from_id, to_id, length_km, cost_raw, geometry in rows:
            key = tuple(sorted((int(from_id), int(to_id))))
            result[key] = {
                "length": float(length_km),
                "cost": None if cost_raw is None else float(cost_raw),
                "geometry": geometry,
            }
    return result


def percent_change(old, new):
    if old is None or new is None or old == 0:
        return None
    return 100.0 * (new - old) / old


def main():
    for path in (OLD, NEW):
        if not arcpy.Exists(path):
            raise FileNotFoundError(path)
    old_paths = load(OLD)
    new_paths = load(NEW)
    keys = sorted(set(old_paths) & set(new_paths))
    if len(keys) != 45:
        raise RuntimeError(f"Expected 45 matched core pairs; found {len(keys)}")

    output_rows = []
    for key in keys:
        old = old_paths[key]
        new = new_paths[key]
        old_buffer = old["geometry"].buffer(BUFFER_METERS)
        new_inside_old = new["geometry"].intersect(old_buffer, 2).length
        overlap_percent = 100.0 * new_inside_old / new["geometry"].length if new["geometry"].length else 0.0
        length_change = percent_change(old["length"], new["length"])
        cost_change = percent_change(old["cost"], new["cost"])
        flags = []
        if overlap_percent < 80.0:
            flags.append("ROUTE_SHIFT")
        if length_change is not None and abs(length_change) >= 20.0:
            flags.append("LENGTH_CHANGE")
        if cost_change is not None and abs(cost_change) >= 20.0:
            flags.append("COST_CHANGE")
        output_rows.append([
            key[0], key[1], old["length"], new["length"], length_change,
            old["cost"], new["cost"], cost_change, overlap_percent,
            "; ".join(flags) if flags else "STABLE",
        ])

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    with REPORT.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "from_core", "to_core", "old_path_km", "combined_path_km",
            "path_length_change_percent", "old_cost_raw", "combined_cost_raw",
            "cost_change_percent", "combined_path_within_5km_of_old_percent", "classification",
        ])
        writer.writerows(output_rows)

    shifted = [row for row in output_rows if "ROUTE_SHIFT" in row[-1]]
    stable = [row for row in output_rows if row[-1] == "STABLE"]
    print(f"matched paths: {len(output_rows)}")
    print(f"stable without review flags: {len(stable)}")
    print(f"routes with less than 80% inside the old 5 km corridor: {len(shifted)}")
    for row in shifted:
        print(f"core {row[0]} -> {row[1]}: {row[8]:.1f}% within 5 km; {row[-1]}")
    print(f"report: {REPORT}")
    print("No rasters, feature classes, or map layers were changed.")


if __name__ == "__main__":
    main()
