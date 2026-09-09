"""Complete and summarize the full temporal vegetation sensitivity workflow.

Run once inside the ArcGIS Pro Python window. The path stage is restart-safe:
completed scenario-years and completed source-core checkpoints are skipped.
The workflow covers all three vegetation scenarios and all four snapshots,
then validates/summarizes the reports and groups the path outputs in the map.
"""

from datetime import datetime
from pathlib import Path
import os
import runpy
import sys
import traceback

import arcpy


OUTPUTS = Path(r"C:\Users\lcrettol\Documents\Codex\2026-08-25\i-am-working-on-this-spreadsheet\outputs")
REPORTS = Path(r"C:\cheetah\reports")
GDB = r"C:\cheetah\gdb\cheetah_working.gdb"
LOG = REPORTS / "overnight_temporal_vegetation_pipeline.log"
SCENARIOS = ("veg_low", "veg_balanced", "veg_high")
YEARS = (2012, 2016, 2020, 2024)
PARENT_NAME = "Cheetah project"
GROUP_NAME = "15 Connectivity paths · vegetation sensitivity"


class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, value):
        for stream in self.streams:
            stream.write(value)
            stream.flush()
        return len(value)

    def flush(self):
        for stream in self.streams:
            stream.flush()


def normalized_source(layer):
    try:
        if layer.supports("DATASOURCE"):
            return os.path.normcase(os.path.normpath(layer.dataSource))
    except Exception:
        pass
    return ""


def organize_outputs():
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    maps = aprx.listMaps("Map")
    map_object = maps[0] if maps else aprx.activeMap
    if map_object is None:
        raise RuntimeError("No active map was found")
    parents = [
        layer for layer in map_object.listLayers()
        if layer.isGroupLayer and layer.longName == PARENT_NAME
    ]
    if len(parents) != 1:
        raise RuntimeError(f"Expected one {PARENT_NAME!r} group; found {len(parents)}")
    wanted = PARENT_NAME + "\\" + GROUP_NAME
    groups = [
        layer for layer in map_object.listLayers()
        if layer.isGroupLayer and layer.longName == wanted
    ]
    group = groups[0] if groups else map_object.createGroupLayer(GROUP_NAME, parents[0])

    existing = {normalized_source(layer) for layer in map_object.listLayers()}
    added_count = 0
    for scenario in SCENARIOS:
        for year in YEARS:
            dataset = os.path.join(GDB, f"least_cost_paths_temporal_{scenario}_{year}")
            if not arcpy.Exists(dataset):
                continue
            target = os.path.normcase(os.path.normpath(dataset))
            if target in existing:
                continue
            loose = map_object.addDataFromPath(dataset)
            grouped = map_object.addLayerToGroup(group, loose, "BOTTOM")
            map_object.removeLayer(loose)
            if grouped:
                grouped[0].visible = False
            existing.add(target)
            added_count += 1
    group.visible = False
    aprx.save()
    print(f"organized path layers added: {added_count}")


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    with LOG.open("a", encoding="utf-8") as log_handle:
        sys.stdout = Tee(original_stdout, log_handle)
        sys.stderr = Tee(original_stderr, log_handle)
        try:
            print("=" * 72)
            print(f"overnight pipeline started: {datetime.now().isoformat(timespec='seconds')}")
            print("years: 2012, 2016, 2020, 2024")
            print("scenarios: veg_low, veg_balanced, veg_high")
            print("restart behavior: completed reports and source-core checkpoints are skipped")

            os.environ["CHEETAH_YEARS"] = "2012,2016,2020,2024"
            os.environ["CHEETAH_SCENARIOS"] = "veg_low,veg_balanced,veg_high"

            print("\n1/3 Completing least-cost paths")
            runpy.run_path(str(OUTPUTS / "run_temporal_vegetation_paths_fast.py"), run_name="__main__")

            print("\n2/3 Validating and summarizing all reports")
            runpy.run_path(str(OUTPUTS / "summarize_temporal_vegetation_paths.py"), run_name="__main__")

            print("\n3/3 Organizing completed path layers")
            try:
                organize_outputs()
            except Exception as exc:
                print(f"WARNING: path calculations and reports succeeded, but map organization failed: {exc}")

            print(f"overnight pipeline completed: {datetime.now().isoformat(timespec='seconds')}")
            print(f"log: {LOG}")
        except Exception:
            print("OVERNIGHT PIPELINE FAILED")
            traceback.print_exc()
            print(f"Progress is checkpointed. Fix the reported issue and run this same script again: {LOG}")
            raise
        finally:
            try:
                arcpy.CheckInExtension("Spatial")
            except Exception:
                pass
            sys.stdout = original_stdout
            sys.stderr = original_stderr


if __name__ == "__main__":
    main()
