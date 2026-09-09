"""Build the four final, documented-fence resistance surfaces.

This is the production structural-connectivity input set:
  temporal vegetation-balanced resistance x documented, finite fence multiplier

The VCF all-zero triplets are deliberately retained as finite values in the
existing vegetation transform.  The accompanying zero-triplet audit shows that
most are persistent water-context cells; it does not establish permanent water
barriers or a cheetah-specific water-permeability coefficient.  Therefore this
script does not impose a water barrier or alter source VCF rasters.

Run in the ArcGIS Pro Python window.  It creates four new rasters, backs up the
open project before changing its Contents pane, and writes a reproducibility
report.  It never changes input rasters, cores, fences, or prior scenarios.
"""

from datetime import datetime
from pathlib import Path
import csv
import json
import os

import arcpy
from arcpy.sa import Raster


GDB = r"C:\cheetah\gdb\cheetah_working.gdb"
SOURCE_GDB = r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah_connectivity.gdb"
REPORTS = Path(r"C:\cheetah\reports")
YEARS = (2012, 2016, 2020, 2024)
FENCE_MULTIPLIER = os.path.join(GDB, "fence_multiplier_main_kruger_documented_1km")
CORES = os.path.join(GDB, "cheetah_core_primary_density051_min500_1km")
PARENT_GROUP = "Cheetah project"
TARGET_GROUP = "13 Resistance surfaces · final"


def locate(name):
    for candidate in (os.path.join(GDB, name), os.path.join(SOURCE_GDB, name)):
        if arcpy.Exists(candidate):
            return candidate
    raise FileNotFoundError(f"Missing {name}. Searched {GDB} and {SOURCE_GDB}")


def grid(dataset):
    r = arcpy.Raster(dataset)
    e = r.extent
    return (int(r.width), int(r.height), float(r.meanCellWidth), float(r.meanCellHeight),
            float(e.XMin), float(e.YMin), float(e.XMax), float(e.YMax),
            int(r.spatialReference.factoryCode or 0))


def same_grid(left, right, tolerance=0.001):
    if left[:2] != right[:2] or left[-1] != right[-1]:
        return False
    return all(abs(a - b) <= tolerance for a, b in zip(left[2:-1], right[2:-1]))


def raster_property(dataset, name):
    try:
        return float(arcpy.management.GetRasterProperties(dataset, name).getOutput(0))
    except Exception:
        arcpy.management.CalculateStatistics(dataset, 1, 1, [], "OVERWRITE")
        return float(arcpy.management.GetRasterProperties(dataset, name).getOutput(0))


def remove_dataset_layers(map_object, dataset):
    wanted = os.path.normcase(os.path.normpath(dataset))
    for layer in list(map_object.listLayers()):
        try:
            if layer.supports("DATASOURCE") and os.path.normcase(os.path.normpath(layer.dataSource)) == wanted:
                map_object.removeLayer(layer)
        except Exception:
            pass


def target_group(map_object):
    parents = [layer for layer in map_object.listLayers()
               if layer.isGroupLayer and layer.longName == PARENT_GROUP]
    if len(parents) != 1:
        raise RuntimeError(f"Expected exactly one {PARENT_GROUP!r} group; found {len(parents)}")
    full_name = PARENT_GROUP + "\\" + TARGET_GROUP
    existing = [layer for layer in map_object.listLayers()
                if layer.isGroupLayer and layer.longName == full_name]
    return existing[0] if existing else map_object.createGroupLayer(TARGET_GROUP, parents[0])


def add_grouped(map_object, group_layer, dataset):
    loose = map_object.addDataFromPath(dataset)
    added = map_object.addLayerToGroup(group_layer, loose, "BOTTOM")
    map_object.removeLayer(loose)
    if not added:
        raise RuntimeError(f"Could not add {dataset} to {group_layer.longName}")
    added[0].visible = False


def backup(aprx):
    folder = Path(r"C:\cheetah\backups")
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = folder / f"{Path(aprx.filePath).stem}_before_final_balanced_fence_{stamp}.aprx"
    aprx.saveACopy(str(path))
    print(f"backup: {path}")


