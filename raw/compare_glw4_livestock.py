"""Compare GLW4 cattle, goat, and sheep exposure patterns without modifying data."""

from pathlib import Path
import csv
import itertools
import os

import arcpy
import numpy as np


GDB = r"C:\cheetah\gdb\cheetah_working.gdb"
RASTERS = {
    "cattle": os.path.join(GDB, "livestock_cattle_2020_1km"),
    "goats": os.path.join(GDB, "livestock_goats_2020_1km"),
    "sheep": os.path.join(GDB, "livestock_sheep_2020_1km"),
}
REPORT_FOLDER = Path(r"C:\cheetah\reports")


def load_arrays():
    arrays = {}
    shapes = set()
    for species, raster in RASTERS.items():
        if not arcpy.Exists(raster):
            raise FileNotFoundError(f"Missing raster: {raster}")
        array = arcpy.RasterToNumPyArray(raster, nodata_to_value=np.nan).astype("float64")
        array[array < 0] = np.nan
        arrays[species] = array
        shapes.add(array.shape)
    if len(shapes) != 1:
        raise RuntimeError(f"Raster dimensions differ: {sorted(shapes)}")
    return arrays


def main():
    arrays = load_arrays()
    common = np.logical_and.reduce([np.isfinite(array) for array in arrays.values()])
    valid_cells = int(np.count_nonzero(common))
    if valid_cells < 2:
        raise RuntimeError("Fewer than two common valid cells were found.")

    values = {name: array[common] for name, array in arrays.items()}
    thresholds = {
        name: float(np.nanpercentile(data, 90)) for name, data in values.items()
    }
    hotspots = {name: data >= thresholds[name] for name, data in values.items()}

    correlation_rows = []
    overlap_rows = []
    for first, second in itertools.combinations(values, 2):
        pearson = float(np.corrcoef(values[first], values[second])[0, 1])
        correlation_rows.append({
            "species_1": first,
            "species_2": second,
            "pearson_correlation": pearson,
            "common_valid_cells": valid_cells,
        })

        both = int(np.count_nonzero(hotspots[first] & hotspots[second]))
        either = int(np.count_nonzero(hotspots[first] | hotspots[second]))
        first_count = int(np.count_nonzero(hotspots[first]))
        second_count = int(np.count_nonzero(hotspots[second]))
        overlap_rows.append({
            "species_1": first,
            "species_2": second,
            "hotspot_definition": "at_or_above_species_90th_percentile",
            "species_1_threshold_head_per_km2": thresholds[first],
            "species_2_threshold_head_per_km2": thresholds[second],
            "overlapping_hotspot_cells": both,
            "percent_of_species_1_hotspots_overlapping": 100.0 * both / first_count if first_count else 0.0,
            "percent_of_species_2_hotspots_overlapping": 100.0 * both / second_count if second_count else 0.0,
            "jaccard_overlap_percent": 100.0 * both / either if either else 0.0,
        })

    REPORT_FOLDER.mkdir(parents=True, exist_ok=True)
    correlation_report = REPORT_FOLDER / "livestock_species_correlations.csv"
    overlap_report = REPORT_FOLDER / "livestock_hotspot_overlap.csv"
    with correlation_report.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(correlation_rows[0]))
        writer.writeheader()
        writer.writerows(correlation_rows)
    with overlap_report.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(overlap_rows[0]))
        writer.writeheader()
        writer.writerows(overlap_rows)

    print(f"common valid cells: {valid_cells}")
    print("90th-percentile hotspot thresholds (head/km2):")
    for species in values:
        print(f"  {species}: {thresholds[species]:.3f}")
    print("pairwise comparison:")
    for corr, overlap in zip(correlation_rows, overlap_rows):
        print(
            f"  {corr['species_1']} vs {corr['species_2']}: "
            f"correlation {corr['pearson_correlation']:.3f}; "
            f"hotspot Jaccard overlap {overlap['jaccard_overlap_percent']:.2f}%"
        )
    print(f"correlation report: {correlation_report}")
    print(f"hotspot report: {overlap_report}")
    print("Complete. No rasters or map layers were changed.")


if __name__ == "__main__":
    main()
