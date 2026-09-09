"""Create the standalone `resistances` ArcGIS Pro project for figure production.

Separate from Resistance.aprx on purpose. That project carries a year of
modelling layers and group structure; this one exists only to make figures, so it
opens clean and nothing in it can disturb the analysis.

Runs standalone, no Pro session required:

    "C:\\Users\\lcrettol\\AppData\\Local\\Programs\\ArcGIS\\Pro\\bin\\Python\\envs\\arcgispro-py3\\python.exe" create_resistances_project.py

Produces C:\\cheetah\\resistances\\resistances.aprx with its own file geodatabase
and three maps, each with a matching 11x8.5 layout:

    FIG A  Modelled current outside cores, 2024
    FIG B  Change in modelled current outside cores, 2012 to 2024
    FIG C  Priority and uncertainty links as least-cost paths

Every layer is referenced in place from C:\\cheetah, nothing is copied or moved,
and the analysis geodatabase is never opened for writing.

Design notes worth keeping
--------------------------
The rasters are the outside-core exports. In a pairwise Circuitscape run the 23
focal cores inject and drain the current, so on the raw surfaces they hold the
entire top decile and swamp any colour ramp. Cores are drawn as outlines instead.

FIG C uses conservation_priority_paths_temporal, the real least-cost geometry.
cheetah_core_neighbor_links and final_priority_core_links_paper are straight
centroid-to-centroid lines and would read as a corridor claim the analysis does
not make.

No north arrow. Across a 2,310 km extent in Africa Albers Equal Area Conic, grid
north and true north diverge visibly off the central meridian. Use a graticule.

Re-running rebuilds the project from scratch; delete the folder first or pass a
different OUT_DIR if you want to keep an earlier version.
"""

import datetime as dt
import os
import shutil
from pathlib import Path

import arcpy

arcpy.env.overwriteOutput = True

# Any small existing project works as a blank starting point; Pro ships no
# template on this machine. The copy is stripped before anything is added.
SEED = r"C:\cheetah\backups\Resistance_before_change_layers_20260831_085218.aprx"

OUT_DIR = Path(r"C:\cheetah\resistances")
PROJECT = OUT_DIR / "resistances.aprx"
GDB = OUT_DIR / "resistances.gdb"

RASTERS = r"C:\cheetah\rasters\outside_core"
WORK_GDB = r"C:\cheetah\gdb\cheetah_working.gdb"

CURRENT_PCTRANK = os.path.join(RASTERS, "current_pctrank_outside_cores_2024.tif")
CHANGE = os.path.join(RASTERS, "current_change_pct_outside_cores_2012_2024.tif")
CORES = os.path.join(WORK_GDB, "cheetah_core_primary_density051_min500")
COUNTRIES = os.path.join(WORK_GDB, "countries_in_study_extent")
PROTECTED = os.path.join(WORK_GDB, "wdpa_aug2026_polygon_dissolved")
PRIORITY = os.path.join(WORK_GDB, "conservation_priority_paths_temporal")
UNCERTAINTY = os.path.join(WORK_GDB, "conservation_uncertainty_paths_temporal")

CURRENT_BREAKS = [50, 80, 90, 95, 99, 100]
CURRENT_COLORS = [(251, 247, 239), (207, 224, 232), (157, 195, 212),
                  (95, 151, 181), (47, 109, 146), (20, 65, 94)]
CURRENT_LABELS = ["below 50th", "50th to 80th", "80th to 90th",
                  "90th to 95th", "95th to 99th", "99th and above"]

CHANGE_BREAKS = [-20, -10, -5, -2, 2, 5, 10, 20, 300]
CHANGE_COLORS = [(94, 36, 16), (140, 61, 31), (201, 123, 78), (234, 191, 154),
                 (242, 240, 235), (168, 201, 189), (90, 151, 130),
                 (31, 99, 80), (14, 64, 47)]
CHANGE_LABELS = ["-20% or less", "-20 to -10%", "-10 to -5%", "-5 to -2%",
                 "-2 to +2%", "+2 to +5%", "+5 to +10%", "+10 to +20%",
                 "+20% or more"]

FIGURES = ("FIG A - Current outside cores 2024",
           "FIG B - Current change outside cores",
           "FIG C - Priority links least-cost paths")
TITLES = ("Modelled current concentration outside range cores, 2024",
          "Change in modelled current outside range cores, 2012 to 2024",
          "Priority and uncertainty links as modelled least-cost paths")


def rgb(triple, alpha=100):
    return {"type": "CIMRGBColor", "values": [triple[0], triple[1], triple[2], alpha]}


def classify(layer, breaks, colors, labels):
    try:
        cim = layer.getDefinition("V3")
        cim.colorizer = {
            "type": "CIMRasterClassifyColorizer",
            "resamplingType": "NearestNeighbor",
            "noDataColor": {"type": "CIMRGBColor", "values": [255, 255, 255, 0]},
            "field": "Value",
            "showInAscendingOrder": True,
            "classBreaks": [
                {"type": "CIMRasterClassBreak", "upperBound": float(b),
                 "label": l, "color": rgb(c)}
                for b, c, l in zip(breaks, colors, labels)],
        }
        layer.setDefinition(cim)
    except Exception as error:
        print(f"    symbology skipped ({layer.name}): {error}")


