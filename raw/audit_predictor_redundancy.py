"""Sample aligned 1 km predictors and report Spearman rank correlations.

Read-only analysis: no rasters, map layers, or project settings are changed.
Run inside the ArcGIS Pro Python window.
"""

from pathlib import Path
import csv
import os

import arcpy
import numpy as np
from scipy.stats import rankdata


GDB = r"C:\cheetah\gdb\cheetah_working.gdb"
GEE = Path(r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah\rasters\gee_exports")
REPORT_FOLDER = Path(r"C:\cheetah\reports")
MAX_SAMPLE = 200_000
SEED = 69150
NODATA_SENTINEL = -3.0e38

PREDICTORS = {
    "built_2024": os.path.join(GDB, "built_2024_aligned_1km"),
    "lights_2024_flaremasked": os.path.join(GDB, "lights_2024_1km_flaremasked"),
    "road_density_5km": os.path.join(GDB, "roaddens_1km"),
    "terrain_resistance": os.path.join(GDB, "terrain_resistance_1_10"),
    "livestock_cattle": os.path.join(GDB, "livestock_cattle_2020_1km"),
    "livestock_goats": os.path.join(GDB, "livestock_goats_2020_1km"),
    "livestock_sheep": os.path.join(GDB, "livestock_sheep_2020_1km"),
    "vcf_tree_2024": os.path.join(GDB, "vcf_tree_2024_aligned_1km"),
    "vcf_nontree_2024": os.path.join(GDB, "vcf_nontree_2024_aligned_1km"),
    "vcf_bare_2024": os.path.join(GDB, "vcf_bare_2024_aligned_1km"),
}


def raster_signature(path):
    desc = arcpy.Describe(path)
    return (
        int(arcpy.management.GetRasterProperties(path, "COLUMNCOUNT").getOutput(0)),
        int(arcpy.management.GetRasterProperties(path, "ROWCOUNT").getOutput(0)),
        round(float(desc.meanCellWidth), 6),
        round(float(desc.meanCellHeight), 6),
        tuple(round(v, 3) for v in (desc.extent.XMin, desc.extent.YMin, desc.extent.XMax, desc.extent.YMax)),
    )


def read_float(path):
    values = arcpy.RasterToNumPyArray(path, nodata_to_value=NODATA_SENTINEL).astype(np.float32, copy=False)
    values[values <= NODATA_SENTINEL / 2] = np.nan
    return values.ravel()


def main():
    missing = [f"{name}: {path}" for name, path in PREDICTORS.items() if not arcpy.Exists(path)]
    if missing:
        raise FileNotFoundError("Missing predictor inputs:\n  " + "\n  ".join(missing))

    signatures = {name: raster_signature(path) for name, path in PREDICTORS.items()}
    reference = next(iter(signatures.values()))
    mismatched = {name: sig for name, sig in signatures.items() if sig != reference}
    if mismatched:
        details = "\n".join(f"  {name}: {sig}" for name, sig in signatures.items())
        raise RuntimeError("Predictors are not on an identical grid; stop before correlation:\n" + details)
    print(f"verified identical grid: {reference[0]} columns x {reference[1]} rows")

    arrays = {}
    common = None
    for name, path in PREDICTORS.items():
        print(f"reading: {name}")
        array = read_float(path)
        arrays[name] = array
        valid = np.isfinite(array)
        common = valid if common is None else common & valid

    valid_indices = np.flatnonzero(common)
    if valid_indices.size == 0:
        raise RuntimeError("No cells contain valid data for every predictor.")
    rng = np.random.default_rng(SEED)
    if valid_indices.size > MAX_SAMPLE:
        sample_indices = rng.choice(valid_indices, MAX_SAMPLE, replace=False)
    else:
        sample_indices = valid_indices
    print(f"common valid cells: {valid_indices.size}")
    print(f"cells sampled: {sample_indices.size}")

    names = list(PREDICTORS)
    sample = np.column_stack([arrays[name][sample_indices] for name in names])
    ranks = np.column_stack([rankdata(sample[:, column], method="average") for column in range(sample.shape[1])])
    correlations = np.corrcoef(ranks, rowvar=False)

    REPORT_FOLDER.mkdir(parents=True, exist_ok=True)
    matrix_report = REPORT_FOLDER / "predictor_spearman_correlation.csv"
    with matrix_report.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["predictor"] + names)
        for row, name in enumerate(names):
            writer.writerow([name] + [f"{correlations[row, col]:.4f}" for col in range(len(names))])

    pairs_report = REPORT_FOLDER / "predictor_redundancy_review.csv"
    pairs = []
    for left in range(len(names)):
        for right in range(left + 1, len(names)):
            rho = float(correlations[left, right])
            level = "REVIEW" if abs(rho) >= 0.70 else "WATCH" if abs(rho) >= 0.50 else "OK"
            pairs.append((abs(rho), names[left], names[right], rho, level))
    pairs.sort(reverse=True)
    with pairs_report.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["predictor_a", "predictor_b", "spearman_rho", "flag", "interpretation"])
        for _, left, right, rho, level in pairs:
            writer.writerow([left, right, f"{rho:.4f}", level,
                             "possible redundant weighting; inspect concept and maps" if level == "REVIEW" else
                             "moderate overlap; retain only with distinct mechanism" if level == "WATCH" else
                             "limited rank overlap"])

    print("strongest relationships:")
    for _, left, right, rho, level in pairs[:15]:
        print(f"  {left} vs {right}: rho={rho:.3f} [{level}]")
    print(f"matrix: {matrix_report}")
    print(f"review: {pairs_report}")
    print("Complete. No rasters, layers, weights, or project settings were changed.")


if __name__ == "__main__":
    main()
