"""Create three clean ArcGIS Pro maps for final-paper layout work.

Creates new maps and a derived 32-link feature class only. Existing maps,
rasters, Circuitscape results, and source datasets are not modified.
"""
import csv
import datetime as dt
from pathlib import Path

import arcpy


WORK_GDB = r"C:\cheetah\gdb\cheetah_working.gdb"
CURRENT_GDB = r"C:\cheetah\circuitscape\derived\current_final_balanced_fence.gdb"
REPORTS = Path(r"C:\cheetah\reports")
BACKUPS = Path(r"C:\cheetah\backups")
CORES = WORK_GDB + r"\cheetah_core_primary_density051_min500"
LINKS = WORK_GDB + r"\cheetah_core_neighbor_links"
CURRENT_2024 = CURRENT_GDB + r"\current_final_balanced_fence_2024_mean"
TEMPORAL_CLASS = CURRENT_GDB + r"\current_final_high_class_2012_2024_display"
PRIORITY_OUTPUT = WORK_GDB + r"\final_priority_core_links_paper"


def newest(pattern):
    matches = sorted(REPORTS.glob(pattern))
    if not matches:
        raise FileNotFoundError(f"No report matches {pattern!r}")
    return matches[-1]


def nested_value(value):
    while isinstance(value, (list, tuple)) and len(value) == 1:
        value = value[0]
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def priority_rows():
    table = newest("final_conservation_link_evidence_*.csv")
    result = {}
    with table.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            key = tuple(sorted((int(row["from_core"]), int(row["to_core"]))))
            result[key] = row
    if len(result) != 32:
        raise RuntimeError(f"Expected 32 final-priority rows, found {len(result)} in {table}")
    return result, table


def prepare_priority_links():
    rows, table = priority_rows()
    if arcpy.Exists(PRIORITY_OUTPUT):
        arcpy.management.Delete(PRIORITY_OUTPUT)
    arcpy.management.CopyFeatures(LINKS, PRIORITY_OUTPUT)
    arcpy.management.AddField(PRIORITY_OUTPUT, "IMPORT_RANK", "LONG")
    arcpy.management.AddField(PRIORITY_OUTPUT, "ER_CHG_PCT", "DOUBLE")
    arcpy.management.AddField(PRIORITY_OUTPUT, "LINK_LABEL", "TEXT", field_length=40)
    kept = 0
    fields = ["FROM_ID", "TO_ID", "IMPORT_RANK", "ER_CHG_PCT", "LINK_LABEL"]
    with arcpy.da.UpdateCursor(PRIORITY_OUTPUT, fields) as cursor:
        for row in cursor:
            key = tuple(sorted((int(row[0]), int(row[1]))))
            evidence = rows.get(key)
            if evidence is None:
                cursor.deleteRow()
                continue
            row[2] = int(evidence["importance_rank"])
            row[3] = float(evidence["final_effective_resistance_change_percent_2012_2024"])
            row[4] = f"{key[0]}–{key[1]} | rank {row[2]}"
            cursor.updateRow(row)
            kept += 1
    if kept != 32:
        raise RuntimeError(f"Expected 32 priority-link features after filtering, found {kept}")
    return table


def set_feature_style(layer, color, width=None, size=None):
    sym = layer.symbology
    try:
        symbol = sym.renderer.symbol
        symbol.color = color
        if width is not None:
            symbol.size = width
        if size is not None:
            symbol.size = size
        sym.renderer.symbol = symbol
        layer.symbology = sym
    except Exception as exc:
        print("WARNING: could not apply feature style to", layer.name, "-", exc)


