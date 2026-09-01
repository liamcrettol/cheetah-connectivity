"""Create a transparent, literature-informed terrain resistance surface.

Run inside the ArcGIS Pro Python window. The transformation assigns resistance
1 through 10: slopes <=10 degrees remain 1, resistance increases linearly from
10 to 30 degrees, and slopes >=30 degrees are capped at 10. Source rasters are
not changed.
"""

from datetime import datetime
from pathlib import Path
import csv
import os

import arcpy
from arcpy.sa import Con, IsNull, Raster, SetNull


WORK_GDB = r"C:\cheetah\gdb\cheetah_working.gdb"
SLOPE_MEAN = os.path.join(WORK_GDB, "slope_mean_1km")
OUTPUT = os.path.join(WORK_GDB, "terrain_resistance_1_10")
SNAP_RASTER = r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah_connectivity.gdb\snapgrid_1km"
EXTENT_MASK = r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah_connectivity.gdb\extent_buffered"
BACKUP_FOLDER = Path(r"C:\cheetah\backups")
REPORT_FOLDER = Path(r"C:\cheetah\reports")
MAP_NAME = "Map"
PARENT_GROUP = "Cheetah project"
GROUP_NAME = "09 Terrain · SRTM"


def require(path):
    if not arcpy.Exists(path):
        raise FileNotFoundError(f"Required input does not exist: {path}")


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


def add_once(map_object, group, dataset):
    wanted = os.path.normcase(os.path.normpath(dataset))
    for layer in map_object.listLayers():
        try:
            if layer.supports("DATASOURCE"):
                existing = os.path.normcase(os.path.normpath(layer.dataSource))
                if existing == wanted:
                    return layer
        except Exception:
            continue
    layer = map_object.addDataFromPath(dataset)
    map_object.moveLayer(group, layer, "BEFORE")
    return layer


def write_report():
    REPORT_FOLDER.mkdir(parents=True, exist_ok=True)
    report = REPORT_FOLDER / "terrain_resistance_decision.csv"
    with report.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["parameter", "value"])
        writer.writerow(["input", SLOPE_MEAN])
        writer.writerow(["output", OUTPUT])
        writer.writerow(["resistance_min", 1])
        writer.writerow(["resistance_max", 10])
        writer.writerow(["no_penalty_through_degrees", 10])
        writer.writerow(["linear_increase_ends_degrees", 30])
        writer.writerow(["formula", "1 + 9 * clamp((slope_degrees - 10) / 20, 0, 1)"])
        writer.writerow([
            "interpretation",
            "Conservative transferred assumption: low-to-intermediate slopes remain permeable; steep terrain progressively raises movement cost.",
        ])
        writer.writerow([
            "literature_caution",
            "Some cheetah research reports selection for moderately rugged, hilly, or mountainous terrain. Test alternate terrain responses during sensitivity analysis.",
        ])
        writer.writerow([
            "main_use",
            "Use slope_mean_1km for the primary model; retain slope_max_1km as supplementary sensitivity context.",
        ])
    print(f"report: {report}")


def main():
    arcpy.CheckOutExtension("Spatial")
    require(SLOPE_MEAN)
    require(SNAP_RASTER)
    require(EXTENT_MASK)

    aprx = arcpy.mp.ArcGISProject("CURRENT")
    maps = [item for item in aprx.listMaps() if item.name == MAP_NAME]
    if not maps:
        raise RuntimeError(f"Map not found: {MAP_NAME}")
    map_object = maps[0]

    BACKUP_FOLDER.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUP_FOLDER / f"{Path(aprx.filePath).stem}_before_terrain_resistance_{stamp}.aprx"
    aprx.saveACopy(str(backup))
    print(f"backup: {backup}")

    arcpy.env.overwriteOutput = True
    arcpy.env.snapRaster = SNAP_RASTER
    arcpy.env.cellSize = SNAP_RASTER
    arcpy.env.extent = EXTENT_MASK
    arcpy.env.mask = EXTENT_MASK
    arcpy.env.outputCoordinateSystem = arcpy.Describe(SNAP_RASTER).spatialReference

    if arcpy.Exists(OUTPUT):
        arcpy.management.Delete(OUTPUT)

    slope = Raster(SLOPE_MEAN)
    scaled = Con(slope <= 10, 0.0, Con(slope >= 30, 1.0, (slope - 10.0) / 20.0))
    resistance = SetNull(IsNull(slope), 1.0 + 9.0 * scaled)
    resistance.save(OUTPUT)
    del resistance, scaled, slope

    arcpy.management.CalculateStatistics(OUTPUT, 1, 1, [], "OVERWRITE")
    print("created: terrain_resistance_1_10")
    print("  <=10 degrees: resistance 1")
    print("  10-30 degrees: continuous increase from 1 to 10")
    print("  >=30 degrees: resistance 10")

    group = ensure_group(map_object)
    layer = add_once(map_object, group, OUTPUT)
    layer.visible = True
    group.visible = True
    write_report()
    aprx.save()

    print("Complete. Slope inputs were unchanged.")
    print("Keep this terrain component provisional until sensitivity testing.")
    arcpy.CheckInExtension("Spatial")


if __name__ == "__main__":
    main()
