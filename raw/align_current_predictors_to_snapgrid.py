"""Create aligned copies of current continuous GEE predictors for modeling.

Original GeoTIFFs are preserved. Continuous percent/amount rasters use
bilinear resampling onto the project's established 1 km snap grid.
"""

from datetime import datetime
from pathlib import Path
import csv
import os

import arcpy
from arcpy.sa import ExtractByMask


GDB = r"C:\cheetah\gdb\cheetah_working.gdb"
GEE = Path(r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah\rasters\gee_exports")
SNAP = r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah_connectivity.gdb\snapgrid_1km"
MASK = r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah_connectivity.gdb\extent_buffered"
BACKUPS = Path(r"C:\cheetah\backups")
REPORTS = Path(r"C:\cheetah\reports")

INPUTS = {
    "built_2024_aligned_1km": str(GEE / "built_2024_1km.tif"),
    "vcf_tree_2024_aligned_1km": str(GEE / "vcf_tree_2024_1km.tif"),
    "vcf_nontree_2024_aligned_1km": str(GEE / "vcf_nontree_2024_1km.tif"),
    "vcf_bare_2024_aligned_1km": str(GEE / "vcf_bare_2024_1km.tif"),
}


def signature(path):
    d = arcpy.Describe(path)
    return (
        int(arcpy.management.GetRasterProperties(path, "COLUMNCOUNT").getOutput(0)),
        int(arcpy.management.GetRasterProperties(path, "ROWCOUNT").getOutput(0)),
        round(float(d.meanCellWidth), 6), round(float(d.meanCellHeight), 6),
        tuple(round(v, 3) for v in (d.extent.XMin, d.extent.YMin, d.extent.XMax, d.extent.YMax)),
    )


def main():
    arcpy.CheckOutExtension("Spatial")
    for path in (GDB, SNAP, MASK, *INPUTS.values()):
        if not arcpy.Exists(path):
            raise FileNotFoundError(path)

    aprx = arcpy.mp.ArcGISProject("CURRENT")
    BACKUPS.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUPS / f"{Path(aprx.filePath).stem}_before_predictor_alignment_{stamp}.aprx"
    aprx.saveACopy(str(backup))
    print(f"backup: {backup}")

    arcpy.env.overwriteOutput = True
    arcpy.env.snapRaster = SNAP
    arcpy.env.cellSize = SNAP
    arcpy.env.extent = SNAP
    arcpy.env.mask = MASK
    arcpy.env.outputCoordinateSystem = arcpy.Describe(SNAP).spatialReference
    target_signature = signature(SNAP)

    rows = []
    for output_name, source in INPUTS.items():
        output = os.path.join(GDB, output_name)
        temporary = os.path.join(GDB, "tmp_" + output_name)
        for dataset in (temporary, output):
            if arcpy.Exists(dataset):
                arcpy.management.Delete(dataset)
        arcpy.management.ProjectRaster(
            source, temporary, arcpy.Describe(SNAP).spatialReference,
            "BILINEAR", "1000 1000"
        )
        ExtractByMask(temporary, MASK, "INSIDE").save(output)
        if arcpy.Exists(temporary):
            arcpy.management.Delete(temporary)
        actual = signature(output)
        if actual != target_signature:
            raise RuntimeError(f"Alignment failed for {output_name}: {actual} != {target_signature}")
        rows.append([output_name, source, output, "BILINEAR", actual])
        print(f"aligned: {output_name}")

    report = REPORTS / "current_predictor_alignment.csv"
    with report.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["output", "source", "aligned_path", "resampling", "grid_signature"])
        writer.writerows(rows)
    print(f"verified grid: {target_signature}")
    print(f"report: {report}")
    print("Complete. Original GEE exports were unchanged; aligned continuous copies were created.")


if __name__ == "__main__":
    main()
