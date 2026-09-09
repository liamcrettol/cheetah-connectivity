"""Map high final current concentration as candidate structural pinch areas.

Classes are descriptive display quantiles of positive 2024 mean current:
1 = 95th--99th percentile, 2 = >=99th percentile.  They are not biological
thresholds, confirmed cheetah bottlenecks, or final priority designations.
"""
import csv
import datetime as dt
import json
from pathlib import Path

import arcpy
import numpy as np


GDB = r"C:\cheetah\circuitscape\derived\current_final_balanced_fence.gdb"
SOURCE = GDB + r"\current_final_balanced_fence_2024_mean"
OUTPUT = GDB + r"\current_final_candidate_concentration_2024"
CORES = r"C:\cheetah\gdb\cheetah_working.gdb\cheetah_core_primary_density051_min500"
MAP_NAME = "FIG 1 · High-current concentration areas · 2024"
BACKUPS = Path(r"C:\cheetah\backups")
REPORTS = Path(r"C:\cheetah\reports")
NODATA = -9999


def value_key(value):
    while isinstance(value, (list, tuple)) and len(value) == 1:
        value = value[0]
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def style(layer):
    colors = {
        1: ("High current concentration | 95th–99th percentile", {"RGB": [253, 174, 97, 100]}),
        2: ("Highest current concentration | >=99th percentile", {"RGB": [178, 24, 43, 100]}),
    }
    sym = layer.symbology
    sym.updateColorizer("RasterUniqueValueColorizer")
    sym.colorizer.field = "Value"
    layer.symbology = sym
    sym = layer.symbology
    styled = set()
    for group in sym.colorizer.groups:
        for item in group.items:
            key = value_key(item.values)
            if key in colors:
                item.label, item.color = colors[key]
                styled.add(key)
    layer.symbology = sym
    if styled != set(colors):
        print("WARNING: unique-value symbology needs a manual refresh; styled:", sorted(styled))


def make_map(aprx):
    existing = aprx.listMaps(MAP_NAME)
    map_object = existing[0] if existing else aprx.createMap(MAP_NAME, "MAP")
    if existing:
        for layer in list(map_object.listLayers()):
            map_object.removeLayer(layer)
    try:
        map_object.addBasemap("Topographic")
    except Exception:
        print("WARNING: Optional Topographic basemap could not be added")
    concentration = map_object.addDataFromPath(OUTPUT)
    concentration.name = "High-current concentration areas | 2024 modeled current"
    style(concentration)
    core_layer = map_object.addDataFromPath(CORES)
    core_layer.name = "Fixed cheetah density cores"
    try:
        sym = core_layer.symbology
        sym.renderer.symbol.color = {"RGB": [45, 45, 45, 100]}
        sym.renderer.symbol.size = 3.5
        core_layer.symbology = sym
    except Exception:
        pass
    map_object.defaultCamera.setExtent(arcpy.Describe(CORES).extent)
    map_object.defaultCamera.scale *= 1.12


def main():
    for dataset in (SOURCE, CORES):
        if not arcpy.Exists(dataset):
            raise FileNotFoundError(dataset)
    source = arcpy.Raster(SOURCE)
    values = arcpy.RasterToNumPyArray(source, nodata_to_value=np.nan).astype(np.float64, copy=False)
    positive = values[np.isfinite(values) & (values > 0)]
    if positive.size == 0:
        raise RuntimeError("2024 final mean-current raster has no positive cells")
    q95, q99 = (float(np.percentile(positive, 95)), float(np.percentile(positive, 99)))
    classes = np.full(values.shape, NODATA, dtype=np.int32)
    classes[np.isfinite(values) & (values >= q95) & (values < q99)] = 1
    classes[np.isfinite(values) & (values >= q99)] = 2

    aprx = arcpy.mp.ArcGISProject("CURRENT")
    BACKUPS.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUPS / f"Resistance_before_candidate_current_concentration_{stamp}.aprx"
    aprx.saveACopy(str(backup))
    if arcpy.Exists(OUTPUT):
        arcpy.management.Delete(OUTPUT)
    raster = arcpy.NumPyArrayToRaster(
        classes, arcpy.Point(source.extent.XMin, source.extent.YMin),
        source.meanCellWidth, source.meanCellHeight, NODATA,
    )
    raster.save(OUTPUT)
    arcpy.management.DefineProjection(OUTPUT, source.spatialReference)
    arcpy.management.CalculateStatistics(OUTPUT, 1, 1, [], "OVERWRITE")
    arcpy.management.BuildRasterAttributeTable(OUTPUT, "Overwrite")
    del raster
    make_map(aprx)
    aprx.save()

    REPORTS.mkdir(parents=True, exist_ok=True)
    report = REPORTS / f"candidate_current_concentration_2024_{stamp}.json"
    record = {
        "source": SOURCE,
        "output": OUTPUT,
        "positive_current_p95": q95,
        "positive_current_p99": q99,
        "p95_to_p99_cell_count": int((classes == 1).sum()),
        "top_p1_cell_count": int((classes == 2).sum()),
        "interpretation": "Descriptive high-current concentration screen; neither class is a biological cutoff or observed cheetah movement evidence.",
    }
    report.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print("backup:", backup)
    print("positive-current 95th percentile:", q95)
    print("positive-current 99th percentile:", q99)
    print("95th–99th percentile cells:", record["p95_to_p99_cell_count"])
    print("top 1% cells:", record["top_p1_cell_count"])
    print("map:", MAP_NAME)
    print("report:", report)
    print("Complete. One derived display raster/map was created; final current, resistance, and priorities were unchanged.")


if __name__ == "__main__":
    main()
