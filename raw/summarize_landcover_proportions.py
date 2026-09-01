"""Summarize six-class land-cover proportions for the four project years."""

from __future__ import annotations

import csv
from pathlib import Path

import arcpy


WORKING_GDB = Path(r"C:\cheetah\gdb\cheetah_working.gdb")
REPORT_PATH = Path(r"C:\cheetah\reports\landcover_class_proportions.csv")
CLASS_NAMES = {
    1: "open vegetation",
    2: "woody",
    3: "cropland",
    4: "built",
    5: "water",
    6: "bare",
}


def main() -> int:
    rows = []
    for year in (2012, 2016, 2020, 2024):
        raster = WORKING_GDB / f"lc6_{year}_1km"
        if not arcpy.Exists(str(raster)):
            raise RuntimeError(f"Missing reclassified raster: {raster}")

        counts = {value: 0 for value in CLASS_NAMES}
        for value, count in arcpy.da.SearchCursor(str(raster), ["Value", "Count"]):
            if value in counts:
                counts[value] = int(count)

        total = sum(counts.values())
        if total == 0:
            raise RuntimeError(f"No classified pixels found in {raster}")
        for value, class_name in CLASS_NAMES.items():
            rows.append(
                {
                    "year": year,
                    "class_value": value,
                    "class_name": class_name,
                    "pixel_count": counts[value],
                    "percent_of_classified_pixels": round(100 * counts[value] / total, 4),
                }
            )

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with REPORT_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print("year | open vegetation | woody | cropland | built | water | bare")
    for year in (2012, 2016, 2020, 2024):
        values = [
            next(row["percent_of_classified_pixels"] for row in rows if row["year"] == year and row["class_value"] == value)
            for value in CLASS_NAMES
        ]
        print(f"{year} | " + " | ".join(f"{value:.2f}%" for value in values))
    print(f"\nreport: {REPORT_PATH}")
    print("No raster values or project layers were changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