def style_temporal(layer):
    colors = {
        0: ("Not high current at either endpoint", {"RGB": [255, 255, 255, 0]}),
        1: ("Persistent high current (2012 and 2024)", {"RGB": [0, 92, 122, 100]}),
        2: ("Emerging high current (2024)", {"RGB": [230, 126, 34, 100]}),
        3: ("Lost high current since 2012", {"RGB": [190, 45, 80, 100]}),
        4: ("Intermediate-only high current", {"RGB": [117, 117, 117, 85]}),
    }
    sym = layer.symbology
    sym.updateColorizer("RasterUniqueValueColorizer")
    sym.colorizer.field = "Value"
    layer.symbology = sym
    sym = layer.symbology
    styled = set()
    for group in sym.colorizer.groups:
        for item in group.items:
            value = nested_value(item.values)
            if value in colors:
                item.label, item.color = colors[value]
                styled.add(value)
    layer.symbology = sym
    if styled != set(colors):
        print("WARNING: temporal display styling incomplete; values found:", sorted(styled))


def new_map(aprx, title):
    # Re-use a prior generated map safely, so re-running the script does not
    # create a stack of duplicate maps. It contains only generated content.
    existing = aprx.listMaps(title)
    if existing:
        map_object = existing[0]
        for layer in list(map_object.listLayers()):
            map_object.removeLayer(layer)
    else:
        map_object = aprx.createMap(title, "MAP")
    try:
        map_object.addBasemap("Topographic")
    except Exception:
        print("WARNING: ArcGIS could not add the optional Topographic basemap to", title)
    return map_object


def add(map_object, dataset, name, visible=True):
    layer = map_object.addDataFromPath(dataset)
    layer.name = name
    layer.visible = visible
    return layer


def frame_to_cores(map_object):
    extent = arcpy.Describe(CORES).extent
    map_object.defaultCamera.setExtent(extent)
    map_object.defaultCamera.scale *= 1.12


def main():
    required = (CORES, LINKS, CURRENT_2024, TEMPORAL_CLASS)
    for dataset in required:
        if not arcpy.Exists(dataset):
            raise FileNotFoundError(f"Required dataset is missing: {dataset}")
    priority_source = prepare_priority_links()
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    BACKUPS.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUPS / f"Resistance_before_final_paper_maps_{stamp}.aprx"
    aprx.saveACopy(str(backup))

    fig1 = new_map(aprx, "FIG 1 · Final structural current · 2024")
    current = add(fig1, CURRENT_2024, "Final normalized mean current | 2024")
    cores1 = add(fig1, CORES, "Fixed cheetah density cores")
    set_feature_style(cores1, {"RGB": [255, 255, 255, 100]}, size=5)
    frame_to_cores(fig1)

    fig2 = new_map(aprx, "FIG 2 · Structural-current endpoint evidence · 2012–2024")
    temporal = add(fig2, TEMPORAL_CLASS, "High-current endpoint evidence | styled")
    style_temporal(temporal)
    cores2 = add(fig2, CORES, "Fixed cheetah density cores")
    set_feature_style(cores2, {"RGB": [30, 30, 30, 100]}, size=3)
    frame_to_cores(fig2)

    fig3 = new_map(aprx, "FIG 3 · Robust conservation-priority core links")
    current3 = add(fig3, CURRENT_2024, "Final normalized mean current | 2024 context")
    priority = add(fig3, PRIORITY_OUTPUT, "32 robust priority core-pair links | not literal routes")
    set_feature_style(priority, {"RGB": [148, 0, 211, 100]}, width=2.5)
    cores3 = add(fig3, CORES, "Fixed cheetah density cores")
    set_feature_style(cores3, {"RGB": [255, 255, 255, 100]}, size=4)
    frame_to_cores(fig3)

    aprx.save()
    print("backup:", backup)
    print("priority evidence source:", priority_source)
    print("created feature class:", PRIORITY_OUTPUT)
    print("created maps:")
    print(" FIG 1 · Final structural current · 2024")
    print(" FIG 2 · Structural-current endpoint evidence · 2012–2024")
    print(" FIG 3 · Robust conservation-priority core links")
    print("Complete. New maps and one derived 32-link display feature class were created; source analyses were unchanged.")


if __name__ == "__main__":
    main()
