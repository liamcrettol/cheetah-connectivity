"""Download World Bank flare locations and create a fixed 2012-2024 5-km mask.

The mask is a union of all sites with nonzero flare volume in any year from
2012 through 2024. It is deliberately fixed across snapshots so that the
nighttime-lights comparison has the same valid footprint in every year.
"""

from __future__ import annotations

import argparse
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
POINTS_WGS84 = "gas_flare_sites_wgs84"
POINTS_AEA = "gas_flare_sites_aea"
BUFFER = "gas_flare_buffer_5km"
CLIPPED_MASK = "gas_flare_mask_5km"
TARGET_CRS = arcpy.SpatialReference(102022)


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


def add_to_group(map_object, group, dataset: str):
    existing = [
        layer for layer in map_object.listLayers()
        if layer.longName.startswith(group.longName + "\\")
        and layer.supports("DATASOURCE")
        and getattr(layer, "dataSource", "").lower() == dataset.lower()
    ]
    if existing:
        return
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


def delete_if_requested(map_object, dataset: str, replace: bool):
    if arcpy.Exists(dataset):
        if not replace:
            raise RuntimeError(f"Output already exists: {dataset}. Rerun with --replace to rebuild it.")
        remove_map_references(map_object, dataset)
        arcpy.management.Delete(dataset)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--map-name", default="Map")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    if not WORKING_GDB.exists():
        raise RuntimeError(f"Working geodatabase not found: {WORKING_GDB}")
    if not arcpy.Exists(str(EXTENT_MASK)):
        raise RuntimeError(f"Study extent not found: {EXTENT_MASK}")

    RAW_FOLDER.mkdir(parents=True, exist_ok=True)
    workbook = RAW_FOLDER / "worldbank_flare_locations_2012_2025.xlsx"
    site_csv = RAW_FOLDER / "worldbank_flare_sites_union_2012_2024.csv"
    print("downloading World Bank flare-location workbook")
    urllib.request.urlretrieve(DATA_URL, workbook)

    table = pd.read_excel(workbook)
    required = {"Flare id", "Latitude", "Longitude", *range(2012, 2025)}
    if not required.issubset(table.columns):
        raise RuntimeError("The downloaded workbook does not have the expected flare-location fields.")
    active = table[list(range(2012, 2025))].fillna(0).gt(0).any(axis=1)
    sites = table.loc[active, ["Flare id", "Country", "Latitude", "Longitude", "Location", "Field Type"]].copy()
    sites.columns = ["flare_id", "country", "latitude", "longitude", "location", "field_type"]
    sites.to_csv(site_csv, index=False)
    print(f"union flare sites, 2012-2024: {len(sites)}")

    aprx = arcpy.mp.ArcGISProject("CURRENT")
    maps = aprx.listMaps(args.map_name)
    map_object = maps[0] if maps else aprx.activeMap
    if map_object is None:
        raise RuntimeError("No active map was found.")
    project_group = one_group(map_object, PROJECT_GROUP)
    group = find_or_create_group(map_object, project_group)

    BACKUP_FOLDER.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUP_FOLDER / f"{Path(aprx.filePath).stem}_before_flare_mask_{stamp}.aprx"
    aprx.saveACopy(str(backup))
    print(f"backup: {backup}")

    points_wgs84 = str(WORKING_GDB / POINTS_WGS84)
    points_aea = str(WORKING_GDB / POINTS_AEA)
    buffer = str(WORKING_GDB / BUFFER)
    clipped_mask = str(WORKING_GDB / CLIPPED_MASK)
    for dataset in (points_wgs84, points_aea, buffer, clipped_mask):
        delete_if_requested(map_object, dataset, args.replace)

    arcpy.management.XYTableToPoint(str(site_csv), points_wgs84, "longitude", "latitude", coordinate_system=arcpy.SpatialReference(4326))
    arcpy.management.Project(points_wgs84, points_aea, TARGET_CRS)
    arcpy.analysis.Buffer(points_aea, buffer, "5000 Meters", dissolve_option="ALL", method="PLANAR")
    arcpy.analysis.Clip(buffer, str(EXTENT_MASK), clipped_mask)
    add_to_group(map_object, group, points_aea)
    add_to_group(map_object, group, clipped_mask)
    aprx.save()

    print(f"mask features after dissolve and clipping: {arcpy.management.GetCount(clipped_mask).getOutput(0)}")
    print(f"mask: {clipped_mask}")
    print("Complete. Lights were not changed; the next step is to apply this fixed mask to each lights raster.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
