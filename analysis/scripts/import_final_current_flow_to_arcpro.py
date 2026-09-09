"""Import normalized final current-flow copies into the active ArcGIS Pro map.

Run only after qc_final_pairwise_current_flow.py reports four years and zero
failures. Raw Circuitscape outputs are never changed.  The derived copies divide
cumulative current by the same 253 core pairs in every year and restore zero
only inside the verified model support; outside support remains NoData.
"""

import datetime as task_datetime
from pathlib import Path
import json
import os

import arcpy
import numpy as np


ROOT = Path(r"C:\cheetah\circuitscape")
INPUT = ROOT / "inputs" / "final_balanced_fence_documented"
OUTPUT = ROOT / "outputs" / "final_balanced_fence_documented"
DERIVED = ROOT / "derived"
YEARS = (2012, 2016, 2020, 2024)
PAIR_COUNT = 253
PARENT_NAME = "Cheetah project"
GROUP_NAME = "17 Current flow · final"


def ascii_support(path):
    with Path(path).open(encoding="utf-8") as handle:
        header = {}
        for _ in range(6):
            key, value = handle.readline().split()
            header[key.lower()] = float(value)
    data = np.loadtxt(path, skiprows=6, dtype=np.float64)
    return data != header["nodata_value"]


def remove_dataset_layers(map_object, dataset):
    wanted = os.path.normcase(os.path.normpath(dataset))
    for layer in list(map_object.listLayers()):
        try:
            if layer.supports("DATASOURCE") and os.path.normcase(os.path.normpath(layer.dataSource)) == wanted:
                map_object.removeLayer(layer)
        except Exception:
            pass


def parent_and_group(map_object):
    parents = [x for x in map_object.listLayers() if x.isGroupLayer and x.longName == PARENT_NAME]
    if len(parents) != 1:
        raise RuntimeError(f"Expected exactly one {PARENT_NAME!r} group; found {len(parents)}")
    full = PARENT_NAME + "\\" + GROUP_NAME
    groups = [x for x in map_object.listLayers() if x.isGroupLayer and x.longName == full]
    return parents[0], groups[0] if groups else map_object.createGroupLayer(GROUP_NAME, parents[0])


def add_grouped(map_object, group, dataset, label, visible):
    loose = map_object.addDataFromPath(dataset)
    added = map_object.addLayerToGroup(group, loose, "BOTTOM")
    map_object.removeLayer(loose)
    if not added:
        raise RuntimeError(f"Could not add {dataset}")
    added[0].name = label
    added[0].visible = visible


def main():
    manifest_path = INPUT / "final_circuitscape_input_manifest.json"
    receipt_path = OUTPUT / "FINAL_PAIRWISE_CURRENT_FLOW_COMPLETE.txt"
    if not manifest_path.exists() or not receipt_path.exists():
        raise RuntimeError("Final manifest or solver-completion receipt is missing; do not import incomplete outputs.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    grid = manifest["grid"]
    if manifest.get("core_count") != 23:
        raise RuntimeError("Unexpected final core count in manifest")

    aprx = arcpy.mp.ArcGISProject("CURRENT")
    maps = aprx.listMaps("Map")
    map_object = maps[0] if maps else aprx.activeMap
    if map_object is None:
        raise RuntimeError("No active ArcGIS Pro map found")
    backup_dir = Path(r"C:\cheetah\backups")
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = task_datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = backup_dir / f"{Path(aprx.filePath).stem}_before_final_current_import_{stamp}.aprx"
    aprx.saveACopy(str(backup))
    print(f"backup: {backup}")

    DERIVED.mkdir(exist_ok=True)
    gdb = DERIVED / "current_final_balanced_fence.gdb"
    if not arcpy.Exists(str(gdb)):
        arcpy.management.CreateFileGDB(str(DERIVED), gdb.name)
    _, group = parent_and_group(map_object)
    source_sr = arcpy.SpatialReference(grid["wkid"])

    for year in YEARS:
        raw = OUTPUT / f"current_final_balanced_fence_documented_{year}_cum_curmap.tif"
        resistance = INPUT / f"resistance_final_balanced_fence_documented_{year}.asc"
        log = OUTPUT / f"current_final_balanced_fence_documented_{year}.log"
        if not raw.exists() or not resistance.exists() or not log.exists():
            raise FileNotFoundError(f"Missing final output/input for {year}")
        if "Solving pair 253 of 253" not in log.read_text(encoding="utf-8", errors="replace"):
            raise RuntimeError(f"{year} does not show 253/253 completed pairs")
        current = arcpy.RasterToNumPyArray(str(raw), nodata_to_value=np.nan).astype(np.float64, copy=False)
        support = ascii_support(str(resistance))
        if current.shape != support.shape:
            raise RuntimeError(f"{year}: raw current and resistance support differ in shape")
        derived = np.full(current.shape, -9999.0, dtype=np.float32)
        derived[support] = 0.0
        observed = np.isfinite(current)
        if np.any(observed & ~support):
            raise RuntimeError(f"{year}: current occurs outside valid resistance support")
        derived[observed] = (current[observed] / PAIR_COUNT).astype(np.float32)
        output = os.path.join(str(gdb), f"current_final_balanced_fence_{year}_mean")
        remove_dataset_layers(map_object, output)
        if arcpy.Exists(output):
            arcpy.management.Delete(output)
        raster = arcpy.NumPyArrayToRaster(
            derived, arcpy.Point(grid["xmin"], grid["ymin"]),
            grid["cell_width"], grid["cell_height"], -9999.0
        )
        raster.save(output)
        arcpy.management.DefineProjection(output, source_sr)
        arcpy.management.CalculateStatistics(output, 1, 1, [], "OVERWRITE")
        add_grouped(map_object, group, output, f"{year} | mean current | final balanced + documented fences", year == 2024)
        print(f"available in map: {year} final mean current")
        del current, support, derived, raster

    group.visible = True
    aprx.save()
    print("Complete. Four normalized final current copies were added to the map.")
    print("Raw Circuitscape outputs and model inputs were unchanged.")
    print("Interpretation: current concentration is modeled structural flow, not cheetah occurrence probability or a validated corridor.")


if __name__ == "__main__":
    main()
