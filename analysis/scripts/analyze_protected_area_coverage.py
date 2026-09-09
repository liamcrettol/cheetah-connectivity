"""Calculate final high-current concentration coverage by protected areas.

Source: UNEP-WCMC/IUCN WDPA polygon service, August 2026. The primary analysis
uses terrestrial/coastal polygons, excludes only ``Proposed`` sites, dissolves
overlaps, and works on the final 1-km valid-current grid. Point records and
marine-only polygons are intentionally excluded from areal coverage estimates.

The 999-draw reference distribution samples the same number of cells uniformly
from valid modeled landscape cells. It is an area-standardized descriptive null,
not a causal test and not a spatially autocorrelation-preserving simulation.
"""
import csv
import datetime as dt
import json
import os
from pathlib import Path

import arcpy
import numpy as np


WDPA_SERVICE = (
    "https://data-gis.unep-wcmc.org/server/rest/services/ProtectedSites/"
    "The_World_Database_of_Protected_Areas/FeatureServer/1"
)
WDPA_CITATION = (
    "UNEP-WCMC and IUCN (2026), Protected Planet: The World Database on "
    "Protected Areas (WDPA) [Online], August 2026, Cambridge, UK. "
    "https://doi.org/10.34892/6fwd-af11"
)
WORK_GDB = r"C:\cheetah\gdb\cheetah_working.gdb"
CURRENT_GDB = r"C:\cheetah\circuitscape\derived\current_final_balanced_fence.gdb"
CURRENT = CURRENT_GDB + r"\current_final_balanced_fence_2024_mean"
HIGH_CURRENT = CURRENT_GDB + r"\current_final_candidate_concentration_2024"
PA_POLYGONS = WORK_GDB + r"\wdpa_aug2026_polygon_study_extent"
PA_DISSOLVED = WORK_GDB + r"\wdpa_aug2026_polygon_dissolved"
PA_GRID = WORK_GDB + r"\wdpa_aug2026_coverage_1km"
REPORTS = Path(r"C:\cheetah\reports")
BACKUPS = Path(r"C:\cheetah\backups")
NODATA = -9999
N_PERMUTATIONS = 999
RNG_SEED = 20260909


def extent_feature_class(source):
    # ArcGIS Pro can release ``in_memory`` feature classes unexpectedly between
    # CreateFeatureclass and InsertCursor.  Keep this tiny temporary polygon in
    # the working geodatabase instead; it is deleted after the WDPA clip.
    name = WORK_GDB + r"\\_pa_study_extent_tmp"
    if arcpy.Exists(name):
        arcpy.management.Delete(name)
    raster = arcpy.Raster(source)
    arcpy.management.CreateFeatureclass(
        WORK_GDB, "_pa_study_extent_tmp", "POLYGON", spatial_reference=raster.spatialReference,
    )
    e = raster.extent
    polygon = arcpy.Polygon(arcpy.Array([
        arcpy.Point(e.XMin, e.YMin), arcpy.Point(e.XMin, e.YMax),
        arcpy.Point(e.XMax, e.YMax), arcpy.Point(e.XMax, e.YMin),
    ]), raster.spatialReference)
    with arcpy.da.InsertCursor(name, ["SHAPE@"]) as cursor:
        cursor.insertRow([polygon])
    return name


def inventory(feature_class):
    rows = []
    with arcpy.da.SearchCursor(feature_class, ["realm", "status"]) as cursor:
        for realm, status in cursor:
            rows.append((str(realm or "<null>"), str(status or "<null>")))
    counts = {}
    for value in rows:
        counts[value] = counts.get(value, 0) + 1
    return [{"realm": key[0], "status": key[1], "feature_count": value}
            for key, value in sorted(counts.items())]


def acquire_polygons():
    extent = extent_feature_class(CURRENT)
    if arcpy.Exists(PA_POLYGONS):
        arcpy.management.Delete(PA_POLYGONS)
    remote = arcpy.management.MakeFeatureLayer(WDPA_SERVICE, "wdpa_aug2026_remote")[0]
    # Marine-only polygons cannot contribute to terrestrial connectivity area.
    # Proposed sites are excluded from the primary legal-protection estimate;
    # other reported statuses are retained and documented in the report.
    query = "realm IN ('Terrestrial', 'Coastal') AND (status IS NULL OR status <> 'Proposed')"
    arcpy.management.SelectLayerByAttribute(remote, "NEW_SELECTION", query)
    arcpy.management.SelectLayerByLocation(remote, "INTERSECT", extent, selection_type="SUBSET_SELECTION")
    selected = int(arcpy.management.GetCount(remote)[0])
    if selected == 0:
        raise RuntimeError("The WDPA service returned no eligible polygons in the study extent")
    arcpy.conversion.ExportFeatures(remote, PA_POLYGONS)
    arcpy.analysis.Clip(PA_POLYGONS, extent, PA_DISSOLVED + "_clip")
    clipped = PA_DISSOLVED + "_clip"
    if arcpy.Exists(PA_DISSOLVED):
        arcpy.management.Delete(PA_DISSOLVED)
    arcpy.management.Dissolve(clipped, PA_DISSOLVED, multi_part="MULTI_PART")
    arcpy.management.Delete(clipped)
    arcpy.management.Delete(extent)
    return selected


