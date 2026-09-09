"""Stage the paper figures in ArcGIS Pro, ready for hand-tuning.

Run from the Python window inside Pro, same as the other scripts in this project:

    exec(open(r"C:\\cheetah\\github_repo\\resistances\\scripts\\stage_paper_figures_in_pro.py").read())

Creates three maps and three layouts, loads the right layers into each, applies a
starting symbology and classification, and adds a map frame, scale bar and legend
to every layout. Everything after that is yours: colours, breaks, extent, label
placement, titles.

    FIG A  Modelled current outside cores, 2024
    FIG B  Change in modelled current outside cores, 2012 to 2024
    FIG C  Priority and uncertainty links as least-cost paths

Why the rasters are the outside-core ones
-----------------------------------------
In a pairwise Circuitscape run the 23 focal cores inject and drain the current, so
on the raw surfaces they hold the entire top decile and will swamp any colour
ramp. The exported surfaces have the cores and all non-positive cells set to
NoData, so a classification computed in Pro covers connecting landscape only.
Cores are still drawn, as outlines, for context.

FIG C deliberately uses conservation_priority_paths_temporal rather than
cheetah_core_neighbor_links or final_priority_core_links_paper. Those two are
straight centroid-to-centroid lines, not routes, and mapping them reads as a
corridor claim the analysis does not make.

No north arrow is added. Across a 2,310 km extent in Africa Albers Equal Area
Conic, grid north and true north diverge visibly away from the central meridian.
Add a graticule in the map properties instead if you want orientation.

Backs the project up before touching anything. Read-only against every raster and
feature class.
"""

import datetime as dt
import os
from pathlib import Path

import arcpy


RASTERS = r"C:\cheetah\rasters\outside_core"
WORK_GDB = r"C:\cheetah\gdb\cheetah_working.gdb"
BACKUPS = Path(r"C:\cheetah\backups")

PARENT = "Cheetah project"
GROUP = "20 Paper figures - outside core"

CURRENT_2024 = os.path.join(RASTERS, "current_pctrank_outside_cores_2024.tif")
CHANGE = os.path.join(RASTERS, "current_change_pct_outside_cores_2012_2024.tif")

CORES = os.path.join(WORK_GDB, "cheetah_core_primary_density051_min500")
COUNTRIES = os.path.join(WORK_GDB, "countries_in_study_extent")
PROTECTED = os.path.join(WORK_GDB, "wdpa_aug2026_polygon_dissolved")
PRIORITY = os.path.join(WORK_GDB, "conservation_priority_paths_temporal")
UNCERTAINTY = os.path.join(WORK_GDB, "conservation_uncertainty_paths_temporal")

FIGURES = (
    ("FIG A - Current outside cores 2024",
     "Modelled current concentration outside range cores, 2024"),
    ("FIG B - Current change outside cores",
     "Change in modelled current outside range cores, 2012 to 2024"),
    ("FIG C - Priority links least-cost paths",
     "Priority and uncertainty links as modelled least-cost paths"),
)

# Percentile breaks for FIG A. These match the bands the analysis reports, so the
# figure and the numbers in Results agree.
CURRENT_BREAKS = [50, 80, 90, 95, 99, 100]
CURRENT_COLORS = [(251, 247, 239), (207, 224, 232), (157, 195, 212),
                  (95, 151, 181), (47, 109, 146), (20, 65, 94)]

# Diverging breaks for FIG B, clamped. The raw range is -79 to +300 percent, so an
# unclamped ramp is useless; the tails saturate on purpose.
CHANGE_BREAKS = [-20, -10, -5, -2, 2, 5, 10, 20, 300]
CHANGE_COLORS = [(94, 36, 16), (140, 61, 31), (201, 123, 78), (234, 191, 154),
                 (242, 240, 235), (168, 201, 189), (90, 151, 130),
                 (31, 99, 80), (14, 64, 47)]


def rgb(triple, alpha=100):
    return {"type": "CIMRGBColor",
            "values": [triple[0], triple[1], triple[2], alpha]}


def backup(project):
    BACKUPS.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = BACKUPS / f"{Path(project.filePath).stem}_before_paper_figures_{stamp}.aprx"
    project.saveACopy(str(path))
    print(f"backup: {path}")


def missing_inputs():
    required = [CURRENT_2024, CHANGE, CORES, COUNTRIES, PRIORITY, UNCERTAINTY]
    return [p for p in required if not arcpy.Exists(p)]


def drop_existing(project):
    """Remove any maps and layouts this script made before, so it is re-runnable."""
    for name, _ in FIGURES:
        for layout in project.listLayouts(name):
            project.deleteItem(layout)
        for mp in project.listMaps(name):
            project.deleteItem(mp)


def add(map_object, source, name, visible=True):
    layer = map_object.addDataFromPath(source)
    layer.name = name
    layer.visible = visible
    return layer


def classify_raster(layer, breaks, colors, label_fmt):
    """Manual-interval classified colorizer via CIM."""
    try:
        cim = layer.getDefinition("V3")
        colorizer = {
            "type": "CIMRasterClassifyColorizer",
            "resamplingType": "NearestNeighbor",
            "noDataColor": {"type": "CIMRGBColor", "values": [255, 255, 255, 0]},
            "classBreaks": [],
            "field": "Value",
            "showInAscendingOrder": True,
        }
        previous = None
        for upper, color in zip(breaks, colors):
            colorizer["classBreaks"].append({
                "type": "CIMRasterClassBreak",
                "upperBound": float(upper),
                "label": label_fmt(previous, upper),
                "color": rgb(color),
            })
            previous = upper
        cim.colorizer = colorizer
        layer.setDefinition(cim)
        return True
    except Exception as error:
        print(f"  symbology skipped for {layer.name}: {error}")
        return False


