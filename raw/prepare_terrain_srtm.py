"""Prepare aligned SRTM elevation and slope layers for the cheetah workflow.

Run inside the ArcGIS Pro Python window. The script prefers a native-resolution
DEM named dem_native_30m.tif, but safely falls back to dem_1km.tif. It backs up
the APRX, preserves source data, aligns outputs to snapgrid_1km, creates a slope
summary, and adds results beneath the Cheetah project group.
"""

from datetime import datetime
from pathlib import Path
import csv
import os

import arcpy
import numpy as np
from arcpy.sa import Aggregate, ExtractByMask, Slope


DEM_FOLDERS = [
    Path(r"C:\cheetah\cheetah_gee_exports"),
    Path(r"C:\Users\lcrettol\Downloads"),
    Path(r"C:\Users\lcrettol\Downloads\cheetah_gee_exports"),
    Path(r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah\rasters\gee_exports"),
]
GEE_SLOPE_MEAN = Path(r"C:\Users\lcrettol\Downloads\slope_mean_native_to_1km_wgs84.tif")
GEE_SLOPE_MAX = Path(r"C:\Users\lcrettol\Downloads\slope_max_native_to_1km_wgs84.tif")
WORK_GDB = r"C:\cheetah\gdb\cheetah_working.gdb"
SNAP_RASTER = r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah_connectivity.gdb\snapgrid_1km"
EXTENT_MASK = r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah_connectivity.gdb\extent_buffered"
BACKUP_FOLDER = Path(r"C:\cheetah\backups")
REPORT_FOLDER = Path(r"C:\cheetah\reports")
MAP_NAME = "Map"
PARENT_GROUP = "Cheetah project"
GROUP_NAME = "09 Terrain · SRTM"

ALIGNED_DEM = os.path.join(WORK_GDB, "dem_srtm_1km_aligned")
SLOPE_MEAN = os.path.join(WORK_GDB, "slope_mean_1km")
SLOPE_MAX = os.path.join(WORK_GDB, "slope_max_1km")


def require(path):
    if not arcpy.Exists(str(path)):
        raise FileNotFoundError(f"Required input does not exist: {path}")


def locate_dem():
    """Prefer a native DEM, then locate the downloaded 1 km Drive export."""
    for filename in ("dem_native_30m.tif", "dem_1km.tif", "dem_1km.tif.tiff"):
        for folder in DEM_FOLDERS:
            candidate = folder / filename
            if candidate.exists():
                # Classic TIFF begins II*\x00 or MM\x00*. BigTIFF, which Earth
                # Engine may export, begins II+\x00 or MM\x00+.
                # This prevents a Google sign-in HTML page saved as .tif from
                # being passed to ArcGIS as though it were a raster.
                with candidate.open("rb") as handle:
                    signature = handle.read(4)
                if signature in (b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+"):
                    return candidate
                print(f"skipping invalid TIFF download: {candidate}")
    searched = "\n  ".join(str(folder) for folder in DEM_FOLDERS)
    raise FileNotFoundError(
        "Download dem_1km.tif from Google Drive folder cheetah_gee_exports. "
        f"The script searched:\n  {searched}"
    )


def safe_name(layer):
    try:
        return layer.name
    except Exception:
        return "<unsupported layer>"


def find_group(map_object, name):
    for layer in map_object.listLayers():
        try:
            if layer.isGroupLayer and layer.name == name:
                return layer
        except Exception:
            continue
    return None


def ensure_group(map_object):
    parent = find_group(map_object, PARENT_GROUP)
    if parent is None:
        parent = map_object.createGroupLayer(PARENT_GROUP)
    group = find_group(map_object, GROUP_NAME)
    return group if group else map_object.createGroupLayer(GROUP_NAME, parent)


def replace_output(path):
    if arcpy.Exists(path):
        arcpy.management.Delete(path)


def add_once(map_object, group, dataset):
    dataset_norm = os.path.normcase(os.path.normpath(dataset))
    for layer in map_object.listLayers():
        try:
            if layer.supports("DATASOURCE"):
                source = os.path.normcase(os.path.normpath(layer.dataSource))
                if source == dataset_norm:
                    return layer
        except Exception:
            continue
    layer = map_object.addDataFromPath(dataset)
    map_object.moveLayer(group, layer, "BEFORE")
    return layer


def numeric_property(raster, prop):
    try:
        return float(arcpy.management.GetRasterProperties(raster, prop).getOutput(0))
    except Exception:
        arcpy.management.CalculateStatistics(raster, 1, 1, [], "OVERWRITE")
        return float(arcpy.management.GetRasterProperties(raster, prop).getOutput(0))


def count_valid_and_threshold(raster, threshold=None):
    condition = "VALUE >= -999999" if threshold is None else f"VALUE >= {threshold}"
    result = arcpy.management.GetCount(arcpy.sa.Con(arcpy.sa.Raster(raster) >= (-999999 if threshold is None else threshold), 1))
    return int(result.getOutput(0))


def raster_cell_count(raster, threshold=None):
    # Direct array counting avoids ArcGIS in-memory locks and does not require
    # a raster attribute table. The study raster is small enough for memory.
    array = arcpy.RasterToNumPyArray(raster, nodata_to_value=np.nan)
    valid = np.isfinite(array)
    if threshold is None:
        return int(np.count_nonzero(valid))
    return int(np.count_nonzero(valid & (array >= threshold)))


def write_report(slope_raster, source, method_note):
    REPORT_FOLDER.mkdir(parents=True, exist_ok=True)
    report = REPORT_FOLDER / "terrain_slope_summary.csv"
    total = raster_cell_count(slope_raster)
    rows = []
    for threshold in (5, 10, 20, 30):
        cells = raster_cell_count(slope_raster, threshold)
        rows.append((threshold, cells, 100.0 * cells / total if total else 0.0))
    with report.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["source_dem", str(source)])
        writer.writerow(["method", method_note])
        writer.writerow(["slope_min_degrees", numeric_property(slope_raster, "MINIMUM")])
        writer.writerow(["slope_max_degrees", numeric_property(slope_raster, "MAXIMUM")])
        writer.writerow(["slope_mean_degrees", numeric_property(slope_raster, "MEAN")])
        writer.writerow([])
        writer.writerow(["threshold_degrees", "cells_at_or_above", "percent_of_valid_cells"])
        writer.writerows(rows)
    print(f"report: {report}")
    for threshold, _cells, percent in rows:
        print(f"slope >= {threshold} degrees: {percent:.2f}%")
    return report


def main():
    arcpy.CheckOutExtension("Spatial")
    require(SNAP_RASTER)
    require(EXTENT_MASK)
    source = locate_dem()

    source_desc = arcpy.Describe(str(source))
    source_cell = max(abs(source_desc.meanCellWidth), abs(source_desc.meanCellHeight))
    native_mode = source.name == "dem_native_30m.tif" or source_cell < 500
    print(f"source DEM: {source}")
    print(f"source cell size: {source_cell}")

    aprx = arcpy.mp.ArcGISProject("CURRENT")
    maps = [m for m in aprx.listMaps() if m.name == MAP_NAME]
    if not maps:
        raise RuntimeError(f"Map not found: {MAP_NAME}")
    map_object = maps[0]

    BACKUP_FOLDER.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUP_FOLDER / f"{Path(aprx.filePath).stem}_before_terrain_{stamp}.aprx"
    aprx.saveACopy(str(backup))
    print(f"backup: {backup}")

    target_sr = arcpy.Describe(SNAP_RASTER).spatialReference
    arcpy.env.overwriteOutput = True
    arcpy.env.snapRaster = SNAP_RASTER
    arcpy.env.cellSize = SNAP_RASTER
    arcpy.env.extent = EXTENT_MASK
    arcpy.env.mask = EXTENT_MASK
    arcpy.env.outputCoordinateSystem = target_sr

    for output in (ALIGNED_DEM, SLOPE_MEAN, SLOPE_MAX):
        replace_output(output)

    projected_1km = os.path.join("in_memory", "dem_projected_1km")
    arcpy.management.ProjectRaster(str(source), projected_1km, target_sr, "BILINEAR", 1000)
    ExtractByMask(projected_1km, EXTENT_MASK, "INSIDE").save(ALIGNED_DEM)
    print("created: dem_srtm_1km_aligned")

    if GEE_SLOPE_MEAN.exists() and GEE_SLOPE_MAX.exists():
        # These rasters were summarized from native SRTM in Earth Engine. Here
        # ArcGIS applies the authoritative project CRS, extent, and snap grid.
        projected_mean = os.path.join("in_memory", "slope_mean_projected")
        projected_max = os.path.join("in_memory", "slope_max_projected")
        arcpy.management.ProjectRaster(
            str(GEE_SLOPE_MEAN), projected_mean, target_sr, "BILINEAR", 1000
        )
        arcpy.management.ProjectRaster(
            str(GEE_SLOPE_MAX), projected_max, target_sr, "NEAREST", 1000
        )
        ExtractByMask(projected_mean, EXTENT_MASK, "INSIDE").save(SLOPE_MEAN)
        ExtractByMask(projected_max, EXTENT_MASK, "INSIDE").save(SLOPE_MAX)
        method_note = (
            "Slope derived from native approximately 30 m SRTM in Google Earth "
            "Engine, aggregated to mean and maximum slope near 1 km, then "
            "projected and snapped to the authoritative ArcGIS 1 km grid."
        )
        print("created: slope_mean_1km (native-derived GEE source)")
        print("created: slope_max_1km (native-derived GEE source)")
    elif native_mode:
        # A 100 m intermediate grid keeps terrain structure and permits an exact
        # 10 x 10 aggregation to the 1 km analysis grid.
        projected_100m = os.path.join("in_memory", "dem_projected_100m")
        slope_100m = os.path.join("in_memory", "slope_100m")
        arcpy.management.ProjectRaster(str(source), projected_100m, target_sr, "BILINEAR", 100)
        Slope(projected_100m, "DEGREE", 1, "PLANAR").save(slope_100m)
        Aggregate(slope_100m, 10, "MEAN", "EXPAND", "DATA").save(SLOPE_MEAN)
        Aggregate(slope_100m, 10, "MAXIMUM", "EXPAND", "DATA").save(SLOPE_MAX)
        method_note = "Slope derived at 100 m from native SRTM, then mean and maximum aggregated to 1 km."
        print("created: slope_mean_1km")
        print("created: slope_max_1km")
    else:
        Slope(ALIGNED_DEM, "DEGREE", 1, "PLANAR").save(SLOPE_MEAN)
        method_note = "Slope derived from the supplied 1 km DEM; terrain is smoothed and should be interpreted cautiously."
        print("created: slope_mean_1km (smoothed 1 km source)")
        print("WARNING: export dem_native_30m.tif later if you want the stronger native-resolution method.")

    arcpy.management.CalculateStatistics(ALIGNED_DEM, 1, 1, [], "OVERWRITE")
    arcpy.management.CalculateStatistics(SLOPE_MEAN, 1, 1, [], "OVERWRITE")
    if arcpy.Exists(SLOPE_MAX):
        arcpy.management.CalculateStatistics(SLOPE_MAX, 1, 1, [], "OVERWRITE")
    report_source = (
        f"{GEE_SLOPE_MEAN}; {GEE_SLOPE_MAX}"
        if GEE_SLOPE_MEAN.exists() and GEE_SLOPE_MAX.exists()
        else source
    )
    write_report(SLOPE_MEAN, report_source, method_note)

    group = ensure_group(map_object)
    for dataset in (ALIGNED_DEM, SLOPE_MEAN, SLOPE_MAX):
        if arcpy.Exists(dataset):
            add_once(map_object, group, dataset)
    group.visible = True
    aprx.save()

    print("Complete. Source DEM was unchanged.")
    print("Interpretation reminder: elevation is context; slope is the candidate resistance variable.")
    arcpy.CheckInExtension("Spatial")


if __name__ == "__main__":
    main()
