"""Download, clip, and inventory GRIP4 Africa roads for the cheetah study extent."""

from __future__ import annotations

import json
import zipfile
from datetime import datetime
from pathlib import Path

import arcpy
import requests


GRIP_URL = "https://dataportaal.pbl.nl/downloads/GRIP4/GRIP4_Region3_vector_fgdb.zip"
RAW_FOLDER = Path(r"C:\cheetah\raw\roads\grip4")
WORKING_GDB = Path(r"C:\cheetah\gdb\cheetah_working.gdb")
EXTENT_MASK = Path(r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah_connectivity.gdb\extent_buffered")
BACKUP_FOLDER = Path(r"C:\cheetah\backups")
REPORT_PATH = Path(r"C:\cheetah\reports\roads_grip4_inventory.json")
PROJECT_GROUP = "Cheetah project"
GROUP_NAME = "09 Roads · GRIP4"
OUTPUT_NAME = "roads_grip4"
TEMP_NAME = "_roads_grip4_projected_temp"


def remove_map_references(map_object, dataset: str):
    for layer in list(map_object.listLayers()):
        if not layer.supports("DATASOURCE"):
            continue
        try:
            if layer.dataSource.lower() == dataset.lower():
                map_object.removeLayer(layer)
        except Exception:
            pass


def delete_if_exists(map_object, dataset: str):
    remove_map_references(map_object, dataset)
    if arcpy.Exists(dataset):
        arcpy.management.Delete(dataset)


def one_group(map_object, long_name: str):
    groups = [layer for layer in map_object.listLayers() if layer.isGroupLayer and layer.longName == long_name]
    if len(groups) != 1:
        raise RuntimeError(f"Expected one group named {long_name!r}; found {len(groups)}.")
    return groups[0]


def find_or_create_group(map_object, parent):
    long_name = parent.longName + "\\" + GROUP_NAME
    matches = [layer for layer in map_object.listLayers() if layer.isGroupLayer and layer.longName == long_name]
    if len(matches) > 1:
        raise RuntimeError(f"More than one group named {long_name!r} exists.")
    return matches[0] if matches else map_object.createGroupLayer(GROUP_NAME, parent)


def add_to_group(map_object, group, dataset: str):
    map_object.addDataFromPath(dataset)
    roots = [
        layer for layer in map_object.listLayers()
        if layer.longName == layer.name and layer.supports("DATASOURCE")
        and getattr(layer, "dataSource", "").lower() == dataset.lower()
    ]
    if len(roots) != 1:
        raise RuntimeError(f"Could not identify the temporary map layer for {dataset}")
    map_object.addLayerToGroup(group, roots[0], "BOTTOM")
    loose = [
        layer for layer in map_object.listLayers()
        if layer.longName == layer.name and layer.supports("DATASOURCE")
        and getattr(layer, "dataSource", "").lower() == dataset.lower()
    ]
    if len(loose) == 1:
        map_object.removeLayer(loose[0])


def get_source_feature_class() -> str:
    RAW_FOLDER.mkdir(parents=True, exist_ok=True)
    archive = RAW_FOLDER / "GRIP4_Region3_vector_fgdb.zip"
    extract_folder = RAW_FOLDER / "GRIP4_Region3_vector_fgdb"
    # ArcGIS Pro's bundled urllib certificate store can reject this server even
    # when Windows trusts it.  Requests succeeds with the environment's CA
    # bundle; verify any interrupted prior download before reusing it.
    if archive.exists() and not zipfile.is_zipfile(archive):
        archive.unlink()
    if not archive.exists():
        print("downloading GRIP4 Africa vector geodatabase (about 125 MB)")
        temporary_archive = archive.with_suffix(".zip.part")
        if temporary_archive.exists():
            temporary_archive.unlink()
        with requests.get(GRIP_URL, stream=True, timeout=(30, 600)) as response:
            response.raise_for_status()
            with temporary_archive.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        handle.write(chunk)
        if not zipfile.is_zipfile(temporary_archive):
            temporary_archive.unlink(missing_ok=True)
            raise RuntimeError("GRIP4 download completed but is not a valid ZIP archive.")
        temporary_archive.replace(archive)
    if not extract_folder.exists():
        print("extracting GRIP4 Africa geodatabase")
        with zipfile.ZipFile(archive) as zipped:
            zipped.extractall(extract_folder)
    geodatabases = list(extract_folder.rglob("*.gdb"))
    if len(geodatabases) != 1:
        raise RuntimeError(f"Expected one extracted geodatabase; found {len(geodatabases)}.")
    candidates = []
    for directory, _, datasets in arcpy.da.Walk(str(geodatabases[0]), datatype="FeatureClass"):
        for dataset in datasets:
            path = str(Path(directory) / dataset)
            if arcpy.Describe(path).shapeType == "Polyline":
                candidates.append(path)
    if len(candidates) != 1:
        raise RuntimeError("Expected one road polyline feature class. Candidates: " + "; ".join(candidates))
    return candidates[0]


def main() -> int:
    if not arcpy.Exists(str(EXTENT_MASK)):
        raise RuntimeError(f"Study extent is unavailable: {EXTENT_MASK}")
    source = get_source_feature_class()
    print(f"GRIP4 source feature class: {source}")

    aprx = arcpy.mp.ArcGISProject("CURRENT")
    map_object = aprx.activeMap
    if map_object is None:
        raise RuntimeError("No active map was found.")
    group = find_or_create_group(map_object, one_group(map_object, PROJECT_GROUP))
    BACKUP_FOLDER.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUP_FOLDER / f"{Path(aprx.filePath).stem}_before_grip4_roads_{stamp}.aprx"
    aprx.saveACopy(str(backup))
    print(f"backup: {backup}")

    output = str(WORKING_GDB / OUTPUT_NAME)
    temporary = str(WORKING_GDB / TEMP_NAME)
    delete_if_exists(map_object, output)
    delete_if_exists(map_object, temporary)
    old_add_outputs = arcpy.env.addOutputsToMap
    arcpy.env.addOutputsToMap = False
    try:
        arcpy.management.Project(source, temporary, arcpy.Describe(str(EXTENT_MASK)).spatialReference)
        arcpy.analysis.PairwiseClip(temporary, str(EXTENT_MASK), output)
    finally:
        arcpy.env.addOutputsToMap = old_add_outputs
        if arcpy.Exists(temporary):
            arcpy.management.Delete(temporary)

    count = int(arcpy.management.GetCount(output).getOutput(0))
    fields = [
        {"name": field.name, "alias": field.aliasName, "type": field.type, "length": field.length}
        for field in arcpy.ListFields(output)
        if field.type not in {"Geometry", "OID"}
    ]
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps({"source": source, "output": output, "feature_count": count, "fields": fields}, indent=2), encoding="utf-8")
    add_to_group(map_object, group, output)
    aprx.save()
    print(f"clipped road features: {count}")
    print("field inventory:")
    for field in fields:
        print(f"  {field['name']} ({field['type']})")
    print(f"report: {REPORT_PATH}")
    print("Complete. A clipped GRIP4 road layer was added; no rasters were changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
