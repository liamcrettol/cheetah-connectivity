"""Label the 23 fixed density cores on the priority-link figure map only."""
import datetime as dt
from pathlib import Path

import arcpy


MAP_NAME = "FIG 3 · Robust conservation-priority core links"
CORE_LAYER = "Fixed cheetah density cores"
BACKUPS = Path(r"C:\cheetah\backups")


def main():
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    maps = aprx.listMaps(MAP_NAME)
    if len(maps) != 1:
        raise RuntimeError(f"Expected one map named {MAP_NAME!r}; found {len(maps)}")
    map_object = maps[0]
    layers = [layer for layer in map_object.listLayers() if layer.name == CORE_LAYER]
    if len(layers) != 1:
        raise RuntimeError(f"Expected one core layer named {CORE_LAYER!r}; found {len(layers)}")
    core_layer = layers[0]
    fields = {field.name.upper() for field in arcpy.ListFields(core_layer.dataSource)}
    if "CORE_ID" not in fields:
        raise RuntimeError("The fixed-core layer has no CORE_ID field to label")

    BACKUPS.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUPS / f"Resistance_before_priority_core_labels_{stamp}.aprx"
    aprx.saveACopy(str(backup))

    classes = core_layer.listLabelClasses()
    label_class = classes[0] if classes else core_layer.createLabelClass("Fixed core ID")
    label_class.expression = "$feature.CORE_ID"
    label_class.visible = True
    core_layer.showLabels = True
    aprx.save()

    print("backup:", backup)
    print("map:", MAP_NAME)
    print("labeled fixed density cores:", int(arcpy.management.GetCount(core_layer.dataSource)[0]))
    print("label field: CORE_ID")
    print("Complete. Figure 3 display changed only; no GIS data or analysis was changed.")


if __name__ == "__main__":
    main()
