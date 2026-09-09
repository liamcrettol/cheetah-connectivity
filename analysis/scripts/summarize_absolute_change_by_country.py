"""Summarize primary absolute-change rasters by country within the study extent."""

from __future__ import annotations

import csv
import urllib.request
import zipfile
from pathlib import Path

import arcpy
from arcpy.sa import ZonalStatisticsAsTable


COUNTRY_URL = "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_0_countries.zip"
RAW_FOLDER = Path(r"C:\cheetah\raw\boundaries\natural_earth")
WORKING_GDB = Path(r"C:\cheetah\gdb\cheetah_working.gdb")
REPORT_PATH = Path(r"C:\cheetah\reports\country_absolute_change_summary.csv")
EXTENT_MASK = Path(r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah_connectivity.gdb\extent_buffered")
COUNTRIES = WORKING_GDB / "countries_in_study_extent"
YEARS = ((2012, 2016), (2016, 2020), (2020, 2024), (2012, 2024))
VARIABLES = ("built", "vcf_tree", "vcf_nontree", "vcf_bare", "lights")


def delete_if_exists(path: str):
    if arcpy.Exists(path):
        arcpy.management.Delete(path)


def source_shapefile() -> Path:
    RAW_FOLDER.mkdir(parents=True, exist_ok=True)
    archive = RAW_FOLDER / "ne_10m_admin_0_countries.zip"
    extract_folder = RAW_FOLDER / "ne_10m_admin_0_countries"
    if not archive.exists():
        print("downloading Natural Earth country boundaries")
        urllib.request.urlretrieve(COUNTRY_URL, archive)
    if not extract_folder.exists():
        with zipfile.ZipFile(archive) as zipped:
            zipped.extractall(extract_folder)
    matches = list(extract_folder.rglob("ne_10m_admin_0_countries.shp"))
    if len(matches) != 1:
        raise RuntimeError("Could not locate the Natural Earth countries shapefile after extraction.")
    return matches[0]


def make_country_zones(reference_raster: str) -> str:
    raw = source_shapefile()
    temporary_projected = str(WORKING_GDB / "_countries_projected_temp")
    delete_if_exists(temporary_projected)
    delete_if_exists(str(COUNTRIES))
    arcpy.management.Project(str(raw), temporary_projected, arcpy.Describe(reference_raster).spatialReference)
    arcpy.analysis.PairwiseClip(temporary_projected, str(EXTENT_MASK), str(COUNTRIES))
    delete_if_exists(temporary_projected)
    if int(arcpy.management.GetCount(str(COUNTRIES)).getOutput(0)) == 0:
        raise RuntimeError("No country polygons intersected the study extent.")
    return str(COUNTRIES)


def main() -> int:
    sources = []
    for variable in VARIABLES:
        for start, end in YEARS:
            dataset = str(WORKING_GDB / f"d_{variable}_{start}_{end}_1km")
            if not arcpy.Exists(dataset):
                raise RuntimeError(f"Missing absolute change raster: {dataset}")
            sources.append((variable, start, end, dataset))

    arcpy.CheckOutExtension("Spatial")
    old_add_outputs = arcpy.env.addOutputsToMap
    arcpy.env.addOutputsToMap = False
    try:
        zones = make_country_zones(sources[0][3])
        fields = {field.name for field in arcpy.ListFields(zones)}
        zone_field = "SOV_A3" if "SOV_A3" in fields else "ADM0_A3"
        name_field = "NAME" if "NAME" in fields else "ADMIN"
        country_names = {code: name for code, name in arcpy.da.SearchCursor(zones, [zone_field, name_field])}

        rows = []
        for variable, start, end, dataset in sources:
            table = str(WORKING_GDB / f"zs_d_{variable}_{start}_{end}")
            delete_if_exists(table)
            arcpy.env.snapRaster = dataset
            arcpy.env.cellSize = dataset
            arcpy.env.extent = dataset
            ZonalStatisticsAsTable(zones, zone_field, dataset, table, "DATA", "ALL")
            with arcpy.da.SearchCursor(table, [zone_field, "COUNT", "MIN", "MAX", "MEAN", "STD"]) as cursor:
                for code, count, minimum, maximum, mean, std in cursor:
                    rows.append({
                        "country_code": code,
                        "country": country_names.get(code, code),
                        "variable": variable.replace("vcf_", ""),
                        "period": f"{start}-{end}",
                        "cell_count": count,
                        "minimum": minimum,
                        "maximum": maximum,
                        "mean": mean,
                        "standard_deviation": std,
                    })
            print(f"summarized: d_{variable}_{start}_{end}_1km")
    finally:
        arcpy.env.addOutputsToMap = old_add_outputs
        arcpy.env.snapRaster = None
        arcpy.env.cellSize = None
        arcpy.env.extent = None
        arcpy.CheckInExtension("Spatial")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with REPORT_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"countries in study extent: {len(country_names)}")
    print(f"summary rows: {len(rows)}")
    print(f"report: {REPORT_PATH}")
    print("No raster values or map layers were changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
