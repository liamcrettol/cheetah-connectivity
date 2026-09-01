"""Create transparent 1 km veterinary-fence resistance scenarios in ArcGIS Pro.

Run inside the ArcGIS Pro Python window. The WWF/KAZA reference lines are
preserved. Outputs are multiplier surfaces: background = 1; fence cells use
the scenario value. They are not combined with the final resistance model.
"""

from datetime import datetime
from pathlib import Path
import csv
import os

import arcpy
from arcpy.sa import Con, IsNull


WORK_GDB = r"C:\cheetah\gdb\cheetah_working.gdb"
FENCES = os.path.join(WORK_GDB, "vet_fence_kaza_wwf_reference")
SNAP_RASTER = r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah_connectivity.gdb\snapgrid_1km"
EXTENT_MASK = r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah_connectivity.gdb\extent_buffered"

FENCE_CELLS = os.path.join(WORK_GDB, "fence_presence_1km")
NO_FENCE = os.path.join(WORK_GDB, "fence_multiplier_none_1km")
MAIN = os.path.join(WORK_GDB, "fence_multiplier_main_1km")
BARRIER = os.path.join(WORK_GDB, "fence_multiplier_nearbarrier_1km")

# Explicit assumptions for sensitivity testing, not empirically fitted values.
MAIN_VALUE = 25
BARRIER_VALUE = 1000

BACKUP_FOLDER = Path(r"C:\cheetah\backups")
REPORT_FOLDER = Path(r"C:\cheetah\reports")
PARENT_NAME = "Cheetah project"
GROUP_NAME = "11 Veterinary fences · scenarios"


def require(path):
    if not arcpy.Exists(path):
        raise FileNotFoundError(path)


def direct_group(map_object, parent, name):
    wanted = parent.longName + "\\" + name
    matches = [layer for layer in map_object.listLayers() if layer.isGroupLayer and layer.longName == wanted]
    return matches[0] if matches else map_object.createGroupLayer(name, parent)


def add_to_group(map_object, group, dataset):
    normalized = os.path.normcase(os.path.normpath(dataset))
    matches = []
    for layer in map_object.listLayers():
        try:
            if layer.supports("DATASOURCE") and os.path.normcase(os.path.normpath(layer.dataSource)) == normalized:
                matches.append(layer)
        except Exception:
            pass
    if matches and matches[0].longName.startswith(group.longName + "\\"):
        return matches[0]
    # Add a group-owned reference first. Remove any loose reference only after
    # the grouped layer exists; the underlying GIS dataset is never deleted.
    loose = map_object.addDataFromPath(dataset)
    grouped_result = map_object.addLayerToGroup(group, loose, "BOTTOM")
    if not grouped_result:
        raise RuntimeError(f"ArcGIS could not add {dataset} to {group.longName}")
    grouped = grouped_result[0]
    map_object.removeLayer(loose)
    for layer in matches:
        try:
            map_object.removeLayer(layer)
        except Exception:
            pass
    return grouped


def main():
    arcpy.CheckOutExtension("Spatial")
    for item in (WORK_GDB, FENCES, SNAP_RASTER, EXTENT_MASK):
        require(item)

    aprx = arcpy.mp.ArcGISProject("CURRENT")
    map_object = aprx.listMaps("Map")[0] if aprx.listMaps("Map") else aprx.activeMap
    parents = [layer for layer in map_object.listLayers() if layer.isGroupLayer and layer.longName == PARENT_NAME]
    if len(parents) != 1:
        raise RuntimeError(f"Expected one {PARENT_NAME!r} group; found {len(parents)}")

    BACKUP_FOLDER.mkdir(parents=True, exist_ok=True)
    REPORT_FOLDER.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUP_FOLDER / f"{Path(aprx.filePath).stem}_before_fence_scenarios_{stamp}.aprx"
    aprx.saveACopy(str(backup))
    print(f"backup: {backup}")

    arcpy.env.overwriteOutput = True
    arcpy.env.snapRaster = SNAP_RASTER
    arcpy.env.cellSize = SNAP_RASTER
    arcpy.env.extent = EXTENT_MASK
    arcpy.env.mask = EXTENT_MASK
    arcpy.env.outputCoordinateSystem = arcpy.Describe(SNAP_RASTER).spatialReference

    temporary = os.path.join(WORK_GDB, "tmp_fence_lines_1km")
    for dataset in (temporary, FENCE_CELLS, NO_FENCE, MAIN, BARRIER):
        if arcpy.Exists(dataset):
            arcpy.management.Delete(dataset)

    arcpy.conversion.PolylineToRaster(
        FENCES, "OBJECTID", temporary, "MAXIMUM_LENGTH", cellsize=SNAP_RASTER
    )
    # Presence is 1 on every crossed 1 km cell and 0 elsewhere inside the mask.
    Con(IsNull(temporary), 0, 1).save(FENCE_CELLS)
    Con(arcpy.Raster(FENCE_CELLS) == 1, 1, 1).save(NO_FENCE)
    Con(arcpy.Raster(FENCE_CELLS) == 1, MAIN_VALUE, 1).save(MAIN)
    Con(arcpy.Raster(FENCE_CELLS) == 1, BARRIER_VALUE, 1).save(BARRIER)
    if arcpy.Exists(temporary):
        arcpy.management.Delete(temporary)

    group = direct_group(map_object, parents[0], GROUP_NAME)
    layers = [add_to_group(map_object, group, p) for p in (FENCE_CELLS, NO_FENCE, MAIN, BARRIER)]
    group.visible = True
    for layer in layers:
        try:
            layer.visible = Path(layer.dataSource).name == Path(MAIN).name
        except Exception:
            pass

    report = REPORT_FOLDER / "veterinary_fence_scenario_decision.csv"
    with report.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["scenario", "background_multiplier", "fence_cell_multiplier", "interpretation"])
        writer.writerow(["none", 1, 1, "baseline comparison; fences omitted"])
        writer.writerow(["main", 1, MAIN_VALUE, "strong but crossable; assumption for scenario testing"])
        writer.writerow(["nearbarrier", 1, BARRIER_VALUE, "near-barrier sensitivity test; not a claim of universal impermeability"])

    aprx.save()
    print(f"fence cells rasterized: {FENCE_CELLS}")
    print(f"created baseline multiplier: 1")
    print(f"created main fence multiplier: {MAIN_VALUE}")
    print(f"created near-barrier multiplier: {BARRIER_VALUE}")
    print(f"report: {report}")
    print("Complete. Reference lines and existing resistance layers were unchanged; scenarios were not combined into a final model.")


if __name__ == "__main__":
    main()
