"""Import the best available public veterinary-fence reference datasets.

Primary source: WWF KAZA Landscape public ArcGIS service (regional, 33 lines).
Cross-check: Atlas of Namibia / EIS 2002 shapefile. Sources remain separate;
the script creates no composite, buffer, raster, or resistance assignment.
Run inside the ArcGIS Pro Python window.
"""

from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zipfile import ZipFile
import csv
import json
import os

import arcpy


KAZA_LAYER = (
    "https://wwfke-giscoe.wwfkenya.org/arcgis/rest/services/"
    "KAZA_Landscape_Socioecological_Data/MapServer/19"
)
KAZA_QUERY = KAZA_LAYER + "/query?" + urlencode({
    "where": "1=1", "outFields": "*", "returnGeometry": "true",
    "outSR": "4326", "f": "geojson",
})
NAMIBIA_URL = (
    "https://the-eis.com/elibrary/sites/default/files/downloads/"
    "Atlas_Data/Vet%20fence.zip"
)
NAMIBIA_PAGE = "https://the-eis.com/elibrary/search/1771"
RESEARCH_SOURCE = "https://doi.org/10.3389/fvets.2025.1702631"

RAW_FOLDER = Path(r"C:\cheetah\raw\fences")
KAZA_GEOJSON = RAW_FOLDER / "kaza_wwf_veterinary_fences.geojson"
NAMIBIA_FOLDER = RAW_FOLDER / "namibia_atlas_2002"
NAMIBIA_ZIP = NAMIBIA_FOLDER / "vet_fence.zip"
NAMIBIA_SHP = NAMIBIA_FOLDER / "VETLINE.SHP"
WORK_GDB = r"C:\cheetah\gdb\cheetah_working.gdb"
SNAP_RASTER = r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah_connectivity.gdb\snapgrid_1km"
EXTENT_MASK = r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah_connectivity.gdb\extent_buffered"
KAZA_OUTPUT = os.path.join(WORK_GDB, "vet_fence_kaza_wwf_reference")
NAMIBIA_OUTPUT = os.path.join(WORK_GDB, "vet_fence_namibia_atlas2002_reference")
KAZA_SOURCE_FC = os.path.join(WORK_GDB, "tmp_kaza_fences_wgs84")
BACKUP_FOLDER = Path(r"C:\cheetah\backups")
REPORT_FOLDER = Path(r"C:\cheetah\reports")
MAP_NAME = "Map"
PARENT_NAME = "Cheetah project"
GROUP_NAME = "11 Veterinary fences · reference"


