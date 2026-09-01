"""Report the coverage retained by candidate VCF proportional-change thresholds."""

from __future__ import annotations

import csv
from pathlib import Path

import arcpy
import numpy as np


SOURCE_FOLDER = Path(
    r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah\rasters\gee_exports"
)
REPORT_PATH = Path(r"C:\cheetah\reports\vcf_proportional_threshold_tradeoffs.csv")
VARIABLES = ("vcf_tree", "vcf_nontree", "vcf_bare")
BASELINE_YEARS = (2012, 2016, 2020)
THRESHOLDS = (1, 5, 10)
NODATA_SENTINEL = -9999


def main() -> int:
    rows = []
    for variable in VARIABLES:
        for year in BASELINE_YEARS:
            raster = SOURCE_FOLDER / f"{variable}_{year}_1km.tif"
            if not arcpy.Exists(str(raster)):
                raise RuntimeError(f"Missing VCF baseline raster: {raster}")

            values = arcpy.RasterToNumPyArray(str(raster), nodata_to_value=NODATA_SENTINEL)
            valid = values[values != NODATA_SENTINEL]
            if valid.size == 0:
                raise RuntimeError(f"No valid cells found in {raster}")

            row = {
                "variable": variable.replace("vcf_", ""),
                "baseline_year": year,
                "valid_pixel_count": int(valid.size),
            }
            for threshold in THRESHOLDS:
                excluded = int(np.count_nonzero(valid < threshold))
                row[f"excluded_below_{threshold}_percent"] = excluded
                row[f"excluded_pct_below_{threshold}_percent"] = round(100 * excluded / valid.size, 3)
            rows.append(row)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with REPORT_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print("variable | baseline | <1% | <5% | <10%")
    for row in rows:
        print(
            f"{row['variable']} | {row['baseline_year']} | "
            f"{row['excluded_pct_below_1_percent']:.2f}% | "
            f"{row['excluded_pct_below_5_percent']:.2f}% | "
            f"{row['excluded_pct_below_10_percent']:.2f}%"
        )
    print(f"\nreport: {REPORT_PATH}")
    print("No rasters, tables, or map layers were changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
