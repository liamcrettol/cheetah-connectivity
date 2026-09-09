"""Download and prepare FAO GLW4 2020 grazing-livestock exposure layers.

Run from the ArcGIS Pro Python window. Downloads resume after interruption.
The script keeps cattle, goats, and sheep separate, clips the global rasters
before projection, aligns outputs to the project's 1 km snap grid, adds them
to the map, and writes a QC report. It does NOT create livestock resistance.
"""

from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
import csv
import os

import arcpy
from arcpy.sa import ExtractByMask, SetNull


BASE_URL = (
    "https://storage.googleapis.com/fao-gismgr-glw4-2020-data/"
    "DATA/GLW4-2020/MAPSET/D-DA-1KM/"
)
SPECIES = {
    "cattle": "CTL",
    "goats": "GTS",
    "sheep": "SHP",
}

RAW_FOLDER = Path(r"C:\cheetah\raw\livestock\glw4_2020")
WORK_GDB = r"C:\cheetah\gdb\cheetah_working.gdb"
SNAP_RASTER = r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah_connectivity.gdb\snapgrid_1km"
EXTENT_MASK = r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah_connectivity.gdb\extent_buffered"
BACKUP_FOLDER = Path(r"C:\cheetah\backups")
REPORT_FOLDER = Path(r"C:\cheetah\reports")
MAP_NAME = "Map"
PARENT_GROUP = "Cheetah project"
GROUP_NAME = "10 Livestock exposure · GLW4 2020"


def require(path):
    if not arcpy.Exists(path):
        raise FileNotFoundError(f"Required project input does not exist: {path}")


def download_resume(url, destination):
    """Download to .part and resume when the server accepts byte ranges."""
    destination = Path(destination)
    part = destination.with_suffix(destination.suffix + ".part")
    if destination.exists() and destination.stat().st_size > 1_000_000:
        print(f"using existing download: {destination}")
        return destination

    start = part.stat().st_size if part.exists() else 0
    headers = {"User-Agent": "ArcGIS-Pro-GLW4-workflow/1.0"}
    if start:
        headers["Range"] = f"bytes={start}-"
        print(f"resuming at {start / 1_048_576:.1f} MB: {destination.name}")
    else:
        print(f"downloading: {destination.name}")

    request = Request(url, headers=headers)
    with urlopen(request, timeout=120) as response:
        partial_response = getattr(response, "status", None) == 206
        if start and not partial_response:
            start = 0
            mode = "wb"
        else:
            mode = "ab" if start else "wb"
        remaining = int(response.headers.get("Content-Length", 0))
        expected = start + remaining
        written = start
        last_report = -1
        with part.open(mode) as handle:
            while True:
                block = response.read(8 * 1024 * 1024)
                if not block:
                    break
                handle.write(block)
                written += len(block)
                percent = int(100 * written / expected) if expected else 0
                if percent >= last_report + 5:
                    print(f"  {destination.name}: {percent}%")
                    last_report = percent
    part.replace(destination)
    print(f"download complete: {destination}")
    return destination


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
                current = os.path.normcase(os.path.normpath(layer.dataSource))
                if current == wanted:
                    return layer
        except Exception:
            continue
    layer = map_object.addDataFromPath(dataset)
    map_object.moveLayer(group, layer, "BEFORE")
    return layer


def raster_property(dataset, name):
    try:
        return float(arcpy.management.GetRasterProperties(dataset, name).getOutput(0))
    except Exception:
        arcpy.management.CalculateStatistics(dataset, 1, 1, [], "OVERWRITE")
        return float(arcpy.management.GetRasterProperties(dataset, name).getOutput(0))


