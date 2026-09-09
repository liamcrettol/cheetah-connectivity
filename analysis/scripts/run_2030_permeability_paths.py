"""Run the 45 fixed core-pair links across three 2030 stress-test surfaces.

The efficient method calculates one CostDistance surface per source core and
scenario (21 x 3 = 63 solves), then extracts every destination linked to that
source. Outputs checkpoint after each source and can safely resume.
"""
from pathlib import Path
import csv
import gc
import os
import sys
import time

import arcpy
from arcpy.sa import CostDistance, CostPathAsPolyline

OUTPUTS = r"C:\Users\lcrettol\Documents\Codex\2026-08-25\i-am-working-on-this-spreadsheet\outputs"
if OUTPUTS not in sys.path:
    sys.path.insert(0, OUTPUTS)
import create_reference_least_cost_paths as base

REPORTS = Path(r"C:\cheetah\reports")
SCENARIOS = ("low_growth", "continuation", "high_development")
FIELDS = ("from_core", "to_core", "path_length_km", "accumulated_cost_raw", "status")


def pairs_from_links():
    return sorted({tuple(sorted((int(a), int(b))))
                   for a, b in arcpy.da.SearchCursor(base.LINKS, ["FROM_ID", "TO_ID"])})


def expected_for_source(pairs, source):
    return [pair for pair in pairs if pair[0] == source]


def create_output(output):
    arcpy.management.CreateFeatureclass(
        base.GDB, Path(output).name, "POLYLINE",
        spatial_reference=arcpy.Describe(base.CORES).spatialReference,
    )
    for name, kind, length in (("FROM_ID", "LONG", None), ("TO_ID", "LONG", None),
                               ("SCENARIO", "TEXT", 40), ("PATH_KM", "DOUBLE", None),
                               ("COST_RAW", "DOUBLE", None), ("STATUS", "TEXT", 20)):
        arcpy.management.AddField(output, name, kind, **({"field_length": length} if length else {}))


def completed_rows(output):
    if not arcpy.Exists(output):
        return {}
    found = {}
    with arcpy.da.SearchCursor(output, ["FROM_ID", "TO_ID", "PATH_KM", "COST_RAW", "STATUS"]) as rows:
        for a, b, length, cost, status in rows:
            if str(status).upper() != "OK":
                continue
            pair = tuple(sorted((int(a), int(b))))
            if pair in found:
                raise RuntimeError(f"Duplicate pair {pair} in {output}")
            found[pair] = [pair[0], pair[1], length, cost, "OK"]
    return found


def checkpoint(output, report):
    found = completed_rows(output)
    temp = report.with_suffix(report.suffix + ".tmp")
    with temp.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle); writer.writerow(FIELDS)
        for pair in sorted(found):
            writer.writerow(found[pair])
    os.replace(temp, report)
    return found


def delete_source_rows(output, source):
    gc.collect()
    arcpy.ClearWorkspaceCache_management()
    with arcpy.da.UpdateCursor(output, ["FROM_ID"], f"FROM_ID = {int(source)}") as rows:
        for _ in rows:
            rows.deleteRow()


def read_path_with_retry(path_fc, attempts=8):
    """Read a newly created path after transient file-GDB locks clear."""
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            return base.first_path_geometry(path_fc)
        except RuntimeError as error:
            last_error = error
            gc.collect()
            arcpy.ClearWorkspaceCache_management()
            if attempt < attempts:
                wait = min(10, attempt * 2)
                print(f"temporary geodatabase lock reading path; retry {attempt}/{attempts} in {wait}s")
                time.sleep(wait)
    raise last_error


def delete_with_retry(dataset, attempts=8):
    """Remove a temporary dataset without turning a transient lock into failure."""
    if not arcpy.Exists(dataset):
        return
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            arcpy.management.Delete(dataset)
            return
        except RuntimeError as error:
            last_error = error
            gc.collect()
            arcpy.ClearWorkspaceCache_management()
            if attempt < attempts:
                time.sleep(min(10, attempt * 2))
    raise last_error


