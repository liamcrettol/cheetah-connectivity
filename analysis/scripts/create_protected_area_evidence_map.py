"""Create a clean protected-area context map for the final 2024 current result.

This is a descriptive overlay: it does not imply that current concentration is
observed use, a biological corridor, or that legal designation ensures effective
protection.  Only the already-clipped WDPA copy is added; no global service
layer is retained in the map.
"""
from pathlib import Path
import datetime as dt
import arcpy

WORK_GDB = r"C:\cheetah\gdb\cheetah_working.gdb"
CURRENT_GDB = r"C:\cheetah\circuitscape\derived\current_final_balanced_fence.gdb"
HIGH = CURRENT_GDB + r"\current_final_candidate_concentration_2024"
PA = WORK_GDB + r"\wdpa_aug2026_polygon_dissolved"
MAP_NAME = "FIG 4 · Protected-area context of high-current concentration · 2024"
GROUP_NAME = "Protected-area coverage | descriptive evidence"
BACKUPS = Path(r"C:\cheetah\backups")


def find_or_create_map(aprx):
    matches = aprx.listMaps(MAP_NAME)
    return matches[0] if matches else aprx.createMap(MAP_NAME)


def remove_all_layers(map_object):
    # A stand-alone figure map avoids accidentally displaying the global source
    # service or unrelated project layers.
    for layer in list(map_object.listLayers()):
        map_object.removeLayer(layer)


def add_to_group(map_object, group, dataset):
    temporary = map_object.addDataFromPath(dataset)
    map_object.addLayerToGroup(group, temporary, "BOTTOM")
    map_object.removeLayer(temporary)
    return group.listLayers()[-1]


def set_simple_outline(layer, color, width=1.4):
    try:
        sym = layer.symbology
        sym.updateRenderer("SimpleRenderer")
        symbol = sym.renderer.symbol
        symbol.color = {"RGB": [255, 255, 255, 0]}
        symbol.outlineColor = {"RGB": color}
        symbol.outlineWidth = width
        layer.symbology = sym
    except Exception as exc:
        print("WARNING: PA outline styling was not applied automatically:", exc)


def set_raster_class_colors(layer):
    # The integer input has class 1 = 95th–99th percentile and class 2 = >=99th.
    # ArcGIS Pro versions differ in RasterClassify symbology support, so this
    # attempts a neutral publication palette but keeps the valid layer if not.
    try:
        sym = layer.symbology
        sym.updateColorizer("RasterUniqueValueColorizer")
        groups = sym.colorizer.groups
        for group in groups:
            for item in group.items:
                value = str(item.values[0][0])
                if value == "1":
                    item.color = {"RGB": [112, 172, 190, 190]}  # light teal
                    item.label = "High concentration (95th–99th percentile)"
                elif value == "2":
                    item.color = {"RGB": [31, 92, 120, 230]}   # deep teal
                    item.label = "Highest concentration (>=99th percentile)"
        layer.symbology = sym
    except Exception as exc:
        print("WARNING: concentration colors were not applied automatically:", exc)
        print("Use unique values: 1 = 95th–99th percentile; 2 = >=99th percentile.")


def main():
    for dataset in (HIGH, PA):
        if not arcpy.Exists(dataset):
            raise FileNotFoundError("Run protected-area coverage first; missing: " + dataset)
    BACKUPS.mkdir(parents=True, exist_ok=True)
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUPS / f"Resistance_before_protected_area_figure_map_{stamp}.aprx"
    aprx.saveACopy(str(backup))

    map_object = find_or_create_map(aprx)
    remove_all_layers(map_object)
    group = map_object.createGroupLayer(GROUP_NAME)
    pa_layer = add_to_group(map_object, group, PA)
    pa_layer.name = "Designated terrestrial/coastal protected areas | WDPA Aug 2026"
    set_simple_outline(pa_layer, [84, 84, 84, 255])
    concentration_layer = add_to_group(map_object, group, HIGH)
    concentration_layer.name = "2024 modeled high-current concentration areas"
    set_raster_class_colors(concentration_layer)
    map_object.addBasemap("Light Gray Canvas")
    aprx.save()

    print("backup:", backup)
    print("created/updated map:", MAP_NAME)
    print("layers: clipped WDPA polygons and 2024 high-current concentration classes")
    print("Interpretation: descriptive protection context, not observed use or protection effectiveness.")


if __name__ == "__main__":
    main()
