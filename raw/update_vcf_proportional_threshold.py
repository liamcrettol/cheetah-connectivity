"""Rebuild proportional VCF change rasters using a >=5% baseline threshold."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import arcpy
from arcpy.sa import Raster, SetNull


SOURCE_FOLDER = Path(
    r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah\rasters\gee_exports"
)
OUTPUT_GDB = Path(r"C:\cheetah\gdb\cheetah_working.gdb")
BACKUP_FOLDER = Path(r"C:\cheetah\backups")
PROJECT_GROUP = "Cheetah project"
PROPORTIONAL_GROUP = "08 Continuous change · proportional"
BASELINE_THRESHOLD = 5
PAIRS = ((2012, 2016), (2016, 2020), (2020, 2024), (2012, 2024))
VARIABLES = ("vcf_tree", "vcf_nontree", "vcf_bare")


def one_group(map_object, long_name: str):
    matches = [
        layer for layer in map_object.listLayers()
        if layer.isGroupLayer and layer.longName == long_name
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one group named {long_name!r}; found {len(matches)}.")
    return matches[0]


def remove_map_references(map_object, dataset: str):
    for layer in list(map_object.listLayers()):
        if not layer.supports("DATASOURCE"):
            continue
        try:
            is_target = layer.dataSource.lower() == dataset.lower()
        except Exception:
            is_target = False
        if is_target:
            map_object.removeLayer(layer)


def add_to_group(map_object, group, dataset: str):
    map_object.addDataFromPath(dataset)
    roots = [
        layer for layer in map_object.listLayers()
        if layer.longName == layer.name
        and layer.supports("DATASOURCE")
        and getattr(layer, "dataSource", "").lower() == dataset.lower()
    ]
    if len(roots) != 1:
        raise RuntimeError(f"Could not identify one temporary map reference for {dataset}")
    map_object.addLayerToGroup(group, roots[0], "BOTTOM")
    roots_after = [
        layer for layer in map_object.listLayers()
        if layer.longName == layer.name
        and layer.supports("DATASOURCE")
        and getattr(layer, "dataSource", "").lower() == dataset.lower()
    ]
    if len(roots_after) != 1:
        raise RuntimeError(f"Could not identify one loose map reference for {dataset} after grouping")
    map_object.removeLayer(roots_after[0])


def main() -> int:
    if arcpy.CheckExtension("Spatial") != "Available":
        raise RuntimeError("Spatial Analyst is not available in this ArcGIS Pro session.")
    if not OUTPUT_GDB.exists():
        raise RuntimeError(f"Working geodatabase not found: {OUTPUT_GDB}")

    aprx = arcpy.mp.ArcGISProject("CURRENT")
    map_object = aprx.activeMap
    if map_object is None:
        raise RuntimeError("No active map was found.")
    one_group(map_object, PROJECT_GROUP)
    proportional_group = one_group(map_object, PROJECT_GROUP + "\\" + PROPORTIONAL_GROUP)

    BACKUP_FOLDER.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUP_FOLDER / f"{Path(aprx.filePath).stem}_before_vcf_threshold_{stamp}.aprx"
    aprx.saveACopy(str(backup))
    print(f"backup: {backup}")

    arcpy.CheckOutExtension("Spatial")
    try:
        for variable in VARIABLES:
            for earlier, later in PAIRS:
                baseline_path = SOURCE_FOLDER / f"{variable}_{earlier}_1km.tif"
                comparison_path = SOURCE_FOLDER / f"{variable}_{later}_1km.tif"
                output = str(OUTPUT_GDB / f"p_{variable}_{earlier}_{later}_1km")
                if not arcpy.Exists(str(baseline_path)) or not arcpy.Exists(str(comparison_path)):
                    raise RuntimeError(f"Missing source pair: {baseline_path.name}, {comparison_path.name}")

                remove_map_references(map_object, output)
                if arcpy.Exists(output):
                    arcpy.management.Delete(output)

                baseline = Raster(str(baseline_path))
                comparison = Raster(str(comparison_path))
                proportional = SetNull(
                    baseline < BASELINE_THRESHOLD,
                    ((comparison - baseline) / baseline) * 100,
                )
                proportional.save(output)
                add_to_group(map_object, proportional_group, output)
                print(f"rebuilt: {Path(output).name}")

        aprx.save()
    finally:
        arcpy.CheckInExtension("Spatial")

    print("Complete. Only proportional VCF outputs were replaced; all other layers were unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
