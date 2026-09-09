"""Audit all-zero VCF triplets before final production current-flow runs.

This is a read-only diagnostic.  It checks cells where VCF tree, non-tree,
and bare cover are all zero even though the triplet is not NoData.  Such a
triplet is not automatically bare ground: the three fractions should normally
describe the full pixel.  The script cross-tabulates those cells with the
existing MCD12Q1 classified-area fractions so that they can be treated as
water context, land context, or unresolved data uncertainty.

It does not modify any resistance surface, VCF raster, map layer, or project.
"""

from datetime import datetime
from pathlib import Path
import csv
import json

import arcpy
import numpy as np


GDB = r"C:\cheetah\gdb\cheetah_working.gdb"
FRACTION_DIR = Path(r"C:\cheetah\raw\source_qa\water_class_fractions_v1_20260904")
REPORT_DIR = Path(r"C:\cheetah\reports")
YEARS = (2012, 2016, 2020, 2024)

# Fixed to the documented export order in export_gee_water_class_fractions_v1.js.
# RasterToNumPyArray returns a 0-based (band, row, column) array.
BOTH_WATER_BAND = 8
BOTH_LAND_BAND = 9
THRESHOLD = 0.95  # descriptive context bin, not an ecological cutoff


def gdb(name):
    return str(Path(GDB) / name)


def require(dataset):
    if not arcpy.Exists(dataset):
        raise FileNotFoundError(dataset)
    return dataset


def grid(dataset):
    # Describe on a multiband TIFF can return DescribeData without width/height.
    # Raster exposes the required geometry consistently for TIFFs and GDB rasters.
    r = arcpy.Raster(dataset)
    e = r.extent
    return (int(r.width), int(r.height), float(r.meanCellWidth), float(r.meanCellHeight),
            float(e.XMin), float(e.YMin), float(e.XMax), float(e.YMax),
            int(r.spatialReference.factoryCode or 0))


def same_grid(first, second, tolerance=0.001):
    return len(first) == len(second) and all(
        a == b if i in (0, 1, 8) else abs(a - b) <= tolerance
        for i, (a, b) in enumerate(zip(first, second))
    )


def valid_array(dataset):
    raster = arcpy.Raster(dataset)
    values = arcpy.RasterToNumPyArray(raster).astype(np.float64)
    nulls = arcpy.RasterToNumPyArray(arcpy.sa.IsNull(raster)).astype(bool)
    if values.shape != nulls.shape:
        raise RuntimeError(f"Value/NoData grids differ: {dataset}")
    values[nulls] = np.nan
    return values


def fraction_bands(dataset):
    values = arcpy.RasterToNumPyArray(arcpy.Raster(dataset)).astype(np.float64)
    if values.ndim != 3 or values.shape[0] < BOTH_LAND_BAND:
        raise RuntimeError(
            f"Expected at least {BOTH_LAND_BAND} fraction bands; found shape {values.shape}: {dataset}"
        )
    water = values[BOTH_WATER_BAND - 1]
    land = values[BOTH_LAND_BAND - 1]
    return water, land


def count(mask):
    return int(np.count_nonzero(mask))


def main():
    arcpy.CheckOutExtension("Spatial")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    reference = gdb("vcf_tree_2012_aligned_1km")
    reference_grid = grid(require(reference))
    annual = []
    zero_masks = {}
    water_masks = {}
    land_masks = {}

    for year in YEARS:
        tree = gdb(f"vcf_tree_{year}_aligned_1km")
        nontree = gdb(f"vcf_nontree_{year}_aligned_1km")
        bare = gdb(f"vcf_bare_{year}_aligned_1km")
        fractions = str(FRACTION_DIR / f"water_class_fractions_v1_{year}.tif")
        for item in (tree, nontree, bare, fractions):
            require(item)
            if not same_grid(reference_grid, grid(item)):
                raise RuntimeError(f"Grid mismatch for {year}: {item}\n{grid(item)}\n{reference_grid}")

        tree_a, non_a, bare_a = (valid_array(item) for item in (tree, nontree, bare))
        valid = np.isfinite(tree_a) & np.isfinite(non_a) & np.isfinite(bare_a)
        zero = valid & (tree_a == 0) & (non_a == 0) & (bare_a == 0)
        water, land = fraction_bands(fractions)
        water95 = zero & np.isfinite(water) & (water >= THRESHOLD)
        land95 = zero & np.isfinite(land) & (land >= THRESHOLD)
        unresolved = zero & ~(water95 | land95)

        zero_masks[year] = zero
        water_masks[year] = water95
        land_masks[year] = land95
        annual.append({
            "year": year,
            "valid_vcf_triplets": count(valid),
            "all_zero_triplets": count(zero),
            "zero_triplets_both_water_ge95pct": count(water95),
            "zero_triplets_both_land_ge95pct": count(land95),
            "zero_triplets_unresolved_or_mixed": count(unresolved),
        })
        print(
            f"{year}: zero triplets={count(zero):,}; water context={count(water95):,}; "
            f"land context={count(land95):,}; unresolved={count(unresolved):,}", flush=True
        )

    persistent_zero = np.logical_and.reduce([zero_masks[y] for y in YEARS])
    persistent_water = persistent_zero & np.logical_and.reduce([water_masks[y] for y in YEARS])
    persistent_land = persistent_zero & np.logical_and.reduce([land_masks[y] for y in YEARS])
    persistent_other = persistent_zero & ~(persistent_water | persistent_land)

    summary = {
        "created": datetime.now().isoformat(timespec="seconds"),
        "scope": "Read-only VCF all-zero-triplet context audit; no resistance or map changes.",
        "threshold_note": "0.95 is a descriptive classified-area context threshold, not an inundation or movement cutoff.",
        "annual": annual,
        "persistent_all_four_years": {
            "all_zero_triplets": count(persistent_zero),
            "both_water_ge95pct_each_year": count(persistent_water),
            "both_land_ge95pct_each_year": count(persistent_land),
            "unresolved_or_mixed": count(persistent_other),
        },
        "interpretation_boundary": [
            "An all-zero VCF triplet is not automatically bare ground because the bare band is also zero.",
            "MCD12Q1 fractions are land-cover classifications, not measured inundation.",
            "This audit does not select a missing-data policy or change the final resistance surface.",
        ],
    }
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = REPORT_DIR / f"vcf_zero_triplet_context_{stamp}.json"
    csv_path = REPORT_DIR / f"vcf_zero_triplet_context_{stamp}.csv"
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(annual[0]))
        writer.writeheader()
        writer.writerows(annual)

    print("persistent all-zero triplets across four years:", count(persistent_zero))
    print("persistent water context:", count(persistent_water))
    print("persistent land context:", count(persistent_land))
    print("persistent unresolved/mixed:", count(persistent_other))
    print(f"report: {json_path}")
    print(f"table: {csv_path}")
    print("No resistance surfaces, VCF rasters, map layers, or project files were changed.")


if __name__ == "__main__":
    main()