def fetch(url, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = Request(url, headers={"User-Agent": "ArcGIS-Pro-cheetah-workflow/1.0"})
    with urlopen(request, timeout=120) as response, destination.open("wb") as output:
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            output.write(block)
    if destination.stat().st_size < 100:
        raise RuntimeError(f"Downloaded file is unexpectedly small: {destination}")


def acquire_sources():
    payload = None
    if KAZA_GEOJSON.exists():
        try:
            candidate = json.loads(KAZA_GEOJSON.read_text(encoding="utf-8"))
            if len(candidate.get("features", [])) > 0:
                payload = candidate
                print(f"using existing verified KAZA source: {KAZA_GEOJSON}")
        except Exception:
            payload = None
    if payload is None:
        print("downloading WWF KAZA veterinary-fence GeoJSON")
        fetch(KAZA_QUERY, KAZA_GEOJSON)
        payload = json.loads(KAZA_GEOJSON.read_text(encoding="utf-8"))
    feature_count = len(payload.get("features", []))
    if feature_count < 1:
        raise RuntimeError("The KAZA service returned no fence features.")
    print(f"KAZA source features downloaded: {feature_count}")

    NAMIBIA_FOLDER.mkdir(parents=True, exist_ok=True)
    if not NAMIBIA_ZIP.exists() or NAMIBIA_ZIP.stat().st_size < 1000:
        print("downloading Atlas of Namibia veterinary-fence archive")
        fetch(NAMIBIA_URL, NAMIBIA_ZIP)
    with ZipFile(NAMIBIA_ZIP) as archive:
        archive.extractall(NAMIBIA_FOLDER)
    if not NAMIBIA_SHP.exists():
        raise FileNotFoundError(NAMIBIA_SHP)


def geojson_to_polyline_fc(geojson_path, output):
    """Create a strictly 2D WGS84 polyline FC without JSONToFeatures."""
    payload = json.loads(Path(geojson_path).read_text(encoding="utf-8"))
    if arcpy.Exists(output):
        arcpy.management.Delete(output)
    arcpy.management.CreateFeatureclass(
        os.path.dirname(output), os.path.basename(output), "POLYLINE",
        spatial_reference=arcpy.SpatialReference(4326), has_z="DISABLED", has_m="DISABLED"
    )
    arcpy.management.AddField(output, "source_id", "LONG")
    inserted = 0
    with arcpy.da.InsertCursor(output, ["SHAPE@", "source_id"]) as cursor:
        for index, feature in enumerate(payload.get("features", []), start=1):
            geometry = feature.get("geometry") or {}
            geometry_type = geometry.get("type")
            coordinates = geometry.get("coordinates") or []
            if geometry_type == "LineString":
                parts = [coordinates]
            elif geometry_type == "MultiLineString":
                parts = coordinates
            else:
                continue
            arc_parts = arcpy.Array()
            for part in parts:
                points = arcpy.Array([
                    arcpy.Point(float(coordinate[0]), float(coordinate[1]))
                    for coordinate in part if len(coordinate) >= 2
                ])
                if len(points) >= 2:
                    arc_parts.add(points)
            if len(arc_parts) == 0:
                continue
            source_id = feature.get("properties", {}).get("ID", index)
            try:
                source_id = int(source_id)
            except Exception:
                source_id = index
            cursor.insertRow([arcpy.Polyline(arc_parts, arcpy.SpatialReference(4326)), source_id])
            inserted += 1
    if inserted == 0:
        raise RuntimeError("No supported line geometry was found in the KAZA GeoJSON.")
    return inserted


def find_group(map_object, long_name):
    matches = [layer for layer in map_object.listLayers() if layer.isGroupLayer and layer.longName == long_name]
    if len(matches) > 1:
        raise RuntimeError(f"More than one group named {long_name!r} exists.")
    return matches[0] if matches else None


def add_to_group(map_object, group, dataset):
    wanted = os.path.normcase(os.path.normpath(dataset))
    for layer in list(map_object.listLayers()):
        try:
            if layer.supports("DATASOURCE") and os.path.normcase(os.path.normpath(layer.dataSource)) == wanted:
                if layer.longName.startswith(group.longName + "\\"):
                    return
                name = layer.name
                map_object.addLayerToGroup(group, layer, "BOTTOM")
                map_object.removeLayer(layer)
                print(f"moved into group: {name}")
                return
        except Exception:
            continue
    root = map_object.addDataFromPath(dataset)
    map_object.addLayerToGroup(group, root, "BOTTOM")
    map_object.removeLayer(root)


def add_text_field(dataset, name, length):
    if name.lower() not in {field.name.lower() for field in arcpy.ListFields(dataset)}:
        arcpy.management.AddField(dataset, name, "TEXT", field_length=length)


def annotate(dataset, source, vintage, coverage, limitation):
    fields = {
        "data_source": (source, 150),
        "vintage": (vintage, 60),
        "coverage": (coverage, 150),
        "limitation": (limitation, 240),
        "model_role": ("candidate barrier; permeability/status must be tested", 100),
    }
    for field, (_value, length) in fields.items():
        add_text_field(dataset, field, length)
    names = list(fields)
    values = [fields[name][0] for name in names]
    with arcpy.da.UpdateCursor(dataset, names) as rows:
        for row in rows:
            for index, value in enumerate(values):
                row[index] = value
            rows.updateRow(row)


def project_clip(source, output, target_sr, define_wgs84=False):
    stem = Path(output).name
    source_copy = os.path.join(WORK_GDB, "tmp_" + stem + "_source")
    projected = os.path.join(WORK_GDB, "tmp_" + stem + "_projected")
    for dataset in (source_copy, projected, output):
        if arcpy.Exists(dataset):
            arcpy.management.Delete(dataset)
    if define_wgs84:
        arcpy.management.CopyFeatures(source, source_copy)
        if not arcpy.Exists(source_copy):
            raise RuntimeError(f"ArcGIS did not create the source copy: {source_copy}")
        desc = arcpy.Describe(source_copy)
        if not desc.spatialReference or desc.spatialReference.name == "Unknown":
            arcpy.management.DefineProjection(source_copy, arcpy.SpatialReference(4326))
        project_source = source_copy
    else:
        project_source = source
    arcpy.management.Project(project_source, projected, target_sr)
    if not arcpy.Exists(projected):
        raise RuntimeError(f"ArcGIS did not create the projected features: {projected}")
    arcpy.analysis.Clip(projected, EXTENT_MASK, output)
    if not arcpy.Exists(output):
        raise RuntimeError(f"ArcGIS did not create the clipped output: {output}")


def summarize(label, dataset):
    count = int(arcpy.management.GetCount(dataset).getOutput(0))
    length_km = sum(row[0] for row in arcpy.da.SearchCursor(dataset, ["SHAPE@LENGTH"])) / 1000.0
    print(f"{label}: {count} features; {length_km:.2f} km")
    return count, length_km


def main():
    acquire_sources()
    for required in (WORK_GDB, SNAP_RASTER, EXTENT_MASK):
        if not arcpy.Exists(required):
            raise FileNotFoundError(required)

    aprx = arcpy.mp.ArcGISProject("CURRENT")
    maps = aprx.listMaps(MAP_NAME)
    map_object = maps[0] if maps else aprx.activeMap
    if map_object is None:
        raise RuntimeError("No active map was found.")
    parents = [layer for layer in map_object.listLayers() if layer.isGroupLayer and layer.longName == PARENT_NAME]
    if len(parents) != 1:
        raise RuntimeError(f"Expected one group named {PARENT_NAME!r}; found {len(parents)}.")
    parent = parents[0]

    BACKUP_FOLDER.mkdir(parents=True, exist_ok=True)
    REPORT_FOLDER.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUP_FOLDER / f"{Path(aprx.filePath).stem}_before_vet_fences_{stamp}.aprx"
    aprx.saveACopy(str(backup))
    print(f"backup: {backup}")

    converted_count = geojson_to_polyline_fc(KAZA_GEOJSON, KAZA_SOURCE_FC)
    if not arcpy.Exists(KAZA_SOURCE_FC):
        raise RuntimeError("ArcGIS did not create the temporary KAZA feature class from GeoJSON.")
    print(f"converted KAZA GeoJSON: {converted_count} features")
    target_sr = arcpy.Describe(SNAP_RASTER).spatialReference
    project_clip(KAZA_SOURCE_FC, KAZA_OUTPUT, target_sr)
    annotate(
        KAZA_OUTPUT,
        "WWF KAZA Landscape Socioecological Data public ArcGIS service",
        "service updated 2026; individual line vintage unspecified",
        "KAZA transboundary landscape",
        "No segment names, condition, maintenance status, permeability, or license statement in service metadata",
    )

    project_clip(str(NAMIBIA_SHP), NAMIBIA_OUTPUT, target_sr, define_wgs84=True)
    annotate(
        NAMIBIA_OUTPUT,
        "Atlas of Namibia / Environmental Information Service",
        "2002",
        "Namibia",
        "Historical reference; archive lacks .prj; WGS84 assigned from geographic coordinates and Atlas context",
    )

    kaza_count, kaza_length = summarize("KAZA/WWF", KAZA_OUTPUT)
    nam_count, nam_length = summarize("Namibia Atlas", NAMIBIA_OUTPUT)

    group = find_group(map_object, PARENT_NAME + "\\" + GROUP_NAME)
    if group is None:
        group = map_object.createGroupLayer(GROUP_NAME, parent)
    add_to_group(map_object, group, KAZA_OUTPUT)
    add_to_group(map_object, group, NAMIBIA_OUTPUT)
    group.visible = True
    for layer in map_object.listLayers():
        try:
            if layer.longName.startswith(group.longName + "\\"):
                layer.visible = layer.name == Path(KAZA_OUTPUT).name
        except Exception:
            pass
    aprx.save()

    report = REPORT_FOLDER / "veterinary_fence_inventory.csv"
    rows = [
        ["KAZA_WWF", KAZA_OUTPUT, kaza_count, kaza_length, "regional primary reference", KAZA_LAYER, RESEARCH_SOURCE],
        ["Namibia_Atlas_2002", NAMIBIA_OUTPUT, nam_count, nam_length, "historical cross-check", NAMIBIA_PAGE, ""],
    ]
    with report.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["source", "dataset", "features", "length_km", "recommended_use", "source_url", "supporting_research"])
        writer.writerows(rows)

    print(f"report: {report}")
    print("Complete. Sources remain separate; no resistance, raster, buffer, or composite was created.")
    print("Next check: compare KAZA/WWF against the Namibia historical reference and inspect obvious omissions.")


if __name__ == "__main__":
    main()