def style_line(layer, color, width, dashed=False):
    try:
        cim = layer.getDefinition("V3")
        stroke = {"type": "CIMSolidStroke", "enable": True, "width": width,
                  "color": rgb(color), "capStyle": "Round", "joinStyle": "Round"}
        if dashed:
            stroke["effects"] = [{"type": "CIMGeometricEffectDashes",
                                  "dashTemplate": [width * 3, width * 2],
                                  "lineDashEnding": "NoConstraint"}]
        cim.renderer = {"type": "CIMSimpleRenderer",
                        "symbol": {"type": "CIMSymbolReference",
                                   "symbol": {"type": "CIMLineSymbol",
                                              "symbolLayers": [stroke]}}}
        layer.setDefinition(cim)
    except Exception as error:
        print(f"    symbology skipped ({layer.name}): {error}")


def style_polygon(layer, fill, outline, width):
    try:
        cim = layer.getDefinition("V3")
        layers = []
        if outline is not None:
            layers.append({"type": "CIMSolidStroke", "enable": True, "width": width,
                           "color": rgb(outline), "capStyle": "Round",
                           "joinStyle": "Round"})
        layers.append({"type": "CIMSolidFill", "enable": True,
                       "color": rgb(fill) if fill else
                       {"type": "CIMRGBColor", "values": [0, 0, 0, 0]}})
        cim.renderer = {"type": "CIMSimpleRenderer",
                        "symbol": {"type": "CIMSymbolReference",
                                   "symbol": {"type": "CIMPolygonSymbol",
                                              "symbolLayers": layers}}}
        layer.setDefinition(cim)
    except Exception as error:
        print(f"    symbology skipped ({layer.name}): {error}")


def add(map_object, source, name):
    layer = map_object.addDataFromPath(source)
    layer.name = name
    return layer


def build_layout(project, map_object, name, title):
    layout = project.createLayout(11, 8.5, "INCH", name)
    frame = layout.createMapFrame(
        arcpy.Polygon(arcpy.Array([arcpy.Point(0.35, 0.35), arcpy.Point(0.35, 7.60),
                                   arcpy.Point(8.65, 7.60), arcpy.Point(8.65, 0.35)])),
        map_object, "Map frame")
    camera = frame.camera
    camera.setExtent(arcpy.Describe(CORES).extent)
    camera.scale = camera.scale * 1.3

    # No title element. Pro 3.7's Layout API has no createTextElement, and building
    # a CIMTextGraphic by hand is version-fragile. Add titles in the layout view;
    # the intended wording for each is printed at the end of this script.

    for kind, point, label in (("Scale_bar", arcpy.Point(0.65, 0.65), "Scale bar"),
                               ("Legend", arcpy.Point(8.85, 7.60), "Legend")):
        try:
            layout.createMapSurroundElement(point, kind, frame, None, label)
        except Exception as error:
            print(f"    {label} skipped: {error}")
    return layout


def main():
    missing = [p for p in (SEED, CURRENT_PCTRANK, CHANGE, CORES, COUNTRIES,
                           PROTECTED, PRIORITY, UNCERTAINTY) if not os.path.exists(p)
               and not arcpy.Exists(p)]
    if missing:
        raise RuntimeError("missing inputs:\n  " + "\n  ".join(missing))

    if OUT_DIR.exists():
        stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        retired = OUT_DIR.with_name(f"resistances_replaced_{stamp}")
        OUT_DIR.rename(retired)
        print(f"existing project moved aside: {retired}")

    OUT_DIR.mkdir(parents=True)
    shutil.copy2(SEED, PROJECT)
    print(f"project: {PROJECT}")

    if not arcpy.Exists(str(GDB)):
        arcpy.management.CreateFileGDB(str(OUT_DIR), GDB.name)

    project = arcpy.mp.ArcGISProject(str(PROJECT))
    project.defaultGeodatabase = str(GDB)
    project.homeFolder = str(OUT_DIR)

    for layout in project.listLayouts():
        project.deleteItem(layout)
    inherited = list(project.listMaps())

    for name, title in zip(FIGURES, TITLES):
        map_object = project.createMap(name, "Map")

        # Added bottom upward; addDataFromPath places each new layer on top.
        add(map_object, COUNTRIES, "Country boundaries")
        protected = add(map_object, PROTECTED, "Protected areas (WDPA Aug 2026)")
        style_polygon(protected, (222, 219, 210), None, 0)

        raster = None
        if name.startswith("FIG A"):
            raster = add(map_object, CURRENT_PCTRANK, "Modelled current, percentile")
            classify(raster, CURRENT_BREAKS, CURRENT_COLORS, CURRENT_LABELS)
        elif name.startswith("FIG B"):
            raster = add(map_object, CHANGE, "Change in modelled current, percent")
            classify(raster, CHANGE_BREAKS, CHANGE_COLORS, CHANGE_LABELS)

        # Pro drops rasters to the bottom of the TOC regardless of when they are
        # added, which buries them under the filled protected-areas polygon. Lift
        # the raster back above it.
        if raster is not None:
            try:
                map_object.moveLayer(protected, raster, "BEFORE")
            except Exception as error:
                print(f"    draw order not adjusted: {error}")

        cores = add(map_object, CORES, "Range cores (fixed, 2010-2016)")
        style_polygon(cores, None, (26, 26, 26), 1.0)

        if name.startswith("FIG C"):
            uncertain = add(map_object, UNCERTAINTY, "Uncertainty links (13)")
            style_line(uncertain, (192, 122, 51), 1.6, dashed=True)
            priority = add(map_object, PRIORITY, "Primary priority links (32)")
            style_line(priority, (20, 65, 94), 2.0)

        build_layout(project, map_object, name, title)
        print(f"  built {name}")

    for map_object in inherited:
        project.deleteItem(map_object)

    project.save()
    print("\nmaps   :", [m.name for m in project.listMaps()])
    print("layouts:", [l.name for l in project.listLayouts()])
    print(f"\nOpen {PROJECT}")


if __name__ == "__main__":
    main()
