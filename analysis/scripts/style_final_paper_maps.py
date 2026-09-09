"""Apply presentation styling to the three generated final-paper maps.

This is display-only: it changes symbology/transparency in the ArcGIS Pro
project and makes an APRX backup. No GIS value, model output, or ranking changes.
"""
import datetime as dt
from pathlib import Path

import arcpy


BACKUPS = Path(r"C:\cheetah\backups")
FIGURES = {
    "FIG 1 · Final structural current · 2024": {
        "current": "Final normalized mean current | 2024",
    },
    "FIG 2 · Structural-current endpoint evidence · 2012–2024": {
        "temporal": "High-current endpoint evidence | styled",
    },
    "FIG 3 · Robust conservation-priority core links": {
        "current": "Final normalized mean current | 2024 context",
        "priority": "32 robust priority core-pair links | not literal routes",
    },
}


def map_by_name(aprx, name):
    matches = aprx.listMaps(name)
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one map named {name!r}; found {len(matches)}")
    return matches[0]


def layer_by_name(map_object, name):
    matches = [layer for layer in map_object.listLayers() if layer.name == name]
    if len(matches) != 1:
        raise RuntimeError(f"{map_object.name}: expected one layer {name!r}; found {len(matches)}")
    return matches[0]


def preferred_ramp(aprx):
    # These are standard Pro ramp names. The wildcard fallback avoids assuming
    # an organization-specific style library exists.
    for pattern in ("Cyan to Purple", "Blue to Purple", "Blue to Yellow", "Yellow to Red"):
        found = aprx.listColorRamps(pattern)
        if found:
            return found[0]
    all_ramps = aprx.listColorRamps()
    if not all_ramps:
        raise RuntimeError("No color ramps are available in this ArcGIS Pro project")
    return all_ramps[0]


def style_current(layer, ramp, transparency=0):
    sym = layer.symbology
    sym.updateColorizer("RasterStretchColorizer")
    sym.colorizer.stretchType = "PercentClip"
    sym.colorizer.minPercent = 1.0
    sym.colorizer.maxPercent = 1.0
    sym.colorizer.colorRamp = ramp
    sym.colorizer.gamma = 0.85
    layer.symbology = sym
    layer.transparency = transparency


def style_priority_lines(layer):
    sym = layer.symbology
    symbol = sym.renderer.symbol
    symbol.color = {"RGB": [124, 58, 237, 100]}
    symbol.size = 3.25
    sym.renderer.symbol = symbol
    layer.symbology = sym


def main():
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    BACKUPS.mkdir(parents=True, exist_ok=True)
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUPS / f"Resistance_before_final_paper_map_style_{timestamp}.aprx"
    aprx.saveACopy(str(backup))
    ramp = preferred_ramp(aprx)

    first = map_by_name(aprx, "FIG 1 · Final structural current · 2024")
    style_current(layer_by_name(first, FIGURES[first.name]["current"]), ramp, transparency=0)

    second = map_by_name(aprx, "FIG 2 · Structural-current endpoint evidence · 2012–2024")
    # The categorical teal/orange/magenta symbology was applied when the map
    # was created; leave it untouched and keep it fully opaque.
    layer_by_name(second, FIGURES[second.name]["temporal"]).transparency = 0

    third = map_by_name(aprx, "FIG 3 · Robust conservation-priority core links")
    style_current(layer_by_name(third, FIGURES[third.name]["current"]), ramp, transparency=78)
    style_priority_lines(layer_by_name(third, FIGURES[third.name]["priority"]))

    aprx.save()
    print("backup:", backup)
    print("continuous-current color ramp:", ramp.name)
    print("FIG 1: blue/purple continuous modeled current, 1% end clip")
    print("FIG 2: teal persistent; orange emerging; magenta lost; gray intermediate-only")
    print("FIG 3: 78% transparent current context with prominent purple priority core-pair links")
    print("Complete. Map display changed only; no GIS data or analysis was changed.")


if __name__ == "__main__":
    main()