def wgs84_clip_rectangle(mask):
    desc = arcpy.Describe(mask)
    source_sr = desc.spatialReference
    wgs84 = arcpy.SpatialReference(4326)
    extent = desc.extent
    polygon = arcpy.Polygon(
        arcpy.Array([
            arcpy.Point(extent.XMin, extent.YMin),
            arcpy.Point(extent.XMin, extent.YMax),
            arcpy.Point(extent.XMax, extent.YMax),
            arcpy.Point(extent.XMax, extent.YMin),
        ]),
        source_sr,
    ).projectAs(wgs84)
    e = polygon.extent
    # A small margin prevents edge loss during reprojection.
    margin = 0.05
    return f"{e.XMin-margin} {e.YMin-margin} {e.XMax+margin} {e.YMax+margin}"


def main():
    arcpy.CheckOutExtension("Spatial")
    require(SNAP_RASTER)
    require(EXTENT_MASK)
    require(WORK_GDB)
    RAW_FOLDER.mkdir(parents=True, exist_ok=True)
    REPORT_FOLDER.mkdir(parents=True, exist_ok=True)
    BACKUP_FOLDER.mkdir(parents=True, exist_ok=True)

    aprx = arcpy.mp.ArcGISProject("CURRENT")
    maps = [item for item in aprx.listMaps() if item.name == MAP_NAME]
    if not maps:
        raise RuntimeError(f"Map not found: {MAP_NAME}")
    map_object = maps[0]

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUP_FOLDER / f"{Path(aprx.filePath).stem}_before_livestock_{stamp}.aprx"
    aprx.saveACopy(str(backup))
    print(f"backup: {backup}")

    target_sr = arcpy.Describe(SNAP_RASTER).spatialReference
    clip_rectangle = wgs84_clip_rectangle(EXTENT_MASK)
    arcpy.env.overwriteOutput = True
    arcpy.env.snapRaster = SNAP_RASTER
    arcpy.env.cellSize = SNAP_RASTER
    arcpy.env.extent = EXTENT_MASK
    arcpy.env.mask = EXTENT_MASK
    arcpy.env.outputCoordinateSystem = target_sr

    outputs = []
    rows = []
    for species, code in SPECIES.items():
        filename = f"GLW4-2020.D-DA-1KM.{code}.tif"
        source = download_resume(BASE_URL + filename, RAW_FOLDER / filename)
        clipped = os.path.join("in_memory", f"glw4_{species}_wgs84_clip")
        projected = os.path.join("in_memory", f"glw4_{species}_projected")
        output = os.path.join(WORK_GDB, f"livestock_{species}_2020_1km")

        for item in (clipped, projected, output):
            if arcpy.Exists(item):
                arcpy.management.Delete(item)

        print(f"clipping global {species} raster")
        arcpy.management.Clip(
            str(source), clip_rectangle, clipped, "#", "-9999", "NONE", "NO_MAINTAIN_EXTENT"
        )
        print(f"projecting and aligning {species}")
        arcpy.management.ProjectRaster(clipped, projected, target_sr, "BILINEAR", 1000)
        ExtractByMask(SetNull(arcpy.Raster(projected) < 0, projected), EXTENT_MASK, "INSIDE").save(output)
        arcpy.management.CalculateStatistics(output, 1, 1, [], "OVERWRITE")
        outputs.append(output)
        rows.append({
            "species": species,
            "output": output,
            "reference_year": 2020,
            "unit": "head_per_square_kilometre",
            "minimum": raster_property(output, "MINIMUM"),
            "maximum": raster_property(output, "MAXIMUM"),
            "mean": raster_property(output, "MEAN"),
            "standard_deviation": raster_property(output, "STD"),
            "role": "exposure_context_not_resistance",
        })
        print(f"created: {os.path.basename(output)}")

    report = REPORT_FOLDER / "livestock_glw4_2020_summary.csv"
    with report.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    group = ensure_group(map_object)
    for output in outputs:
        layer = add_once(map_object, group, output)
        layer.visible = False
    group.visible = True
    aprx.save()

    print(f"report: {report}")
    print("Complete. Cattle, goats, and sheep remain separate.")
    print("No livestock composite or resistance layer was created.")
    print("Interpretation: modeled 2020 livestock density is exposure context, not observed conflict.")
    arcpy.CheckInExtension("Spatial")


if __name__ == "__main__":
    main()
