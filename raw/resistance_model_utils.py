"""Shared ArcPy helpers for the transparent resistance workflow."""

from datetime import datetime
from pathlib import Path
import os

import arcpy
import numpy as np
from arcpy.sa import Con, Raster

GDB = r"C:\cheetah\gdb\cheetah_working.gdb"
SNAP = r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah_connectivity.gdb\snapgrid_1km"
MASK = r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah_connectivity.gdb\extent_buffered"
BACKUPS = Path(r"C:\cheetah\backups")
REPORTS = Path(r"C:\cheetah\reports")
PARENT = "Cheetah project"
COMPONENT_GROUP = "12 Resistance components · standardized"
FINAL_GROUP = "13 Resistance surfaces · scenarios"


def require(*paths):
    for path in paths:
        if not arcpy.Exists(path):
            raise FileNotFoundError(path)


def setup_env():
    arcpy.CheckOutExtension("Spatial")
    require(GDB, SNAP, MASK)
    arcpy.env.overwriteOutput = True
    arcpy.env.snapRaster = SNAP
    arcpy.env.cellSize = SNAP
    arcpy.env.extent = SNAP
    arcpy.env.mask = MASK
    arcpy.env.outputCoordinateSystem = arcpy.Describe(SNAP).spatialReference


def project_and_map():
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    maps = aprx.listMaps("Map")
    map_object = maps[0] if maps else aprx.activeMap
    if map_object is None:
        raise RuntimeError("No active map found")
    parents = [x for x in map_object.listLayers() if x.isGroupLayer and x.longName == PARENT]
    if len(parents) != 1:
        raise RuntimeError(f"Expected one {PARENT!r} group; found {len(parents)}")
    return aprx, map_object, parents[0]


def backup(aprx, label):
    BACKUPS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = BACKUPS / f"{Path(aprx.filePath).stem}_before_{label}_{stamp}.aprx"
    aprx.saveACopy(str(path))
    print(f"backup: {path}")
    return path


def remove_references(map_object, dataset):
    target = os.path.normcase(os.path.normpath(dataset))
    for layer in list(map_object.listLayers()):
        try:
            if layer.supports("DATASOURCE") and os.path.normcase(os.path.normpath(layer.dataSource)) == target:
                map_object.removeLayer(layer)
        except Exception:
            pass


def replace(map_object, dataset):
    remove_references(map_object, dataset)
    if arcpy.Exists(dataset):
        arcpy.management.Delete(dataset)


def group(map_object, parent, name):
    wanted = parent.longName + "\\" + name
    found = [x for x in map_object.listLayers() if x.isGroupLayer and x.longName == wanted]
    return found[0] if found else map_object.createGroupLayer(name, parent)


def add_grouped(map_object, target_group, dataset, visible=False):
    loose = map_object.addDataFromPath(dataset)
    added = map_object.addLayerToGroup(target_group, loose, "BOTTOM")
    map_object.removeLayer(loose)
    if not added:
        raise RuntimeError(f"Could not add {dataset} to {target_group.longName}")
    added[0].visible = visible
    return added[0]


def positive_percentile(path, percentile=95):
    sentinel = -3.0e38
    values = arcpy.RasterToNumPyArray(path, nodata_to_value=sentinel).astype(np.float32, copy=False)
    values = values[(values > 0) & (values > sentinel / 2) & np.isfinite(values)]
    if values.size == 0:
        raise RuntimeError(f"No positive cells in {path}")
    return float(np.percentile(values, percentile))


def pressure_1_10(source, output, threshold):
    raster = Raster(source)
    result = Con(raster <= 0, 1, Con(raster >= threshold, 10, 1 + 9 * raster / threshold))
    result.save(output)
    arcpy.management.CalculateStatistics(output, 1, 1, [], "OVERWRITE")

