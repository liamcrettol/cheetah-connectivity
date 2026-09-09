"""Apply a restrained, consistent palette to the three final figure maps.

Deep teal = persistent/priority/strongest concentration; light teal = high
concentration; muted amber = emerging; muted rust = lost; gray = intermediate
or uncertainty. This changes ArcGIS Pro display only.
"""
import datetime as dt
from pathlib import Path

import arcpy


BACKUPS = Path(r"C:\cheetah\backups")
FIG1 = "FIG 1 · High-current concentration areas · 2024"
FIG2 = "FIG 2 · Structural-current endpoint evidence · 2012–2024"
FIG3 = "FIG 3 · Robust conservation-priority core links"

TEAL_DARK = {"RGB": [31, 90, 115, 100]}
TEAL_LIGHT = {"RGB": [143, 190, 193, 100]}
AMBER = {"RGB": [201, 133, 44, 100]}
RUST = {"RGB": [176, 78, 74, 100]}
GRAY = {"RGB": [125, 125, 125, 85]}
TRANSPARENT = {"RGB": [255, 255, 255, 0]}


def key(value):
    while isinstance(value, (list, tuple)) and len(value) == 1:
        value = value[0]
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def only_map(aprx, name):
    matches = aprx.listMaps(name)
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one map named {name!r}; found {len(matches)}")
    return matches[0]


def only_layer(map_object, name):
    matches = [layer for layer in map_object.listLayers() if layer.name == name]
    if len(matches) != 1:
        raise RuntimeError(f"{map_object.name}: expected one layer named {name!r}; found {len(matches)}")
    return matches[0]


def light_gray_basemap(map_object):
    # Remove only current basemap layers, never analytical layers.
    for layer in list(map_object.listLayers()):
        try:
            if layer.isBasemapLayer:
                map_object.removeLayer(layer)
        except Exception:
            pass
    try:
        map_object.addBasemap("Light Gray Canvas")
    except Exception as exc:
        print("WARNING: could not add Light Gray Canvas to", map_object.name, "-", exc)


def unique_style(layer, classes):
    sym = layer.symbology
    sym.updateColorizer("RasterUniqueValueColorizer")
    sym.colorizer.field = "Value"
    layer.symbology = sym
    sym = layer.symbology
    styled = set()
    for group in sym.colorizer.groups:
        for item in group.items:
            value = key(item.values)
            if value in classes:
                item.label, item.color = classes[value]
                styled.add(value)
    layer.symbology = sym
    if styled != set(classes):
        print("WARNING:", layer.name, "could not style all expected values; styled", sorted(styled))


def line_style(layer):
    sym = layer.symbology
    symbol = sym.renderer.symbol
    symbol.color = TEAL_DARK
    symbol.size = 3.25
    sym.renderer.symbol = symbol
    layer.symbology = sym


def main():
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    BACKUPS.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUPS / f"Resistance_before_unified_paper_palette_{stamp}.aprx"
    aprx.saveACopy(str(backup))

    fig1 = only_map(aprx, FIG1)
    light_gray_basemap(fig1)
    unique_style(only_layer(fig1, "High-current concentration areas | 2024 modeled current"), {
        1: ("High current concentration | 95th–99th percentile", TEAL_LIGHT),
        2: ("Highest current concentration | >=99th percentile", TEAL_DARK),
    })

    fig2 = only_map(aprx, FIG2)
    light_gray_basemap(fig2)
    unique_style(only_layer(fig2, "High-current endpoint evidence | styled"), {
        0: ("Not high current at either endpoint", TRANSPARENT),
        1: ("Persistent high current (2012 and 2024)", TEAL_DARK),
        2: ("Emerging high current (2024)", AMBER),
        3: ("Lost high current since 2012", RUST),
        4: ("Intermediate-only high current", GRAY),
    })

    fig3 = only_map(aprx, FIG3)
    light_gray_basemap(fig3)
    context = only_layer(fig3, "Final normalized mean current | 2024 context")
    context.transparency = 85
    line_style(only_layer(fig3, "32 robust priority core-pair links | not literal routes"))

    aprx.save()
    print("backup:", backup)
    print("palette: deep teal=priority/persistent/highest; light teal=high; amber=emerging; rust=lost; gray=intermediate")
    print("basemap: Light Gray Canvas")
    print("Figure 3 current context transparency: 85%")
    print("Complete. Display-only map changes; no GIS data or analysis was modified.")


if __name__ == "__main__":
    main()
