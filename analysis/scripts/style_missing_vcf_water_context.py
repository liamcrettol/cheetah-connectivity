"""Apply diagnostic colors to the existing missing-VCF context layer only."""
import arcpy

LAYER_NAME = "vcf_missing_water_context_v1"
COLORS = {
    1: {"RGB": [44, 123, 182, 100]},   # blue: persistent water
    2: {"RGB": [49, 163, 84, 100]},    # green: persistent land
    3: {"RGB": [253, 174, 97, 100]},   # orange: unresolved/mixed
}
LABELS = {
    1: "Persistent water context",
    2: "Persistent land context",
    3: "Unresolved / mixed context",
}


def class_key(value):
    while isinstance(value, (list, tuple)) and len(value) == 1:
        value = value[0]
    try:
        return int(float(value))
    except (TypeError, ValueError):
        text = str(value).lower()
        if "water" in text:
            return 1
        if "land" in text:
            return 2
        if "unresolved" in text or "mixed" in text:
            return 3
        return None


def main():
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    maps = aprx.listMaps("Map") or aprx.listMaps()
    if not maps:
        raise RuntimeError("No map exists in the current ArcGIS Pro project")
    matches = []
    for layer in maps[0].listLayers():
        try:
            if not layer.isGroupLayer and layer.name == LAYER_NAME:
                matches.append(layer)
        except Exception:
            pass
    if not matches:
        raise RuntimeError(f"Layer not found: {LAYER_NAME}")
    layer = matches[0]
    sym = layer.symbology
    sym.updateColorizer("RasterUniqueValueColorizer")
    try:
        sym.colorizer.field = "CLASS_NAME"
    except Exception:
        pass
    styled = set()
    for group in sym.colorizer.groups:
        for item in group.items:
            key = class_key(item.values)
            if key is None:
                key = class_key(item.label)
            if key in COLORS:
                item.color = COLORS[key]
                item.label = LABELS[key]
                styled.add(key)
    if styled != {1, 2, 3}:
        raise RuntimeError(f"Expected three classes; styled {sorted(styled)}")
    layer.symbology = sym
    layer.visible = True
    aprx.save()
    print("Styled: blue = persistent water; green = persistent land; orange = unresolved/mixed")
    print("Nothing except layer symbology was changed.")


if __name__ == "__main__":
    main()
