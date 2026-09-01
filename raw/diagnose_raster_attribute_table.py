"""Read-only diagnostics for a raster layer's attribute table in ArcGIS Pro."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import arcpy


def safe(label, function):
    try:
        value = function()
        print(f"{label}: {value}")
        return value
    except Exception as exc:
        print(f"{label}: ERROR - {exc}")
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--layer", default="lc_2012_1km")
    parser.add_argument("--map-name", default="Map")
    args = parser.parse_args()

    aprx = arcpy.mp.ArcGISProject("CURRENT")
    maps = aprx.listMaps(args.map_name)
    active_map = maps[0] if maps else aprx.activeMap
    if active_map is None:
        print("ERROR: no active map was found.")
        return 1

    matches = []
    for layer in active_map.listLayers():
        name = safe("checking layer name", lambda layer=layer: layer.name)
        if name and args.layer.lower() in name.lower():
            matches.append(layer)

    print(f"map: {active_map.name}")
    print(f"matching layers: {len(matches)}")
    if not matches:
        print(f"ERROR: no layer containing {args.layer!r} was found.")
        return 1

    for number, layer in enumerate(matches, 1):
        print(f"\n--- match {number} ---")
        safe("layer name", lambda: layer.name)
        safe("long name", lambda: layer.longName)
        safe("broken", lambda: layer.isBroken)
        source = safe("data source", lambda: layer.dataSource)
        safe("supports DATASOURCE", lambda: layer.supports("DATASOURCE"))

        if not source:
            continue
        safe("arcpy.Exists", lambda: arcpy.Exists(source))
        raster = safe("open as arcpy.Raster", lambda: arcpy.Raster(source))
        if raster is None:
            continue

        safe("format", lambda: raster.format)
        safe("pixel type", lambda: raster.pixelType)
        safe("integer", lambda: raster.isInteger)
        safe("band count", lambda: raster.bandCount)
        safe("has raster attribute table", lambda: raster.hasRAT)
        fields = safe(
            "fields",
            lambda: [(field.name, field.type) for field in arcpy.ListFields(source)],
        )
        if fields and {name.lower() for name, _ in fields} >= {"value", "count"}:
            safe(
                "first Value/Count rows",
                lambda: list(arcpy.da.SearchCursor(source, ["Value", "Count"]))[:25],
            )

        source_path = Path(source)
        if source_path.exists():
            safe(
                "matching source/sidecar files",
                lambda: sorted(
                    item.name
                    for item in source_path.parent.iterdir()
                    if item.name.lower().startswith(source_path.name.lower())
                ),
            )
            safe("source writable", lambda: os.access(source_path, os.W_OK))

    print("\nDiagnostic complete; nothing was changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
