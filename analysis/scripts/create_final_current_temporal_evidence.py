"""Create descriptive temporal evidence layers from final normalized current.

High-current screening uses each year's 90th percentile of *positive* mean
current.  This identifies relative modeled concentration, not a biological
threshold or observed corridor.  Outputs support map review and reporting; they
do not replace the existing link-based conservation-priority workflow.
"""

import datetime as task_datetime
from pathlib import Path
import csv
import os

import arcpy
import numpy as np


GDB = r"C:\cheetah\circuitscape\derived\current_final_balanced_fence.gdb"
REPORTS = Path(r"C:\cheetah\reports")
YEARS = (2012, 2016, 2020, 2024)
PARENT_NAME = "Cheetah project"
GROUP_NAME = "18 Current flow · temporal evidence"
NODATA = -9999.0


def source(year):
    path = os.path.join(GDB, f"current_final_balanced_fence_{year}_mean")
    if not arcpy.Exists(path):
        raise FileNotFoundError(f"Missing normalized final current: {path}")
    return path


def remove_dataset_layers(map_object, dataset):
    wanted = os.path.normcase(os.path.normpath(dataset))
    for layer in list(map_object.listLayers()):
        try:
            if layer.supports("DATASOURCE") and os.path.normcase(os.path.normpath(layer.dataSource)) == wanted:
                map_object.removeLayer(layer)
        except Exception:
            pass


def target_group(map_object):
    parents = [x for x in map_object.listLayers() if x.isGroupLayer and x.longName == PARENT_NAME]
    if len(parents) != 1:
        raise RuntimeError(f"Expected exactly one {PARENT_NAME!r} group; found {len(parents)}")
    full = PARENT_NAME + "\\" + GROUP_NAME
    existing = [x for x in map_object.listLayers() if x.isGroupLayer and x.longName == full]
    return existing[0] if existing else map_object.createGroupLayer(GROUP_NAME, parents[0])


def add_grouped(map_object, group, dataset, label, visible=False):
    loose = map_object.addDataFromPath(dataset)
    added = map_object.addLayerToGroup(group, loose, "BOTTOM")
    map_object.removeLayer(loose)
    if not added:
        raise RuntimeError(f"Could not add {dataset}")
    added[0].name = label
    added[0].visible = visible


def save_array(array, output, grid, spatial_reference):
    remove_dataset_layers(grid["map"], output)
    if arcpy.Exists(output):
        arcpy.management.Delete(output)
    raster = arcpy.NumPyArrayToRaster(
        array.astype(np.float32), arcpy.Point(grid["xmin"], grid["ymin"]),
        grid["cell_width"], grid["cell_height"], NODATA,
    )
    raster.save(output)
    arcpy.management.DefineProjection(output, spatial_reference)
    arcpy.management.CalculateStatistics(output, 1, 1, [], "OVERWRITE")
    del raster


def main():
    arrays, valid_masks, thresholds = {}, {}, {}
    reference = arcpy.Raster(source(2012))
    e = reference.extent
    spatial_reference = reference.spatialReference
    grid = {"columns": int(reference.width), "rows": int(reference.height),
            "xmin": float(e.XMin), "ymin": float(e.YMin),
            "cell_width": float(reference.meanCellWidth), "cell_height": float(reference.meanCellHeight)}
    for year in YEARS:
        raster = arcpy.Raster(source(year))
        if (raster.width, raster.height, raster.meanCellWidth, raster.meanCellHeight) != (
            reference.width, reference.height, reference.meanCellWidth, reference.meanCellHeight):
            raise RuntimeError(f"{year}: current grid differs from 2012")
        values = arcpy.RasterToNumPyArray(raster, nodata_to_value=np.nan).astype(np.float64, copy=False)
        valid = np.isfinite(values)
        positive = values[valid & (values > 0)]
        if positive.size == 0:
            raise RuntimeError(f"{year}: no positive current cells")
        arrays[year], valid_masks[year] = values, valid
        thresholds[year] = float(np.percentile(positive, 90))
        print(f"{year}: positive-current 90th percentile={thresholds[year]:.8g}")

    support = np.logical_and.reduce([valid_masks[y] for y in YEARS])
    high = {year: support & (arrays[year] >= thresholds[year]) for year in YEARS}
    count = np.sum(np.stack([high[y] for y in YEARS]), axis=0).astype(np.float32)

    # 0--4 count of snapshots in which a cell is in the annual high-current decile.
    high_count = np.full(count.shape, NODATA, dtype=np.float32)
    high_count[support] = count[support]
    # Categorical endpoint comparison: 1 persistent high; 2 emerging; 3 lost;
    # 4 high only in an intermediate snapshot; 0 neither endpoint high.
    category = np.full(count.shape, NODATA, dtype=np.float32)
    category[support] = 0
    category[support & high[2012] & high[2024]] = 1
    category[support & ~high[2012] & high[2024]] = 2
    category[support & high[2012] & ~high[2024]] = 3
    category[support & ~high[2012] & ~high[2024] & (count > 0)] = 4
    change = np.full(count.shape, NODATA, dtype=np.float32)
    change[support] = (arrays[2024][support] - arrays[2012][support]).astype(np.float32)

    aprx = arcpy.mp.ArcGISProject("CURRENT")
    maps = aprx.listMaps("Map")
    map_object = maps[0] if maps else aprx.activeMap
    if map_object is None:
        raise RuntimeError("No active ArcGIS Pro map found")
    backup_dir = Path(r"C:\cheetah\backups")
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = task_datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = backup_dir / f"{Path(aprx.filePath).stem}_before_final_current_temporal_evidence_{stamp}.aprx"
    aprx.saveACopy(str(backup))
    print(f"backup: {backup}")
    grid["map"] = map_object
    group = target_group(map_object)

    outputs = {
        "current_final_high_snapshot_count_2012_2024": high_count,
        "current_final_high_class_2012_2024": category,
        "current_final_mean_change_2012_2024": change,
    }
    labels = {
        "current_final_high_snapshot_count_2012_2024": "High-current presence | snapshots in annual top decile (0–4)",
        "current_final_high_class_2012_2024": "High-current endpoint class | 1 persistent, 2 emerging, 3 lost, 4 intermediate-only",
        "current_final_mean_change_2012_2024": "Mean current change | 2024 minus 2012",
    }
    for name, array in outputs.items():
        out = os.path.join(GDB, name)
        save_array(array, out, grid, spatial_reference)
        add_grouped(map_object, group, out, labels[name], name.endswith("high_class_2012_2024"))
        print(f"created: {name}")

    rows = []
    for year in YEARS:
        rows.append({"year": year, "positive_current_90th_percentile": thresholds[year],
                     "positive_high_current_cells": int(high[year].sum()),
                     "common_support_cells": int(support.sum())})
    summary = {
        "persistent_high_both_endpoints": int((support & high[2012] & high[2024]).sum()),
        "emerging_high_2024": int((support & ~high[2012] & high[2024]).sum()),
        "lost_high_since_2012": int((support & high[2012] & ~high[2024]).sum()),
        "intermediate_only_high": int((support & ~high[2012] & ~high[2024] & (count > 0)).sum()),
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    report = REPORTS / f"final_current_temporal_evidence_{stamp}.csv"
    with report.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
        handle.write("\nclass,cell_count\n")
        for name, amount in summary.items():
            handle.write(f"{name},{amount}\n")
    aprx.save()
    print(f"summary: {report}")
    print("Complete. High-current categories are descriptive screening evidence, not biological corridor classes or final conservation priorities.")


if __name__ == "__main__":
    main()
