"""Export outside-core current surfaces as GeoTIFFs for hand-built cartography.

Why this exists
---------------
The outside-core masking only ever happened in memory inside the analysis
scripts, so there was no layer anyone could drag into ArcGIS Pro and symbolise.
Building a current figure from the raw surfaces reproduces the original problem:
in a pairwise formulation the 23 focal cores inject and drain the current, so
they carry the entire top decile and will dominate any colour ramp.

These are written masked, with the cores and all non-positive cells set to
NoData, so any classification applied in Pro is computed over connecting
landscape only.

GeoTIFF rather than file-geodatabase raster because GDAL's OpenFileGDB driver is
read-only for rasters. Pro reads TIFFs natively; use Raster to Geodatabase if you
want them inside cheetah_working.gdb.

Outputs, all 1 km, Africa Albers Equal Area Conic, NoData -9999:

    current_outside_cores_<year>.tif          masked current, four years
    current_pctrank_outside_cores_2024.tif    percentile rank 0-100 within the
                                              outside-core domain, so any
                                              threshold can be set in Pro
    current_change_pct_outside_cores_2012_2024.tif
                                              percent change on the shared domain

Read-only against the model outputs. Nothing in any geodatabase is modified.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np
from osgeo import gdal

gdal.UseExceptions()

WORK_GDB = r"C:\cheetah\gdb\cheetah_working.gdb"
CURRENT_GDB = r"C:\cheetah\circuitscape\derived\current_final_balanced_fence.gdb"
CORE = "cheetah_core_primary_density051_min500_1km"
CURRENT_TEMPLATE = "current_final_balanced_fence_{year}_mean"
YEARS = (2012, 2016, 2020, 2024)

OUT_DIR = Path(r"C:\cheetah\rasters\outside_core")
NODATA = -9999.0

NP_DTYPE = {
    gdal.GDT_Byte: "u1", gdal.GDT_Int16: "i2", gdal.GDT_UInt16: "u2",
    gdal.GDT_Int32: "i4", gdal.GDT_UInt32: "u4",
    gdal.GDT_Float32: "f4", gdal.GDT_Float64: "f8",
}


def read(gdb: str, name: str):
    """Read via ReadRaster; gdal_array is broken against numpy 2.2 in this env."""
    dataset = gdal.Open(f'OpenFileGDB:"{gdb}":{name}')
    band = dataset.GetRasterBand(1)
    raw = band.ReadRaster(0, 0, dataset.RasterXSize, dataset.RasterYSize)
    array = np.frombuffer(raw, dtype=NP_DTYPE[band.DataType])
    array = array.reshape(dataset.RasterYSize, dataset.RasterXSize)
    return array, band.GetNoDataValue(), dataset


def write(path: Path, array: np.ndarray, template) -> None:
    array = np.ascontiguousarray(array.astype("f4"))
    rows, cols = array.shape
    driver = gdal.GetDriverByName("GTiff")
    out = driver.Create(str(path), cols, rows, 1, gdal.GDT_Float32,
                        options=["COMPRESS=LZW", "TILED=YES", "PREDICTOR=3",
                                 "BIGTIFF=IF_SAFER"])
    out.SetGeoTransform(template.GetGeoTransform())
    out.SetProjection(template.GetProjection())
    band = out.GetRasterBand(1)
    band.SetNoDataValue(NODATA)
    band.WriteRaster(0, 0, cols, rows, array.tobytes())
    band.FlushCache()
    valid = array != NODATA
    band.SetStatistics(float(array[valid].min()), float(array[valid].max()),
                       float(array[valid].mean()), float(array[valid].std()))
    out = None
    print(f"  {path.name:52s} {int(valid.sum()):>9,} cells")


def percentile_rank(values: np.ndarray) -> np.ndarray:
    """Rank each value as a percentile of the population, 0 to 100."""
    order = np.argsort(values, kind="stable")
    ranks = np.empty(values.size, dtype="f8")
    ranks[order] = np.arange(values.size, dtype="f8")
    return 100.0 * ranks / max(values.size - 1, 1)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    core, _, _ = read(WORK_GDB, CORE)
    in_core = core > 0

    surfaces, template = {}, None
    for year in YEARS:
        array, nodata, dataset = read(CURRENT_GDB, CURRENT_TEMPLATE.format(year=year))
        template = template or dataset
        surfaces[year] = (array, np.isfinite(array) & (array != nodata))

    print(f"writing to {OUT_DIR}\n")

    domains = {}
    for year in YEARS:
        current, valid = surfaces[year]
        domain = valid & ~in_core & (current > 0)
        domains[year] = domain
        masked = np.where(domain, current, NODATA)
        write(OUT_DIR / f"current_outside_cores_{year}.tif", masked, template)

    # Percentile rank for 2024, so any threshold can be chosen in Pro without
    # recomputing the distribution over a domain that includes the cores.
    current_2024, _ = surfaces[2024]
    domain = domains[2024]
    ranked = np.full(current_2024.shape, NODATA, dtype="f8")
    ranked[domain] = percentile_rank(current_2024[domain])
    write(OUT_DIR / "current_pctrank_outside_cores_2024.tif", ranked, template)

    # Percent change on the domain shared by both endpoints.
    current_2012, _ = surfaces[2012]
    shared = domains[2024] & domains[2012]
    change = np.full(current_2024.shape, NODATA, dtype="f8")
    change[shared] = 100.0 * (current_2024[shared] - current_2012[shared]) / current_2012[shared]
    write(OUT_DIR / "current_change_pct_outside_cores_2012_2024.tif", change, template)

    readme = OUT_DIR / "README.txt"
    readme.write_text(
        "Outside-core current surfaces, written %s\n\n"
        "1 km, Africa Albers Equal Area Conic (ESRI:102022), NoData -9999.\n"
        "Source: final vegetation-balanced resistance with documented finite fences,\n"
        "Circuitscape.jl 5.17.1 pairwise, 253 core pairs per year.\n\n"
        "The 23 input cores are masked out, along with any cell carrying no positive\n"
        "current. This matters: in a pairwise run the cores inject and drain the\n"
        "current, so on the unmasked surfaces they hold the entire top decile and will\n"
        "swamp any colour ramp. Classify these, not the raw surfaces.\n\n"
        "current_outside_cores_<year>.tif\n"
        "    Masked cumulative current. Values are small (median around 2.7e-4), so\n"
        "    classify by percentile rather than equal interval.\n\n"
        "current_pctrank_outside_cores_2024.tif\n"
        "    Each cell's percentile rank, 0 to 100, within the outside-core domain.\n"
        "    Use this if you want to set thresholds directly, e.g. >= 90.\n\n"
        "current_change_pct_outside_cores_2012_2024.tif\n"
        "    Percent change across the shared domain. Median absolute change is about\n"
        "    4.3 percent, 90th percentile about 10.7. Diverge around zero.\n"
        "    Read it against the current surfaces: the low-current periphery can show\n"
        "    large relative change while carrying negligible absolute flow.\n\n"
        "Vector layers already in cheetah_working.gdb:\n"
        "    conservation_priority_paths_temporal      32 least-cost paths\n"
        "    conservation_uncertainty_paths_temporal   13 least-cost paths\n"
        "    cheetah_core_primary_density051_min500    the 23 fixed cores\n"
        "    countries_in_study_extent                 boundaries\n"
        "    wdpa_aug2026_polygon_dissolved            protected areas\n\n"
        "Note: cheetah_core_neighbor_links and final_priority_core_links_paper are\n"
        "straight centroid-to-centroid lines, not routes. Do not map them as corridors.\n"
        % dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        encoding="utf-8")
    print(f"\n  {readme.name}")


if __name__ == "__main__":
    main()
