"""Print a read-only snapshot of the current ArcGIS Pro map Contents pane."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import arcpy


def layer_record(layer, depth: int) -> dict:
    record = {
        "depth": depth,
        "name": layer.name,
        "long_name": layer.longName,
        "group": bool(layer.isGroupLayer),
        "visible": bool(layer.visible),
        "broken": bool(layer.isBroken),
    }
    if layer.supports("DATASOURCE"):
        try:
            record["data_source"] = layer.dataSource
        except Exception as exc:
            record["data_source_error"] = str(exc)
    return record


def walk(map_object, depth: int = 0):
    records = []
    for layer in map_object.listLayers():
        record = layer_record(layer, depth)
        records.append(record)
        prefix = "  " * depth
        kind = "[GROUP]" if record["group"] else "[LAYER]"
        state = "visible" if record["visible"] else "hidden"
        broken = " BROKEN" if record["broken"] else ""
        print(f"{prefix}{kind} {record['name']} ({state}){broken}")
        if record["group"]:
            # listLayers returns all descendants, so nesting depth is calculated
            # from the ArcGIS long-name path rather than recursing duplicates.
            continue
    return records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--map-name", default="Map")
    parser.add_argument(
        "--report",
        default=r"C:\cheetah\contents_pane_dump.json",
        help="Where to save the JSON report.",
    )
    args = parser.parse_args()

    aprx = arcpy.mp.ArcGISProject("CURRENT")
    maps = aprx.listMaps(args.map_name)
    map_object = maps[0] if maps else aprx.activeMap
    if map_object is None:
        raise RuntimeError("No active map was found.")

    print(f"map: {map_object.name}")
    records = []
    for layer in map_object.listLayers():
        # Number of separators in longName gives its nesting depth.
        record = layer_record(layer, layer.longName.count("\\"))
        records.append(record)
        prefix = "  " * record["depth"]
        kind = "[GROUP]" if record["group"] else "[LAYER]"
        state = "visible" if record["visible"] else "hidden"
        broken = " BROKEN" if record["broken"] else ""
        print(f"{prefix}{kind} {record['name']} ({state}){broken}")

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(records, indent=2), encoding="utf-8")
    print(f"\nreport: {report_path}")
    print("Nothing was changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
