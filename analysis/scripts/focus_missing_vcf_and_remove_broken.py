"""Focus the map on missing-VCF context and remove broken layer references.

Creates an APRX backup first. Removes map references only, never GIS datasets.
Turns off all other layers and leaves the diagnostic layer and its group visible.
"""
import datetime as dt
from pathlib import Path
import arcpy

TARGET = "vcf_missing_water_context_v1"
TARGET_GROUP = "14 Missing VCF · water context"
BACKUPS = Path(r"C:\cheetah\backups")
COLORS = {
    1: {"RGB": [44, 123, 182, 100]},
    2: {"RGB": [49, 163, 84, 100]},
    3: {"RGB": [253, 174, 97, 100]},
}
LABELS = {
    1: "Persistent water context",
    2: "Persistent land context",
    3: "Unresolved / mixed context",
}


def safe_name(layer):
    for attribute in ("longName", "name"):
        try:
            return str(getattr(layer, attribute))
        except Exception:
            pass
    return "<broken layer with unavailable name>"


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


def style(layer):
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
        raise RuntimeError(f"Expected three diagnostic classes; styled {sorted(styled)}")
    layer.symbology = sym


def main():
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    maps = aprx.listMaps("Map") or aprx.listMaps()
    if not maps:
        raise RuntimeError("No map exists in the current project")
    map_object = maps[0]
    BACKUPS.mkdir(parents=True, exist_ok=True)
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUPS / f"Resistance_before_broken_layer_cleanup_{timestamp}.aprx"
    aprx.saveACopy(str(backup))

    removed = []
    failed = []
    # Reverse drawing order protects nested references while they are removed.
    for layer in reversed(list(map_object.listLayers())):
        label = safe_name(layer)
        try:
            broken = bool(layer.isBroken)
        except Exception:
            broken = False
        if broken:
            try:
                map_object.removeLayer(layer)
                removed.append(label)
            except Exception as exc:
                failed.append((label, str(exc)))

    target = None
    target_group = None
    for layer in list(map_object.listLayers()):
        label = safe_name(layer)
        try:
            layer.visible = False
        except Exception:
            pass
        try:
            if not layer.isGroupLayer and layer.name == TARGET:
                target = layer
            elif layer.isGroupLayer and layer.name == TARGET_GROUP:
                target_group = layer
        except Exception:
            pass
    if target is None:
        raise RuntimeError(f"Diagnostic layer was not found after cleanup: {TARGET}")

    style(target)
    target.visible = True
    if target_group is not None:
        target_group.visible = True
    aprx.save()

    print("backup:", backup)
    print("broken map references removed:", len(removed))
    for label in removed:
        print("removed reference:", label)
    print("broken references that could not be removed:", len(failed))
    for label, error in failed:
        print("WARNING:", label, error)
    print("visible layer:", TARGET)
    print("blue = persistent water; green = persistent land; orange = unresolved/mixed")
    print("Complete. No GIS dataset was deleted or altered.")


if __name__ == "__main__":
    main()