def style_line(layer, color, width, dashed=False):
    try:
        cim = layer.getDefinition("V3")
        stroke = {
            "type": "CIMSolidStroke",
            "enable": True,
            "width": width,
            "color": rgb(color),
            "capStyle": "Round",
            "joinStyle": "Round",
        }
        if dashed:
            stroke["effects"] = [{"type": "CIMGeometricEffectDashes",
                                  "dashTemplate": [width * 3, width * 2],
                                  "lineDashEnding": "NoConstraint"}]
        cim.renderer = {
            "type": "CIMSimpleRenderer",
            "symbol": {"type": "CIMSymbolReference",
                       "symbol": {"type": "CIMLineSymbol", "symbolLayers": [stroke]}},
        }
        layer.setDefinition(cim)
    except Exception as error:
        print(f"  symbology skipped for {layer.name}: {error}")


def style_polygon(layer, fill, outline, outline_width):
    try:
        cim = layer.getDefinition("V3")
        layers = []
        if outline is not None:
            layers.append({"type": "CIMSolidStroke", "enable": True,
                           "width": outline_width, "color": rgb(outline),
                           "capStyle": "Round", "joinStyle": "Round"})
        layers.append({"type": "CIMSolidFill", "enable": True,
                       "color": rgb(fill) if fill else
                                {"type": "CIMRGBColor", "values": [0, 0, 0, 0]}})
        cim.renderer = {
            "type": "CIMSimpleRenderer",
            "symbol": {"type": "CIMSymbolReference",
                       "symbol": {"type": "CIMPolygonSymbol", "symbolLayers": layers}},
        }
        layer.setDefinition(cim)
    except Exception as error:
        print(f"  symbology skipped for {layer.name}: {error}")


def build_layout(project, map_object, name, title):
    layout = project.createLayout(11, 8.5, "INCH", name)
    frame = layout.createMapFrame(
        arcpy.Polygon(arcpy.Array([
            arcpy.Point(0.35, 0.35), arcpy.Point(0.35, 7.65),
            arcpy.Point(8.70, 7.65), arcpy.Point(8.70, 0.35)])),
        map_object, "Map frame")

    camera = frame.camera
    camera.setExtent(arcpy.Describe(CORES).extent)
    camera.scale = camera.scale * 1.35

    text = layout.createTextElement(
        arcpy.Point(0.35, 7.95), "TEXT", title, "Map frame title")
    try:
        text.textSize = 16
    except Exception:
        pass

    for kind, point, element in (
        ("Scale_bar", arcpy.Point(0.60, 0.60), "Scale bar"),
        ("Legend", arcpy.Point(8.90, 7.65), "Legend"),
    ):
        try:
            layout.createMapSurroundElement(point, kind, frame, None, element)
        except Exception as error:
            print(f"  {element} skipped: {error}")
    return layout


def main():
    missing = missing_inputs()
    if missing:
        raise RuntimeError("missing inputs:\n  " + "\n  ".join(missing))

    project = arcpy.mp.ArcGISProject("CURRENT")
    backup(project)
    drop_existing(project)

    made = []
    for (name, title) in FIGURES:
        map_object = project.createMap(name, "Map")
        map_object.addDataFromPath(COUNTRIES)

        if name.startswith("FIG A"):
            raster = add(map_object, CURRENT_2024, "Modelled current, percentile")
            classify_raster(
                raster, CURRENT_BREAKS, CURRENT_COLORS,
                lambda lo, hi: ("below 50th" if lo is None
                                else f"{int(lo)}th to {int(hi)}th"))
        elif name.startswith("FIG B"):
            raster = add(map_object, CHANGE, "Change in modelled current, percent")
            classify_raster(
                raster, CHANGE_BREAKS, CHANGE_COLORS,
                lambda lo, hi: (f"{hi:+g}% and below" if lo is None
                                else f"{lo:+g}% to {hi:+g}%"))
        else:
            uncertain = add(map_object, UNCERTAINTY, "Uncertainty links (13)")
            style_line(uncertain, (192, 122, 51), 1.6, dashed=True)
            priority = add(map_object, PRIORITY, "Primary priority links (32)")
            style_line(priority, (20, 65, 94), 2.0)

        protected = add(map_object, PROTECTED, "Protected areas", visible=True)
        style_polygon(protected, (222, 219, 210), None, 0)

        cores = add(map_object, CORES, "Range cores (fixed, 2010-2016)")
        style_polygon(cores, None, (26, 26, 26), 1.0)

        # Cores and boundaries sit above the raster; protected areas below it.
        for layer, index in ((cores, 0), (protected, len(map_object.listLayers()) - 1)):
            try:
                map_object.moveLayer(map_object.listLayers()[index], layer, "BEFORE")
            except Exception:
                pass

        build_layout(project, map_object, name, title)
        made.append(name)
        print(f"staged: {name}")

    project.save()
    print("\nproject saved. Layouts created:")
    for name in made:
        print(f"  {name}")
    print("\nAll symbology, breaks, extents and titles are starting points. "
          "Tune them in Pro.")


main()
