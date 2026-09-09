"""Fast, exploratory temporal consistency audit of the Weise et al. observations.

This is not a population-trend or independent-validation analysis. Exact-year
records are spatially thinned to one occupied 10-km cell per period. Ambiguous
multi-year records are excluded from the primary comparison. The script uses
existing model products and performs no connectivity solve or map edit.
"""
from collections import defaultdict
import datetime as dt
from pathlib import Path
import csv
import json
import math
import os

import arcpy
import numpy as np
from scipy.stats import fisher_exact, mannwhitneyu

OBS = Path(r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah\raw\dryad_weise2017\cheetahobservationssouthernafrica.csv")
GDB = r"C:\cheetah\gdb\cheetah_working.gdb"
REPORTS = Path(r"C:\cheetah\reports")
RES_EARLY = os.path.join(GDB, "resistance_final_balanced_fence_documented_2012")
RES_LATE = os.path.join(GDB, "resistance_final_balanced_fence_documented_2016")
CORES = os.path.join(GDB, "cheetah_core_primary_density051_min500_1km")
PATHS = os.path.join(GDB, "conservation_priority_paths_temporal")
CELL_M = 10000.0
PATH_DISTANCE_M = 10000.0


def require(path):
    if not arcpy.Exists(str(path)):
        raise FileNotFoundError(str(path))


def parse_float(value):
    try:
        number = float(str(value).strip())
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def period(year_text):
    text = str(year_text).strip()
    if not text.isdigit() or len(text) != 4:
        return None
    year = int(text)
    if 2010 <= year <= 2012:
        return "early_2010_2012"
    if 2013 <= year <= 2016:
        return "late_2013_2016"
    return None


def cliff_delta(a, b):
    """Positive means values in b (late) tend to exceed values in a (early)."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if not len(a) or not len(b):
        return float("nan")
    # Rank-based identity equivalent to P(b>a)-P(b<a).
    u = mannwhitneyu(b, a, alternative="two-sided").statistic
    return float(2.0 * u / (len(a) * len(b)) - 1.0)


def raster_info(path):
    r = arcpy.Raster(path)
    sentinel = -999999.0
    values = arcpy.RasterToNumPyArray(path, nodata_to_value=sentinel).astype("float64")
    values[values == sentinel] = np.nan
    return r, values


def sample(array, raster, x, y):
    col = int(math.floor((x - raster.extent.XMin) / raster.meanCellWidth))
    row = int(math.floor((raster.extent.YMax - y) / raster.meanCellHeight))
    if row < 0 or col < 0 or row >= array.shape[0] or col >= array.shape[1]:
        return float("nan")
    return float(array[row, col])


def main():
    require(OBS)
    for item in (RES_EARLY, RES_LATE, CORES, PATHS):
        require(item)
    REPORTS.mkdir(parents=True, exist_ok=True)
    target_sr = arcpy.Describe(RES_EARLY).spatialReference
    wgs84 = arcpy.SpatialReference(4326)

    raw_counts = defaultdict(int)
    sources = defaultdict(set)
    cells = defaultdict(lambda: {"x": [], "y": [], "records": 0, "sources": set()})
    excluded_ambiguous = excluded_coordinate = 0
    # The archived CSV mixes legacy single-byte characters; Latin-1 preserves
    # every byte while all analytical fields remain plain ASCII.
    with OBS.open(newline="", encoding="latin-1") as handle:
        for row in csv.DictReader(handle):
            p = period(row.get("Assessment_Year"))
            if p is None:
                excluded_ambiguous += 1
                continue
            lat = parse_float(row.get("Combined_Lat"))
            lon = parse_float(row.get("Combined_Long"))
            if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
                excluded_coordinate += 1
                continue
            geom = arcpy.PointGeometry(arcpy.Point(lon, lat), wgs84).projectAs(target_sr)
            x, y = geom.firstPoint.X, geom.firstPoint.Y
            key = (p, int(math.floor(x / CELL_M)), int(math.floor(y / CELL_M)))
            cells[key]["x"].append(x); cells[key]["y"].append(y)
            cells[key]["records"] += 1
            source = (row.get("Source") or "unspecified").strip()
            cells[key]["sources"].add(source)
            raw_counts[p] += 1; sources[p].add(source)

    early_r, early_a = raster_info(RES_EARLY)
    late_r, late_a = raster_info(RES_LATE)
    core_r, core_a = raster_info(CORES)
    rows = []
    for (p, gx, gy), item in cells.items():
        x, y = float(np.mean(item["x"])), float(np.mean(item["y"]))
        rows.append({
            "period": p, "grid_x": gx, "grid_y": gy, "x": x, "y": y,
            "source_records": item["records"], "source_count": len(item["sources"]),
            "resistance": sample(early_a if p.startswith("early") else late_a,
                                 early_r if p.startswith("early") else late_r, x, y),
            "inside_fixed_core": int(sample(core_a, core_r, x, y) > 0),
            "within_10km_priority_path": 0,
        })

    # Mark proximity to existing robust priority links. The temporary point layer
    # is deleted and is never added to the map.
    temp = os.path.join(GDB, "_tmp_cheetah_temporal_audit_points")
    if arcpy.Exists(temp):
        arcpy.management.Delete(temp)
    arcpy.management.CreateFeatureclass(GDB, os.path.basename(temp), "POINT", spatial_reference=target_sr)
    arcpy.management.AddField(temp, "ROW_ID", "LONG")
    with arcpy.da.InsertCursor(temp, ["SHAPE@XY", "ROW_ID"]) as cursor:
        for i, row in enumerate(rows):
            cursor.insertRow([(row["x"], row["y"]), i])
    layer = "cheetah_temporal_audit_points_lyr"
    arcpy.management.MakeFeatureLayer(temp, layer)
    arcpy.management.SelectLayerByLocation(layer, "WITHIN_A_DISTANCE", PATHS, f"{PATH_DISTANCE_M} Meters")
    selected = {int(v) for (v,) in arcpy.da.SearchCursor(layer, ["ROW_ID"])}
    for i in selected:
        rows[i]["within_10km_priority_path"] = 1
    arcpy.management.Delete(layer)
    arcpy.management.Delete(temp)

    early_cells = {(r["grid_x"], r["grid_y"]) for r in rows if r["period"].startswith("early")}
    late_cells = {(r["grid_x"], r["grid_y"]) for r in rows if r["period"].startswith("late")}
    shared = early_cells & late_cells
    union = early_cells | late_cells
    # Exclusive cells avoid treating shared cells as independent observations in tests.
    early_only = [r for r in rows if r["period"].startswith("early") and (r["grid_x"], r["grid_y"]) not in shared]
    late_only = [r for r in rows if r["period"].startswith("late") and (r["grid_x"], r["grid_y"]) not in shared]
    early_res = [r["resistance"] for r in early_only if math.isfinite(r["resistance"])]
    late_res = [r["resistance"] for r in late_only if math.isfinite(r["resistance"])]
    u = mannwhitneyu(early_res, late_res, alternative="two-sided")
    core_table = [[sum(r["inside_fixed_core"] for r in early_only), sum(not r["inside_fixed_core"] for r in early_only)],
                  [sum(r["inside_fixed_core"] for r in late_only), sum(not r["inside_fixed_core"] for r in late_only)]]
    path_table = [[sum(r["within_10km_priority_path"] for r in early_only), sum(not r["within_10km_priority_path"] for r in early_only)],
                  [sum(r["within_10km_priority_path"] for r in late_only), sum(not r["within_10km_priority_path"] for r in late_only)]]
    core_test = fisher_exact(core_table, alternative="two-sided")
    path_test = fisher_exact(path_table, alternative="two-sided")
    raw_p = [float(u.pvalue), float(core_test.pvalue), float(path_test.pvalue)]
    adjusted = [min(1.0, p * len(raw_p)) for p in raw_p]

    def proportion(items, field):
        return sum(r[field] for r in items) / len(items) if items else float("nan")

    tests = [
        {"test": "resistance_2012_early_vs_2016_late", "method": "Mann-Whitney U",
         "early_n": len(early_res), "late_n": len(late_res),
         "early_median": float(np.median(early_res)), "late_median": float(np.median(late_res)),
         "cliffs_delta_late_minus_early": cliff_delta(early_res, late_res),
         "p_raw": raw_p[0], "p_bonferroni_3_tests": adjusted[0]},
        {"test": "inside_fixed_historical_core", "method": "Fisher exact",
         "early_n": len(early_only), "late_n": len(late_only),
         "early_proportion": proportion(early_only, "inside_fixed_core"),
         "late_proportion": proportion(late_only, "inside_fixed_core"),
         "odds_ratio": float(core_test.statistic), "p_raw": raw_p[1], "p_bonferroni_3_tests": adjusted[1]},
        {"test": "within_10km_robust_priority_path", "method": "Fisher exact",
         "early_n": len(early_only), "late_n": len(late_only),
         "early_proportion": proportion(early_only, "within_10km_priority_path"),
         "late_proportion": proportion(late_only, "within_10km_priority_path"),
         "odds_ratio": float(path_test.statistic), "p_raw": raw_p[2], "p_bonferroni_3_tests": adjusted[2]},
    ]
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    cell_path = REPORTS / f"cheetah_temporal_thinned_cells_{stamp}.csv"
    with cell_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    test_path = REPORTS / f"cheetah_temporal_consistency_tests_{stamp}.csv"
    with test_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=sorted({k for t in tests for k in t}))
        writer.writeheader(); writer.writerows(tests)
    summary = {
        "created": dt.datetime.now().isoformat(timespec="seconds"),
        "primary_periods": {"early": "2010-2012 exact-year records", "late": "2013-2016 exact-year records"},
        "raw_records": dict(raw_counts), "unique_sources": {k: len(v) for k, v in sources.items()},
        "excluded_non_exact_or_outside_period": excluded_ambiguous,
        "excluded_invalid_coordinates": excluded_coordinate,
        "spatial_thinning": "one occupied cell per period on a 10-km projected lattice",
        "unique_cells": {"early": len(early_cells), "late": len(late_cells), "shared": len(shared),
                         "early_only": len(early_cells-shared), "late_only": len(late_cells-shared),
                         "jaccard": len(shared)/len(union) if union else None},
        "tests": tests,
        "interpretation_limits": [
            "Observation effort, contributors, geography and telemetry intensity differ among years.",
            "The observations helped create the historical density cores, so core/path associations are not independent validation.",
            "Presence-only records cannot estimate abundance, absence, colonization or population trend.",
            "P-values are exploratory screening statistics; effect sizes and spatial sampling bias control interpretation.",
            "No post-2016 observations are available for direct validation of 2020 or 2024 modeled change.",
        ],
        "cell_report": str(cell_path), "test_report": str(test_path),
    }
    json_path = REPORTS / f"cheetah_temporal_consistency_summary_{stamp}.json"
    json_path.write_text(json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, allow_nan=False))
    print("cell report:", cell_path)
    print("test report:", test_path)
    print("summary:", json_path)
    print("Complete. Existing rasters, paths, map layers and project were unchanged.")


if __name__ == "__main__":
    main()
