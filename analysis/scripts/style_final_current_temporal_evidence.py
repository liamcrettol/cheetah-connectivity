"""Apply a readable categorical style to the final-current temporal evidence.

This changes ArcGIS Pro map-layer display only. It never changes a raster,
Circuitscape result, resistance surface, or conservation-priority decision.
"""
import datetime as dt
from pathlib import Path

import arcpy


LAYER_NAME = "current_final_high_class_2012_2024"
GROUP_NAME = "18 Current flow · temporal evidence"
BACKUPS = Path(r"C:\cheetah\backups")
DISPLAY_NAME = "current_final_high_class_2012_2024_display"

# Value 0 is deliberately transparent: it is simply the large background of
# cells that were not in the positive-current top decile at either endpoint.
CLASSES = {
    0: ("Not high current at either endpoint", {"RGB": [255, 255, 255, 0]}),
    1: ("Persistent high current (2012 and 2024)", {"RGB": [0, 92, 122, 100]}),
    2: ("Emerging high current (2024)", {"RGB": [230, 126, 34, 100]}),
    3: ("Lost high current since 2012", {"RGB": [190, 45, 80, 100]}),
    4: ("Intermediate-only high current", {"RGB": [117, 117, 117, 85]}),
}


def key(value):
    """Turn ArcGIS' nested unique-value representation into an integer."""
    while isinstance(value, (list, tuple)) and len(value) == 1:
        value = value[0]
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def find_map_and_layer(aprx):
    maps = aprx.listMaps("Map") or aprx.listMaps()
    if not maps:
        raise RuntimeError("No map is available in the current ArcGIS Pro project")
    for map_object in maps:
        for layer in map_object.listLayers():
            if not layer.isGroupLayer and layer.name == LAYER_NAME:
                return map_object, layer
    raise RuntimeError(f"Could not find {LAYER_NAME!r} in this ArcGIS Pro project")


def display_copy(source_dataset):
    """Make an integer, map-only copy of the float-valued 0--4 class raster."""
    source = arcpy.Raster(source_dataset)
    output = str(Path(source_dataset).parent / DISPLAY_NAME)
    if arcpy.Exists(output):
        arcpy.management.Delete(output)
    values = arcpy.RasterToNumPyArray(source, nodata_to_value=-9999).astype("int32")
    copy = arcpy.NumPyArrayToRaster(
        values, arcpy.Point(source.extent.XMin, source.extent.YMin),
        source.meanCellWidth, source.meanCellHeight, -9999,
    )
    copy.save(output)
    arcpy.management.DefineProjection(output, source.spatialReference)
    arcpy.management.CalculateStatistics(output, 1, 1, [], "OVERWRITE")
    arcpy.management.BuildRasterAttributeTable(output, "Overwrite")
    del copy
    return output


def add_display_to_group(map_object, original, display_dataset):
    for candidate in list(map_object.listLayers()):
        try:
            if candidate.supports("DATASOURCE") and candidate.dataSource == display_dataset:
                map_object.removeLayer(candidate)
        except Exception:
            pass
    group = next((x for x in map_object.listLayers()
                  if x.isGroupLayer and x.name == GROUP_NAME), None)
    loose = map_object.addDataFromPath(display_dataset)
    if group is None:
        added = [loose]
    else:
        added = map_object.addLayerToGroup(group, loose, "BOTTOM")
        map_object.removeLayer(loose)
    if not added:
        raise RuntimeError("Could not add the integer display copy to the map")
    layer = added[0]
    layer.name = "High-current endpoint class | styled display copy"
    original.visible = False
    return layer


def style(layer):

    # First assign/reload.  ArcGIS builds its unique-value item list only after
    # the field/colorizer has been applied to the layer.
    sym = layer.symbology
    sym.updateColorizer("RasterUniqueValueColorizer")
    sym.colorizer.field = "Value"
    layer.symbology = sym

    sym = layer.symbology
    styled = set()
    found = []
    for group in sym.colorizer.groups:
        for item in group.items:
            value = key(item.values)
            found.append((item.values, item.label))
            if value in CLASSES:
                label, color = CLASSES[value]
                item.label = label
                item.color = color
                styled.add(value)
    layer.symbology = sym
    return styled, found


def main():
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    map_object, layer = find_map_and_layer(aprx)

    BACKUPS.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUPS / f"Resistance_before_final_current_evidence_style_{stamp}.aprx"
    aprx.saveACopy(str(backup))

    display_dataset = display_copy(layer.dataSource)
    display_layer = add_display_to_group(map_object, layer, display_dataset)
    styled, found = style(display_layer)
    display_layer.visible = True
    for candidate in map_object.listLayers():
        if candidate.isGroupLayer and candidate.name == GROUP_NAME:
            candidate.visible = True
            break
    aprx.save()

    print("backup:", backup)
    print("created map-only integer display copy:", display_dataset)
    print("styled values:", sorted(styled))
    if styled != set(CLASSES):
        print("WARNING: Expected values 0-4 but ArcGIS returned these items:")
        for values, label in found:
            print(" ", values, "|", label)
        print("The layer remains usable; open Symbology > Unique Values > Value if any class needs a manual refresh.")
    print("0 = transparent background")
    print("1 = teal persistent high current; 2 = orange emerging; 3 = magenta lost; 4 = gray intermediate-only")
    print("Complete. Display-only change; no GIS data or analysis result was changed.")


if __name__ == "__main__":
    main()
