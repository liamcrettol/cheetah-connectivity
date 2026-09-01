"""Create the fixed flare mask efficiently by filtering sites before buffering."""

from __future__ import annotations

import urllib.request
from datetime import datetime
from pathlib import Path

import arcpy
import pandas as pd


DATA_URL = (
    "https://thedocs.worldbank.org/en/doc/"
    "b34e0c054bb3fe3695e70154c28eef3f-0400072026/related/"
    "Flare-Volume-Estimates-by-individual-Flare-Location-2012-2025.xlsx"
)
RAW_FOLDER = Path(r"C:\cheetah\raw\gas_flares")
WORKING_GDB = Path(r"C:\cheetah\gdb\cheetah_working.gdb")
EXTENT_MASK = Path(
    r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah_connectivity.gdb\extent_buffered"
)
BACKUP_FOLDER = Path(r"C:\cheetah\backups")
PROJECT_GROUP = "Cheetah project"
GROUP_NAME = "08 Nighttime lights · flare mask"
TARGET_CRS = arcpy.SpatialReference(102022)
TEMP_WGS84 = "_flare_sites_wgs84_temp"
TEMP_AEA = "_flare_sites_aea_temp"
TEMP_BUFFER = "_flare_buffer_temp"
SITES_NEAR_EXTENT = "gas_flare_sites_near_extent_5km"
FINAL_MASK = "gas_flare_mask_5km"
# Names created by the earlier, global-buffer version.  Remove them so the
# Contents pane has only the efficient workflow's final products.
LEGACY_PARTIAL_OUTPUTS = (
    "gas_flare_sites_wgs84",
    "gas_flare_sites_aea",
    "gas_flare_buffer_5km",
)


def one_group(map_object, long_name: str):
    matches = [
        layer for layer in map_object.listLayers()
        if layer.isGroupLayer and layer.longName == long_name
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one group named {long_name!r}; found {len(matches)}.")
    return matches[0]


def find_or_create_group(map_object, parent):
    wanted = parent.longName + "\\" + GROUP_NAME
    matches = [layer for layer in map_object.listLayers() if layer.isGroupLayer and layer.longName == wanted]
    if len(matches) > 1:
        raise RuntimeError(f"More than one group named {wanted!r} exists.")
    return matches[0] if matches else map_object.createGroupLayer(GROUP_NAME, parent)


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


def delete_dataset(map_object, dataset: str):
    remove_map_references(map_object, dataset)
    if arcpy.Exists(dataset):
        arcpy.management.Delete(dataset)


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
    if not WORKING_GDB.exists() or not arcpy.Exists(str(EXTENT_MASK)):
        raise RuntimeError("The project working geodatabase or study extent is unavailable.")

    RAW_FOLDER.mkdir(parents=True, exist_ok=True)
    workbook = RAW_FOLDER / "worldbank_flare_locations_2012_2025.xlsx"
    site_csv = RAW_FOLDER / "worldbank_flare_sites_union_2012_2024.csv"
    if not workbook.exists():
        print("downloading World Bank flare-location workbook")
        urllib.request.urlretrieve(DATA_URL, workbook)

    table = pd.read_excel(workbook)
    active = table[list(range(2012, 2025))].fillna(0).gt(0).any(axis=1)
    sites = table.loc[active, ["Flare id", "Country", "Latitude", "Longitude", "Location", "Field Type"]].copy()
    sites.columns = ["flare_id", "country", "latitude", "longitude", "location", "field_type"]
    sites.to_csv(site_csv, index=False)
    print(f"global union flare sites: {len(sites)}")

    aprx = arcpy.mp.ArcGISProject("CURRENT")
    map_object = aprx.activeMap
    if map_object is None:
        raise RuntimeError("No active map was found.")
    project_group = one_group(map_object, PROJECT_GROUP)
    group = find_or_create_group(map_object, project_group)

    BACKUP_FOLDER.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUP_FOLDER / f"{Path(aprx.filePath).stem}_before_fast_flare_mask_{stamp}.aprx"
    aprx.saveACopy(str(backup))
    print(f"backup: {backup}")

    temp_wgs84 = str(WORKING_GDB / TEMP_WGS84)
    temp_aea = str(WORKING_GDB / TEMP_AEA)
    temp_buffer = str(WORKING_GDB / TEMP_BUFFER)
    near_sites = str(WORKING_GDB / SITES_NEAR_EXTENT)
    final_mask = str(WORKING_GDB / FINAL_MASK)
    for dataset in (temp_wgs84, temp_aea, temp_buffer, near_sites, final_mask):
        delete_dataset(map_object, dataset)
    for name in LEGACY_PARTIAL_OUTPUTS:
        delete_dataset(map_object, str(WORKING_GDB / name))

    original_add_outputs = arcpy.env.addOutputsToMap
    arcpy.env.addOutputsToMap = False
    try:
        arcpy.management.XYTableToPoint(str(site_csv), temp_wgs84, "longitude", "latitude", coordinate_system=arcpy.SpatialReference(4326))
        arcpy.management.Project(temp_wgs84, temp_aea, TARGET_CRS)
        arcpy.management.MakeFeatureLayer(temp_aea, "flare_sites_for_selection")
        arcpy.management.SelectLayerByLocation(
            "flare_sites_for_selection", "WITHIN_A_DISTANCE", str(EXTENT_MASK), "5000 Meters"
        )
        arcpy.management.CopyFeatures("flare_sites_for_selection", near_sites)
        near_count = int(arcpy.management.GetCount(near_sites).getOutput(0))
        print(f"flare sites within 5 km of the study extent: {near_count}")
        if near_count == 0:
            raise RuntimeError("No flare sites fall within 5 km of the study extent.")
        arcpy.analysis.Buffer(near_sites, temp_buffer, "5000 Meters", dissolve_option="ALL", method="PLANAR")
        arcpy.analysis.Clip(temp_buffer, str(EXTENT_MASK), final_mask)
    finally:
        arcpy.env.addOutputsToMap = original_add_outputs

    delete_dataset(map_object, temp_wgs84)
    delete_dataset(map_object, temp_aea)
    delete_dataset(map_object, temp_buffer)
    add_to_group(map_object, group, near_sites)
    add_to_group(map_object, group, final_mask)
    aprx.save()

    print(f"mask features after dissolve and clipping: {arcpy.management.GetCount(final_mask).getOutput(0)}")
    print(f"mask: {final_mask}")
    print("Complete. Lights were not changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