def main():
    arcpy.CheckOutExtension("Spatial")
    arcpy.env.overwriteOutput = True
    fence = FENCE_MULTIPLIER
    if not arcpy.Exists(fence):
        raise FileNotFoundError(f"Missing documented fence multiplier: {fence}")
    if not arcpy.Exists(CORES):
        raise FileNotFoundError(f"Missing fixed cores: {CORES}")

    bases = {year: locate(f"resistance_temporal_veg_balanced_{year}") for year in YEARS}
    reference_grid = grid(bases[2012])
    for label, dataset in [("documented fence multiplier", fence), ("fixed cores", CORES), *bases.items()]:
        if not same_grid(reference_grid, grid(dataset)):
            raise RuntimeError(f"Grid mismatch before final build: {label}: {grid(dataset)}")

    arcpy.env.snapRaster = bases[2012]
    arcpy.env.cellSize = bases[2012]
    arcpy.env.extent = arcpy.Describe(bases[2012]).extent
    arcpy.env.mask = bases[2012]
    arcpy.env.outputCoordinateSystem = arcpy.Describe(bases[2012]).spatialReference

    aprx = arcpy.mp.ArcGISProject("CURRENT")
    maps = aprx.listMaps("Map")
    map_object = maps[0] if maps else aprx.activeMap
    if map_object is None:
        raise RuntimeError("No map named 'Map' or active map found")
    backup(aprx)
    scenario_group = target_group(map_object)

    records = []
    core_ids = sorted({int(value) for (value,) in arcpy.da.SearchCursor(CORES, ["Value"])})
    if len(core_ids) != 23:
        raise RuntimeError(f"Expected 23 fixed core IDs; found {len(core_ids)}")

    for year, base in bases.items():
        name = f"resistance_final_balanced_fence_documented_{year}"
        output = os.path.join(GDB, name)
        remove_dataset_layers(map_object, output)
        if arcpy.Exists(output):
            arcpy.management.Delete(output)

        # The multiplier is already the cell-wise maximum of KAZA and the
        # documented Kruger fence component, so overlaps are never multiplied twice.
        (Raster(base) * Raster(fence)).save(output)
        arcpy.management.CalculateStatistics(output, 1, 1, [], "OVERWRITE")
        if not same_grid(reference_grid, grid(output)):
            raise RuntimeError(f"Output grid mismatch: {name}")
        # Fast, exact support test: each core must intersect finite output data.
        missing_cores = []
        output_array = arcpy.RasterToNumPyArray(output, nodata_to_value=-3.4e38)
        cores_array = arcpy.RasterToNumPyArray(CORES, nodata_to_value=-9999)
        for core_id in core_ids:
            if not ((cores_array == core_id) & (output_array > -3e38)).any():
                missing_cores.append(core_id)
        if missing_cores:
            raise RuntimeError(f"{name} excludes fixed cores: {missing_cores}")
        del output_array, cores_array
        add_grouped(map_object, scenario_group, output)
        record = {
            "year": year,
            "output": output,
            "minimum": raster_property(output, "MINIMUM"),
            "maximum": raster_property(output, "MAXIMUM"),
            "fence_multiplier_minimum": raster_property(fence, "MINIMUM"),
            "fence_multiplier_maximum": raster_property(fence, "MAXIMUM"),
            "fixed_cores_retained": len(core_ids),
            "vcf_zero_policy": "Retained finite midpoint vegetation score (5.5/10); persistent all-zero VCF cells are water-context uncertainty, not permanent barriers.",
            "scenario": "vegetation-balanced (0.60 anthropogenic, 0.20 vegetation, 0.20 terrain) x finite documented KAZA+Kruger fence multiplier",
        }
        records.append(record)
        print(f"created: {name}")

    REPORTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = REPORTS / f"final_balanced_fence_resistance_register_{stamp}.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    json_path = REPORTS / f"final_balanced_fence_resistance_register_{stamp}.json"
    json_path.write_text(json.dumps({
        "created": datetime.now().isoformat(timespec="seconds"),
        "purpose": "Final structural-connectivity resistance inputs; not calibrated empirical movement resistance.",
        "grid": reference_grid,
        "fixed_core_count": len(core_ids),
        "water_context_policy": "No permanent water barrier introduced. VCF all-zero triplets remain finite in the baseline; audit found 169283 of 174975 persistent all-zero triplets (96.7%) in persistent water-class context and 5692 unresolved/mixed.",
        "fence_policy": "KAZA and documented Kruger fence penalties are finite/crossable and combined with cell-wise maximum, avoiding a double penalty where they overlap.",
        "records": records,
    }, indent=2), encoding="utf-8")
    aprx.save()
    print(f"registered: {csv_path}")
    print(f"method record: {json_path}")
    print("Complete. Four final resistance surfaces were created; source rasters and previous scenarios were unchanged.")


if __name__ == "__main__":
    main()