def make_grid():
    if arcpy.Exists(PA_GRID):
        arcpy.management.Delete(PA_GRID)
    old = {name: getattr(arcpy.env, name) for name in ("snapRaster", "extent", "cellSize", "mask", "outputCoordinateSystem")}
    try:
        arcpy.env.snapRaster = CURRENT
        arcpy.env.extent = CURRENT
        arcpy.env.cellSize = CURRENT
        arcpy.env.mask = CURRENT
        arcpy.env.outputCoordinateSystem = arcpy.Describe(CURRENT).spatialReference
        oid = arcpy.Describe(PA_DISSOLVED).OIDFieldName
        arcpy.conversion.PolygonToRaster(PA_DISSOLVED, oid, PA_GRID, "CELL_CENTER", cellsize=CURRENT)
    finally:
        for name, value in old.items():
            setattr(arcpy.env, name, value)


def calculate_coverage():
    current = arcpy.RasterToNumPyArray(CURRENT, nodata_to_value=np.nan).astype(np.float64, copy=False)
    high = arcpy.RasterToNumPyArray(HIGH_CURRENT, nodata_to_value=NODATA).astype(np.int16, copy=False)
    pa = arcpy.RasterToNumPyArray(PA_GRID, nodata_to_value=0)
    valid = np.isfinite(current)
    if current.shape != high.shape or current.shape != pa.shape:
        raise RuntimeError("Current, high-current, and PA grids are not identical")
    coverage = (pa > 0) & valid
    rng = np.random.default_rng(RNG_SEED)
    results = []
    for code, label in ((1, "High concentration (95th–99th percentile)"),
                        (2, "Highest concentration (>=99th percentile)"),
                        (0, "Combined high concentration (>=95th percentile)")):
        target = ((high == code) if code else np.isin(high, (1, 2))) & valid
        cells = int(target.sum())
        inside = int((target & coverage).sum())
        if cells == 0:
            raise RuntimeError(f"{label}: no valid cells")
        observed = inside / cells
        # Hypergeometric sampling exactly matches uniform equal-area draws
        # without allocating a 999 x ncell random matrix.
        draws = rng.hypergeometric(
            int(coverage.sum()), int(valid.sum() - coverage.sum()), cells, size=N_PERMUTATIONS,
        ) / cells
        results.append({
            "class": label,
            "model_cells": cells,
            "protected_cells": inside,
            "protected_percent": 100.0 * observed,
            "null_mean_percent": 100.0 * float(draws.mean()),
            "null_p025_percent": 100.0 * float(np.percentile(draws, 2.5)),
            "null_p975_percent": 100.0 * float(np.percentile(draws, 97.5)),
            "difference_from_null_mean_percentage_points": 100.0 * (observed - draws.mean()),
            "one_sided_high_tail_probability": float((np.count_nonzero(draws >= observed) + 1) / (N_PERMUTATIONS + 1)),
            "one_sided_low_tail_probability": float((np.count_nonzero(draws <= observed) + 1) / (N_PERMUTATIONS + 1)),
        })
    return results, int(valid.sum()), int(coverage.sum())


def main():
    for dataset in (CURRENT, HIGH_CURRENT):
        if not arcpy.Exists(dataset):
            raise FileNotFoundError(f"Missing required final-model input: {dataset}")
    BACKUPS.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUPS / f"Resistance_before_protected_area_coverage_{stamp}.aprx"
    aprx.saveACopy(str(backup))
    print("downloading/selecting WDPA August 2026 polygon records for the study extent")
    selected = acquire_polygons()
    make_grid()
    rows, valid_cells, pa_cells = calculate_coverage()
    statuses = inventory(PA_POLYGONS)

    report = REPORTS / f"protected_area_high_current_coverage_{stamp}.csv"
    with report.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    metadata = {
        "created": dt.datetime.now().isoformat(timespec="seconds"),
        "source_service": WDPA_SERVICE,
        "source_citation": WDPA_CITATION,
        "study_extent_eligible_pa_polygons_before_clip": selected,
        "valid_model_cells": valid_cells,
        "protected_valid_model_cells": pa_cells,
        "protected_valid_model_percent": 100.0 * pa_cells / valid_cells,
        "primary_inclusion": "WDPA polygon records with realm Terrestrial or Coastal and status other than Proposed",
        "excluded": "WDPA point records, marine-only polygons, and Proposed polygons",
        "null": f"{N_PERMUTATIONS} uniform equal-area samples from valid model-support cells; seed {RNG_SEED}",
        "null_limit": "The null does not preserve spatial autocorrelation or patch geometry; use as descriptive area-standardized context, not causal inference.",
        "status_inventory": statuses,
    }
    record = REPORTS / f"protected_area_high_current_coverage_{stamp}.json"
    record.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    aprx.save()
    print("backup:", backup)
    print("eligible WDPA polygons selected:", selected)
    print("valid model cells / protected valid model cells:", valid_cells, "/", pa_cells)
    for row in rows:
        print(row["class"] + ":", f"{row['protected_percent']:.3f}% protected;",
              f"null mean {row['null_mean_percent']:.3f}%;",
              f"difference {row['difference_from_null_mean_percentage_points']:.3f} percentage points")
    print("report:", report)
    print("method record:", record)
    print("Complete. WDPA study-extent copies and coverage outputs were created; final model rasters and existing maps were unchanged.")


if __name__ == "__main__":
    main()
