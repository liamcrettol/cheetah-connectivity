"""Audit the completed unfenced-reference least-cost paths without changing GIS data."""

from pathlib import Path
import csv
import math
import os

import arcpy

GDB = r"C:\cheetah\gdb\cheetah_working.gdb"
PATHS = os.path.join(GDB, "least_cost_paths_reference_unfenced")
LINKS = os.path.join(GDB, "cheetah_core_neighbor_links")
CORES = os.path.join(GDB, "cheetah_core_primary_density051_min500")
REPORT = Path(r"C:\cheetah\reports\least_cost_paths_reference_unfenced_qc.csv")


def percentile(values, probability):
    ordered = sorted(values)
    if not ordered:
        return float("nan")
    position = (len(ordered) - 1) * probability
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def main():
    for dataset in (PATHS, LINKS, CORES):
        if not arcpy.Exists(dataset):
            raise FileNotFoundError(dataset)

    core_shapes = {}
    with arcpy.da.SearchCursor(CORES, ["CORE_ID", "SHAPE@"]) as rows:
        for core_id, geometry in rows:
            core_shapes[int(core_id)] = geometry

    centroid_distance = {}
    with arcpy.da.SearchCursor(LINKS, ["FROM_ID", "TO_ID", "DIST_KM"]) as rows:
        for from_id, to_id, distance in rows:
            key = tuple(sorted((int(from_id), int(to_id))))
            centroid_distance[key] = float(distance)

    records = []
    with arcpy.da.SearchCursor(PATHS, ["FROM_ID", "TO_ID", "PATH_KM", "COST_RAW", "STATUS"]) as rows:
        for from_id, to_id, path_km, cost_raw, status in rows:
            key = tuple(sorted((int(from_id), int(to_id))))
            if key[0] not in core_shapes or key[1] not in core_shapes:
                raise RuntimeError(f"Missing core geometry for pair {key}")
            direct_km = float(core_shapes[key[0]].distanceTo(core_shapes[key[1]]) / 1000.0)
            centroid_km = centroid_distance.get(key)
            if direct_km <= 0:
                raise RuntimeError(f"Core polygons overlap or touch for pair {key}")
            path_km = float(path_km)
            cost_raw = None if cost_raw is None else float(cost_raw)
            detour = path_km / direct_km
            cost_per_km = None if cost_raw is None or path_km <= 0 else cost_raw / path_km
            records.append({
                "from": key[0], "to": key[1], "direct": direct_km,
                "centroid": centroid_km,
                "path": path_km, "detour": detour, "cost": cost_raw,
                "cost_per_km": cost_per_km, "status": status,
            })

    if len(records) != 45:
        raise RuntimeError(f"Expected 45 reference paths; found {len(records)}")
    detours = [row["detour"] for row in records]
    costs_per_km = [row["cost_per_km"] for row in records if row["cost_per_km"] is not None]
    detour_q95 = percentile(detours, 0.95)
    cost_q95 = percentile(costs_per_km, 0.95)

    for row in records:
        flags = []
        if row["detour"] < 0.98:
            flags.append("CHECK_PATH_SHORTER_THAN_DIRECT")
        if row["detour"] >= detour_q95:
            flags.append("REVIEW_HIGH_DETOUR")
        if row["cost_per_km"] is not None and row["cost_per_km"] >= cost_q95:
            flags.append("REVIEW_HIGH_COST_PER_KM")
        row["qc"] = "; ".join(flags) if flags else "OK"

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    with REPORT.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "from_core", "to_core", "centroid_distance_km", "core_edge_distance_km", "least_cost_path_km",
            "detour_ratio", "accumulated_cost_raw", "cost_per_path_km", "qc",
        ])
        for row in sorted(records, key=lambda x: (x["from"], x["to"])):
            writer.writerow([
                row["from"], row["to"], row["centroid"], row["direct"], row["path"], row["detour"],
                "" if row["cost"] is None else row["cost"],
                "" if row["cost_per_km"] is None else row["cost_per_km"], row["qc"],
            ])

    flagged = [row for row in records if row["qc"] != "OK"]
    print(f"reference paths checked: {len(records)}")
    print(f"median detour ratio: {percentile(detours, 0.50):.3f}")
    print(f"95th-percentile detour ratio: {detour_q95:.3f}")
    print(f"QC review paths: {len(flagged)}")
    for row in flagged:
        print(f"core {row['from']} -> {row['to']}: detour {row['detour']:.3f}; {row['qc']}")
    print(f"report: {REPORT}")
    print("No rasters, feature classes, or map layers were changed.")


if __name__ == "__main__":
    main()
