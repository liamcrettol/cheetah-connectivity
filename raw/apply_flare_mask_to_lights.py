"""Create flare-masked copies of the VIIRS light rasters without changing inputs."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import arcpy
from arcpy.sa import Con, IsNull, Raster, SetNull


SOURCE_FOLDER = Path(r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah\rasters\gee_exports")
WORKING_GDB = Path(r"C:\cheetah\gdb\cheetah_working.gdb")
BACKUP_FOLDER = Path(r"C:\cheetah\backups")
FLARE_MASK = WORKING_GDB / "gas_flare_mask_5km"
PROJECT_GROUP = "Cheetah project"
GROUP_NAME = "08 Nighttime lights · flare-masked"
YEARS = (2012, 2016, 2020, 2024)
# Float32 missing-data sentinel present in these exported VIIRS rasters.
SOURCE_NODATA_FLOOR = -3.0e38
SNAP_RASTER = r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah_connectivity.gdb\snapgrid_1km"
EXTENT_MASK = r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah_connectivity.gdb\extent_buffered"


def one_group(map_object, long_name: str):
    matches = [layer for layer in map_object.listLayers() if layer.isGroupLayer and layer.longName == long_name]
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one group named {long_name!r}; found {len(matches)}.")
    return matches[0]


def find_or_create_group(map_object, parent):
    long_name = parent.longName + "\\" + GROUP_NAME
    matches = [layer for layer in map_object.listLayers() if layer.isGroupLayer and layer.longName == long_name]
    if len(matches) > 1:
        raise RuntimeError(f"More than one group named {long_name!r} exists.")
    return matches[0] if matches else map_object.createGroupLayer(GROUP_NAME, parent)


def remove_map_references(map_object, dataset: str):
    for layer in list(map_object.listLayers()):
        if not layer.supports("DATASOURCE"):
            continue
        try:
            if layer.dataSource.lower() == dataset.lower():
                map_object.removeLayer(layer)
        except Exception:
            pass


def replace_dataset(map_object, dataset: str):
    remove_map_references(map_object, dataset)
    if arcpy.Exists(dataset):
        arcpy.management.Delete(dataset)


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


def main() -> int:
    if not arcpy.Exists(str(FLARE_MASK)):
        raise RuntimeError(f"Flare mask is missing: {FLARE_MASK}")
    sources = {year: str(SOURCE_FOLDER / f"lights_{year}_1km.tif") for year in YEARS}
    missing = [path for path in sources.values() if not arcpy.Exists(path)]
    if missing:
        raise RuntimeError("Missing source light raster(s): " + "; ".join(missing))
    for path in (SNAP_RASTER, EXTENT_MASK):
        if not arcpy.Exists(path):
            raise RuntimeError(f"Required input is missing: {path}")

    arcpy.CheckOutExtension("Spatial")
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    map_object = aprx.activeMap
    if map_object is None:
        raise RuntimeError("No active map was found.")
    project_group = one_group(map_object, PROJECT_GROUP)
    group = find_or_create_group(map_object, project_group)

    BACKUP_FOLDER.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUP_FOLDER / f"{Path(aprx.filePath).stem}_before_flare_masked_lights_{stamp}.aprx"
    aprx.saveACopy(str(backup))
    print(f"backup: {backup}")

    original_add_outputs = arcpy.env.addOutputsToMap
    arcpy.env.addOutputsToMap = False
    try:
        for source in sources.values():
            # GEE-exported TIFFs don't ship with computed statistics, which
            # SetNull needs for its VALUE comparison below. This only writes
            # a .tif.aux.xml sidecar; pixel values are untouched.
            arcpy.management.CalculateStatistics(source)

        for year, source in sources.items():
            output = str(WORKING_GDB / f"lights_{year}_1km_flaremasked")
            replace_dataset(map_object, output)
            arcpy.env.snapRaster = SNAP_RASTER
            arcpy.env.cellSize = SNAP_RASTER
            arcpy.env.extent = EXTENT_MASK
            arcpy.env.mask = EXTENT_MASK
            mask_raster = str(WORKING_GDB / f"_flare_mask_grid_{year}")
            binary_mask = str(WORKING_GDB / f"_flare_mask_binary_{year}")
            replace_dataset(map_object, mask_raster)
            replace_dataset(map_object, binary_mask)
            arcpy.conversion.PolygonToRaster(
                str(FLARE_MASK), "OBJECTID", mask_raster, "MAXIMUM_AREA", cellsize=SNAP_RASTER
            )
            # PolygonToRaster is NoData outside the flare polygon.  Convert it
            # to an explicit 0/1 grid first; otherwise SetNull propagates that
            # outside NoData and would erase the whole raster.
            Con(IsNull(Raster(mask_raster)), 0, 1).save(binary_mask)
            # The GEE export represents background NoData as a Float32 sentinel
            # value.  Convert it to real NoData before applying the flare mask,
            # so it cannot enter later subtraction statistics as a huge number.
            clean_source = SetNull(Raster(source), Raster(source), f"VALUE <= {SOURCE_NODATA_FLOOR}")
            SetNull(Raster(binary_mask), clean_source, "VALUE = 1").save(output)
            arcpy.management.Delete(mask_raster)
            arcpy.management.Delete(binary_mask)
            add_to_group(map_object, group, output)
            print(f"created: lights_{year}_1km_flaremasked")
    finally:
        arcpy.env.addOutputsToMap = original_add_outputs
        arcpy.env.snapRaster = None
        arcpy.env.cellSize = None
        arcpy.env.extent = None
        arcpy.env.mask = None
        arcpy.CheckInExtension("Spatial")

    aprx.save()
    print("Complete. Four flare-masked copies were created; original lights rasters were unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