def read_report(path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return {(int(r["from_core"]), int(r["to_core"])): r for r in csv.DictReader(handle)}


def summarize(pairs):
    by_scenario = {scenario: read_report(REPORTS / f"future2030_paths_{scenario}.csv")
                   for scenario in SCENARIOS}
    long_rows, comparison = [], []
    for a, b in pairs:
        base_row = by_scenario["low_growth"][(a, b)]
        base_cost = float(base_row["accumulated_cost_raw"])
        item = {"from_core": a, "to_core": b,
                "baseline_2024_cost": base_cost,
                "baseline_2024_path_km": float(base_row["path_length_km"])}
        for scenario in SCENARIOS:
            row = by_scenario[scenario][(a, b)]
            cost = float(row["accumulated_cost_raw"]); length = float(row["path_length_km"])
            change = 100.0 * (cost - base_cost) / base_cost
            long_rows.append({"scenario": scenario, "from_core": a, "to_core": b,
                              "path_length_km": length, "accumulated_cost_raw": cost,
                              "cost_change_from_2024_percent": change})
            item[f"{scenario}_cost"] = cost
            item[f"{scenario}_path_km"] = length
            item[f"{scenario}_cost_change_percent"] = change
        comparison.append(item)
    long_path = REPORTS / "future2030_path_costs_long.csv"
    with long_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(long_rows[0])); writer.writeheader(); writer.writerows(long_rows)
    comparison_path = REPORTS / "future2030_link_change_summary.csv"
    with comparison_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(comparison[0])); writer.writeheader(); writer.writerows(comparison)
    for scenario in ("continuation", "high_development"):
        changes = sorted(row[f"{scenario}_cost_change_percent"] for row in comparison)
        n = len(changes)
        median = changes[n // 2] if n % 2 else (changes[n // 2 - 1] + changes[n // 2]) / 2
        print(f"{scenario}: median selected-link cost change {median:+.3f}%; range {min(changes):+.3f}% to {max(changes):+.3f}%")
    print("long report:", long_path)
    print("comparison report:", comparison_path)


def main():
    arcpy.CheckOutExtension("Spatial")
    arcpy.env.overwriteOutput = True
    arcpy.env.snapRaster = base.SNAP
    arcpy.env.cellSize = base.SNAP
    arcpy.env.extent = arcpy.Describe(base.SNAP).extent
    arcpy.env.mask = base.MASK
    arcpy.env.outputCoordinateSystem = arcpy.Describe(base.SNAP).spatialReference
    arcpy.env.parallelProcessingFactor = "75%"
    for required in (base.CORES, base.LINKS, base.SNAP, base.MASK):
        base.require(required)
    pairs = pairs_from_links()
    if len(pairs) != 45:
        raise RuntimeError(f"Expected 45 fixed selected links; found {len(pairs)}")
    sources = sorted({a for a, _ in pairs})
    print("selected links:", len(pairs))
    print("source cores per scenario:", len(sources))
    print("planned cost-distance solves:", len(sources) * len(SCENARIOS))
    src, dst = "future2030_source", "future2030_destination"
    arcpy.management.MakeFeatureLayer(base.CORES, src)
    arcpy.management.MakeFeatureLayer(base.CORES, dst)

    for scenario in SCENARIOS:
        resistance = os.path.join(base.GDB, f"resistance_future2030_{scenario}_balanced_fence")
        output = os.path.join(base.GDB, f"least_cost_paths_future2030_{scenario}")
        report = REPORTS / f"future2030_paths_{scenario}.csv"
        base.require(resistance)
        if not arcpy.Exists(output):
            create_output(output)
        done = completed_rows(output)
        for source in sources:
            expected = expected_for_source(pairs, source)
            if all(pair in done for pair in expected):
                print(f"{scenario}: source core {source} already complete; skipping")
                continue
            delete_source_rows(output, source)
            print(f"{scenario}: source core {source}")
            arcpy.management.SelectLayerByAttribute(src, "NEW_SELECTION", f"CORE_ID = {source}")
            token = f"future2030_{scenario}_{source}"
            cd, backlink = os.path.join(base.GDB, token + "_cd"), os.path.join(base.GDB, token + "_bl")
            base.delete_if_exists(cd); base.delete_if_exists(backlink)
            try:
                CostDistance(src, resistance, maximum_distance=None, out_backlink_raster=backlink).save(cd)
                # Finish all geoprocessing and close each temporary dataset
                # before opening the output InsertCursor. Holding that cursor
                # while creating another FC in the same GDB can trigger 999999
                # "Cannot acquire a lock" after many successful iterations.
                pending = []
                for a, b in expected:
                    arcpy.management.SelectLayerByAttribute(dst, "NEW_SELECTION", f"CORE_ID = {b}")
                    path_fc = os.path.join(base.GDB, f"{token}_{b}_path")
                    delete_with_retry(path_fc)
                    try:
                        CostPathAsPolyline(dst, cd, backlink, path_fc, "BEST_SINGLE", "CORE_ID")
                        geometry, cost = read_path_with_retry(path_fc)
                        if cost is None:
                            raise RuntimeError("CostPathAsPolyline did not return accumulated path cost")
                        pending.append((geometry, a, b, scenario, geometry.length / 1000.0, cost, "OK"))
                    finally:
                        delete_with_retry(path_fc)
                gc.collect()
                arcpy.ClearWorkspaceCache_management()
                with arcpy.da.InsertCursor(output, ["SHAPE@", "FROM_ID", "TO_ID", "SCENARIO", "PATH_KM", "COST_RAW", "STATUS"]) as insert:
                    for pending_row in pending:
                        insert.insertRow(pending_row)
            finally:
                delete_with_retry(cd); delete_with_retry(backlink)
            done = checkpoint(output, report)
            print(f"{scenario}: checkpoint {len(done)}/45")
        done = checkpoint(output, report)
        if set(done) != set(pairs):
            raise RuntimeError(f"{scenario} incomplete; missing {sorted(set(pairs) - set(done))}")
        print(f"{scenario}: successful paths 45/45")
    summarize(pairs)
    print("Complete. Three 2030 path scenarios were compared with the exact 2024 low-growth baseline.")
    arcpy.CheckInExtension("Spatial")


if __name__ == "__main__":
    main()
