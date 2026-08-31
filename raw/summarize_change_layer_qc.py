"""Create a read-only QC summary for continuous-change rasters."""

from __future__ import annotations

import csv
from pathlib import Path

import arcpy


WORKING_GDB = Path(r"C:\cheetah\gdb\cheetah_working.gdb")
REPORT_PATH = Path(r"C:\cheetah\reports\change_layer_qc_summary.csv")
VARIABLES = ("built", "vcf_tree", "vcf_nontree", "vcf_bare")
PAIRS = ((2012, 2016), (2016, 2020), (2020, 2024), (2012, 2024))


def raster_property(dataset: str, property_name: str) -> float:
    try:
        return float(arcpy.management.GetRasterProperties(dataset, property_name).getOutput(0))
    except arcpy.ExecuteError:
        # Newly derived geodatabase rasters may not have statistics yet.  This
        # writes only summary metadata; it does not alter their pixel values.
        print(f"calculating missing statistics: {Path(dataset).name}")
        # Force a rebuild: ArcGIS may otherwise skip a stale/incomplete stats
        # record left by a just-created raster calculation.
        arcpy.management.CalculateStatistics(dataset, skip_existing="OVERWRITE")
        return float(arcpy.management.GetRasterProperties(dataset, property_name).getOutput(0))


def flag(kind: str, variable: str, minimum: float, maximum: float) -> str:
    if kind == "d" and variable.startswith("vcf_") and (minimum < -100 or maximum > 100):
        return "CHECK: VCF absolute change is outside the possible -100 to +100 percentage-point range"
    if kind == "p" and variable.startswith("vcf_") and minimum < -100:
        return "CHECK: proportional VCF change is below -100%, which is not possible"
    if kind == "p" and variable.startswith("vcf_") and maximum > 1000:
        return "REVIEW: high proportional change remains; use as supplementary context, not the main map"
    if kind == "d" and variable == "lights":
        return "CONTEXT: values are flare-masked absolute VIIRS brightness change; document the export scale before reporting magnitude"
    return ""


def main() -> int:
    rows = []
    for kind, label in (("d", "absolute"), ("p", "proportional")):
        for variable in VARIABLES:
            for earlier, later in PAIRS:
                dataset = str(WORKING_GDB / f"{kind}_{variable}_{earlier}_{later}_1km")
                if not arcpy.Exists(dataset):
                    raise RuntimeError(f"Missing change raster: {dataset}")
                minimum = raster_property(dataset, "MINIMUM")
                maximum = raster_property(dataset, "MAXIMUM")
                mean = raster_property(dataset, "MEAN")
                standard_deviation = raster_property(dataset, "STD")
                rows.append(
                    {
                        "raster": Path(dataset).name,
                        "change_type": label,
                        "variable": variable.replace("vcf_", ""),
                        "period": f"{earlier}-{later}",
                        "minimum": round(minimum, 6),
                        "maximum": round(maximum, 6),
                        "mean": round(mean, 6),
                        "standard_deviation": round(standard_deviation, 6),
                        "qc_note": flag(kind, variable, minimum, maximum),
                    }
                )

    # Nighttime lights are intentionally absolute-only: proportional changes are
    # unstable where the baseline signal is near zero.
    for earlier, later in PAIRS:
        dataset = str(WORKING_GDB / f"d_lights_{earlier}_{later}_1km")
        if not arcpy.Exists(dataset):
            raise RuntimeError(f"Missing flare-masked lights change raster: {dataset}")
        minimum = raster_property(dataset, "MINIMUM")
        maximum = raster_property(dataset, "MAXIMUM")
        mean = raster_property(dataset, "MEAN")
        standard_deviation = raster_property(dataset, "STD")
        rows.append(
            {
                "raster": Path(dataset).name,
                "change_type": "absolute",
                "variable": "lights",
                "period": f"{earlier}-{later}",
                "minimum": round(minimum, 6),
                "maximum": round(maximum, 6),
                "mean": round(mean, 6),
                "standard_deviation": round(standard_deviation, 6),
                "qc_note": flag("d", "lights", minimum, maximum),
            }
        )

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with REPORT_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    notes = [row for row in rows if row["qc_note"]]
    print(f"checked rasters: {len(rows)}")
    print(f"QC notes: {len(notes)}")
    for row in notes:
        print(f"{row['raster']}: {row['qc_note']}")
    print(f"report: {REPORT_PATH}")
    print("No raster values or map layers were changed; missing raster statistics were calculated as metadata.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
