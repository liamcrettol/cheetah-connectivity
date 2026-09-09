"""Create a diagnostic map of the 4,866 common missing-VCF cells.

Class 1 = >=95% both-water classified area in all four snapshots.
Class 2 = >=95% both-land classified area in all four snapshots.
Class 3 = neither persistent classification (unresolved).

The 95% rule is descriptive only. This script does not edit any resistance
surface, path, priority result, source raster, or missing-data policy.
"""
import csv
import datetime as dt
import json
from pathlib import Path

import arcpy
import numpy as np

GDB = Path(r"C:\cheetah\gdb\cheetah_working.gdb")
FRACTIONS = Path(r"C:\cheetah\raw\source_qa\water_class_fractions_v1_20260904")
VCF = Path(r"C:\cheetah\raw\source_qa\vcf_maskpreserved_v2_20260903")
REPORTS = Path(r"C:\cheetah\reports")
BACKUPS = Path(r"C:\cheetah\backups")
OUT = GDB / "vcf_missing_water_context_v1"
YEARS = (2012, 2016, 2020, 2024)
EXPECTED_BANDS = [
    "lw_water_fraction", "lw_land_fraction", "lw_valid_fraction",
    "lc_water_fraction", "lc_wetland_fraction", "lc_barren_fraction",
    "lc_valid_fraction", "both_water_fraction", "both_land_fraction",
    "disagreement_fraction", "both_valid_fraction",
]


def same_grid(raster, reference):
    values = (
        raster.width == reference.width,
        raster.height == reference.height,
        raster.spatialReference.factoryCode == reference.spatialReference.factoryCode,
        abs(raster.meanCellWidth - reference.meanCellWidth) < 0.001,
        abs(raster.meanCellHeight - reference.meanCellHeight) < 0.001,
        abs(raster.extent.XMin - reference.extent.XMin) < 0.001,
        abs(raster.extent.YMax - reference.extent.YMax) < 0.001,
    )
    if not all(values):
        raise RuntimeError("A source is not on the verified 2,310 x 2,200 model grid")


def add_labels(dataset):
    arcpy.management.BuildRasterAttributeTable(str(dataset), "Overwrite")
    names = {field.name.upper() for field in arcpy.ListFields(str(dataset))}
    if "CLASS_NAME" not in names:
        arcpy.management.AddField(str(dataset), "CLASS_NAME", "TEXT", field_length=32)
    if "INTERPRET" not in names:
        arcpy.management.AddField(str(dataset), "INTERPRET", "TEXT", field_length=180)
    labels = {
        1: ("Persistent water context", ">=95% both-water classified area in every snapshot; descriptive, not an adopted barrier"),
        2: ("Persistent land context", ">=95% both-land classified area in every snapshot; missing VCF still needs treatment"),
        3: ("Unresolved / mixed context", "Neither persistent rule met; do not infer water, land, wetland, or permeability"),
    }
    with arcpy.da.UpdateCursor(str(dataset), ["Value", "CLASS_NAME", "INTERPRET"]) as rows:
        for row in rows:
            label = labels.get(int(row[0]))
            if label:
                row[1], row[2] = label
                rows.updateRow(row)


def add_to_map(dataset, aprx):
    maps = aprx.listMaps("Map") or aprx.listMaps()
    if not maps:
        raise RuntimeError("No map exists in the current ArcGIS Pro project")
    map_object = maps[0]
    group_name = "14 Missing VCF · water context"
    groups = [layer for layer in map_object.listLayers() if layer.isGroupLayer and layer.name == group_name]
    group = groups[0] if groups else map_object.createGroupLayer(group_name)
    for layer in list(map_object.listLayers()):
        try:
            if not layer.isGroupLayer and layer.name == OUT.name:
                map_object.removeLayer(layer)
        except Exception:
            pass
    loose = map_object.addDataFromPath(str(dataset))
    map_object.addLayerToGroup(group, loose, "TOP")
    try:
        map_object.removeLayer(loose)
    except Exception:
        pass
    candidates = [layer for layer in map_object.listLayers() if not layer.isGroupLayer and layer.name == OUT.name]
    if candidates:
        layer = candidates[0]
        try:
            sym = layer.symbology
            sym.updateColorizer("RasterUniqueValueColorizer")
            colors = {1: {"RGB": [44, 123, 182, 100]},
                      2: {"RGB": [49, 163, 84, 100]},
                      3: {"RGB": [253, 174, 97, 100]}}
            labels = {1: "Persistent water context", 2: "Persistent land context",
                      3: "Unresolved / mixed context"}
            for sym_group in sym.colorizer.groups:
                for item in sym_group.items:
                    raw_value = item.values
                    while isinstance(raw_value, (list, tuple)) and len(raw_value) == 1:
                        raw_value = raw_value[0]
                    try:
                        value = int(float(raw_value))
                    except (TypeError, ValueError):
                        text_value = str(raw_value).lower()
                        value = (1 if "water" in text_value else
                                 2 if "land" in text_value else
                                 3 if "unresolved" in text_value or "mixed" in text_value else -1)
                    if value in colors:
                        item.color = colors[value]
                        item.label = labels[value]
            layer.symbology = sym
        except Exception as exc:
            print("WARNING: diagnostic raster added, but automatic colors were not applied:", exc)
        layer.visible = True
    group.visible = True
    return map_object.name


def main():
    arcpy.CheckOutExtension("Spatial")
    REPORTS.mkdir(parents=True, exist_ok=True)
    BACKUPS.mkdir(parents=True, exist_ok=True)
    reference_path = GDB / "resistance_temporal_veg_balanced_2012"
    if not arcpy.Exists(str(reference_path)):
        raise FileNotFoundError(reference_path)
    reference = arcpy.Raster(str(reference_path))
    support = arcpy.RasterToNumPyArray(arcpy.sa.IsNull(reference), nodata_to_value=1) == 0
    missing = None
    all_fractions = []
    for year in YEARS:
        vcf_path = VCF / f"vcf_maskpreserved_common_v2_{year}.tif"
        water_path = FRACTIONS / f"water_class_fractions_v1_{year}.tif"
        if not vcf_path.exists() or not water_path.exists():
            raise FileNotFoundError(f"Missing source for {year}: {vcf_path} or {water_path}")
        vcf_raster = arcpy.Raster(str(vcf_path))
        water_raster = arcpy.Raster(str(water_path))
        same_grid(vcf_raster, reference)
        same_grid(water_raster, reference)
        if list(water_raster.bandNames) != EXPECTED_BANDS:
            raise RuntimeError(f"Unexpected band order for {year}: {water_raster.bandNames}")
        vcf_data = arcpy.RasterToNumPyArray(vcf_raster, nodata_to_value=-9999)
        year_missing = support & (vcf_data[3] == 0)
        if missing is None:
            missing = year_missing
        elif not np.array_equal(missing, year_missing):
            raise RuntimeError("The common missing-VCF mask differs among years")
        all_fractions.append(arcpy.RasterToNumPyArray(water_raster, nodata_to_value=-9999))
    if int(missing.sum()) != 4866:
        raise RuntimeError(f"Expected 4,866 common missing cells; found {int(missing.sum()):,}")
    fractions = np.stack(all_fractions)
    persistent_water = missing & np.all(fractions[:, 7] >= 0.95, axis=0)
    persistent_land = missing & np.all(fractions[:, 8] >= 0.95, axis=0)
    if np.any(persistent_water & persistent_land):
        raise RuntimeError("Water and land classes overlap")
    unresolved = missing & ~(persistent_water | persistent_land)
    result = np.zeros(missing.shape, dtype=np.uint8)
    result[persistent_water] = 1
    result[persistent_land] = 2
    result[unresolved] = 3
    if arcpy.Exists(str(OUT)):
        arcpy.management.Delete(str(OUT))
    out_raster = arcpy.NumPyArrayToRaster(
        result, arcpy.Point(reference.extent.XMin, reference.extent.YMin),
        reference.meanCellWidth, reference.meanCellHeight, 0,
    )
    out_raster.save(str(OUT))
    arcpy.management.DefineProjection(str(OUT), reference.spatialReference)
    arcpy.management.CalculateStatistics(str(OUT))
    add_labels(OUT)
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    summary = {
        "created": timestamp, "output": str(OUT), "threshold": 0.95,
        "missing_cells": int(missing.sum()),
        "persistent_water_context": int(persistent_water.sum()),
        "persistent_land_context": int(persistent_land.sum()),
        "unresolved_or_mixed_context": int(unresolved.sum()),
        "interpretation": "Diagnostic classes only; no resistance or missing-data policy changed.",
    }
    report = REPORTS / f"vcf_missing_water_context_map_{timestamp}.json"
    report.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    backup = BACKUPS / f"Resistance_before_missing_water_context_{timestamp}.aprx"
    aprx.saveACopy(str(backup))
    map_name = add_to_map(OUT, aprx)
    aprx.save()
    print(json.dumps(summary, indent=2))
    print("map:", map_name)
    print("backup:", backup)
    print("report:", report)
    print("Complete. Diagnostic context only; no resistance surface or analysis result was changed.")


if __name__ == "__main__":
    main()
