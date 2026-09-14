"""Build importable ArcGIS Pro maps styled after Moqanaki & Cushman (2016).

Run with the ArcGIS Pro Python environment. The script creates:
  * a self-contained file geodatabase
  * an ArcGIS Pro project containing all maps
  * one MAPX file per map
  * reusable LYRX files for the main symbols

The package contains 2024 current and 2012-2024 current change. It does not
contain separate current rasters for 2012, 2016, and 2020, so the script does
not invent a four-year panel.
"""

from pathlib import Path
import os

import arcpy


ROOT = Path(r"C:\Users\liamc\Documents\Codex\2026-09-11\i-want-help")
OUT = ROOT / "outputs" / "asiatic_style_maps"
OUT.mkdir(parents=True, exist_ok=True)

PACKAGE = ROOT / "work" / "resistances_package_full"
PACKAGE_APRX = PACKAGE / "p30" / "resistances.aprx"
SOURCE_VECTOR_GDB = PACKAGE / "commondata" / "cheetah_working.gdb"
SOURCE_RASTER_GDB = PACKAGE / "commondata" / "raster_data.gdb"
NUCLEUS_GDB = ROOT / "work" / "terrain_sensitivity_31_32.gdb"
BASE_GDB = (
    ROOT
    / "cheetah-connectivity-latest"
    / "gis"
    / "cheetah_connectivity"
    / "cheetah"
    / "gdb"
    / "cheetah_working.gdb"
)

OUT_GDB = OUT / "asiatic_style_map_data.gdb"
OUT_APRX = OUT / "asiatic_style_maps.aprx"
MAPX_DIR = OUT / "mapx"
LYRX_DIR = OUT / "layer_files"
MAPX_DIR.mkdir(exist_ok=True)
LYRX_DIR.mkdir(exist_ok=True)

arcpy.env.overwriteOutput = True


def p(path):
    return str(path)


def require(path):
    if not arcpy.Exists(p(path)) and not Path(path).exists():
        raise FileNotFoundError(path)


for needed in [PACKAGE_APRX, SOURCE_VECTOR_GDB, SOURCE_RASTER_GDB, NUCLEUS_GDB, BASE_GDB]:
    require(needed)


if not arcpy.Exists(p(OUT_GDB)):
    arcpy.management.CreateFileGDB(p(OUT), OUT_GDB.name)


def copy_feature(source_gdb, source_name, output_name=None):
    output_name = output_name or source_name
    source = os.path.join(p(source_gdb), source_name)
    target = os.path.join(p(OUT_GDB), output_name)
    require(source)
    if arcpy.Exists(target):
        arcpy.management.Delete(target)
    arcpy.management.CopyFeatures(source, target)
    return target


def copy_raster(source_gdb, source_name, output_name=None):
    output_name = output_name or source_name
    source = os.path.join(p(source_gdb), source_name)
    target = os.path.join(p(OUT_GDB), output_name)
    require(source)
    if arcpy.Exists(target):
        arcpy.management.Delete(target)
    arcpy.management.CopyRaster(source, target)
    return target


DATA = {
    "countries": copy_feature(SOURCE_VECTOR_GDB, "countries_in_study_extent"),
    "protected": copy_feature(SOURCE_VECTOR_GDB, "wdpa_aug2026_polygon_dissolved"),
    "cores": copy_feature(NUCLEUS_GDB, "core_nuclei_final_v2", "cheetah_cores_with_groups"),
    "nuclei": copy_feature(NUCLEUS_GDB, "local_nuclei_windows_25km", "core_group_outlines"),
    "primary": copy_feature(SOURCE_VECTOR_GDB, "conservation_priority_paths_temporal"),
    "uncertain": copy_feature(SOURCE_VECTOR_GDB, "conservation_uncertainty_paths_temporal"),
    "roads": copy_feature(BASE_GDB, "roads_grip4_major", "major_roads"),
    "fences_kaza": copy_feature(BASE_GDB, "vet_fence_kaza_wwf_reference", "fences_kaza_reference"),
    "fences_namibia": copy_feature(
        BASE_GDB, "vet_fence_namibia_atlas2002_reference", "fences_namibia_reference"
    ),
    "current": copy_raster(SOURCE_RASTER_GDB, "current_pctrank_outside_cores_2024"),
    "change": copy_raster(SOURCE_RASTER_GDB, "current_change_pct_outside_cores_2012_2024"),
}


if OUT_APRX.exists():
    OUT_APRX.unlink()
template = arcpy.mp.ArcGISProject(p(PACKAGE_APRX))
template.saveACopy(p(OUT_APRX))
del template

aprx = arcpy.mp.ArcGISProject(p(OUT_APRX))
for item in list(aprx.listLayouts()) + list(aprx.listMaps()):
    aprx.deleteItem(item)


def rgba(values):
    return {"RGB": list(values)}


def simple_polygon(layer, fill, outline, width=0.8, transparency=0):
    sym = layer.symbology
    sym.updateRenderer("SimpleRenderer")
    sym.renderer.symbol.color = rgba(fill)
    sym.renderer.symbol.outlineColor = rgba(outline)
    sym.renderer.symbol.outlineWidth = width
    layer.symbology = sym
    layer.transparency = transparency


def simple_line(layer, color, width=1.0, dashed=False, transparency=0):
    sym = layer.symbology
    sym.updateRenderer("SimpleRenderer")
    if dashed:
        try:
            sym.renderer.symbol.applySymbolFromGallery("Dashed 4:4")
        except Exception:
            pass
    sym.renderer.symbol.color = rgba(color)
    sym.renderer.symbol.size = width
    layer.symbology = sym
    layer.transparency = transparency


def label_layer(layer, field, size=8, where=None):
    if not layer.supports("SHOWLABELS"):
        return
    label_class = layer.listLabelClasses()[0]
    label_class.expression = f"$feature.{field}"
    if where:
        label_class.SQLQuery = where
    layer.showLabels = True
    cim = layer.getDefinition("V3")
    if cim.labelClasses:
        text_symbol = cim.labelClasses[0].textSymbol.symbol
        text_symbol.height = size
        try:
            text_symbol.symbol.symbolLayers[0].color.values = [25, 25, 25, 100]
        except Exception:
            pass
        try:
            text_symbol.haloSize = 1.0
        except Exception:
            pass
    layer.setDefinition(cim)


def style_current(layer):
    colors = [
        [49, 54, 149, 35],
        [69, 117, 180, 50],
        [116, 173, 209, 65],
        [253, 174, 97, 75],
        [244, 109, 67, 88],
        [165, 0, 38, 100],
    ]
    bounds = [50, 80, 90, 95, 99, 100]
    labels = [
        "Below 50th percentile",
        "50th to 80th",
        "80th to 90th",
        "90th to 95th",
        "95th to 99th",
        "99th percentile and above",
    ]
    sym = layer.symbology
    sym.updateColorizer("RasterClassifyColorizer")
    sym.colorizer.classificationField = "Value"
    sym.colorizer.breakCount = 6
    sym.colorizer.classificationMethod = "ManualInterval"
    layer.symbology = sym
    sym = layer.symbology
    colorizer = sym.colorizer
    for item, bound, label, color in zip(colorizer.classBreaks, bounds, labels, colors):
        item.upperBound = bound
        item.label = label
        item.color = rgba(color)
    colorizer.minimumBreak = 0
    colorizer.showInAscendingOrder = True
    layer.symbology = sym


def style_change(layer):
    colors = [
        [49, 54, 149, 100],
        [69, 117, 180, 95],
        [116, 173, 209, 85],
        [171, 217, 233, 75],
        [245, 245, 245, 35],
        [253, 219, 199, 75],
        [244, 165, 130, 85],
        [214, 96, 77, 95],
        [178, 24, 43, 100],
    ]
    bounds = [-20, -10, -5, -2, 2, 5, 10, 20, 300]
    labels = [
        "20% decrease or more",
        "10% to 20% decrease",
        "5% to 10% decrease",
        "2% to 5% decrease",
        "Little change (-2% to +2%)",
        "2% to 5% increase",
        "5% to 10% increase",
        "10% to 20% increase",
        "20% increase or more",
    ]
    sym = layer.symbology
    sym.updateColorizer("RasterClassifyColorizer")
    sym.colorizer.classificationField = "Value"
    sym.colorizer.breakCount = 9
    sym.colorizer.classificationMethod = "ManualInterval"
    layer.symbology = sym
    sym = layer.symbology
    colorizer = sym.colorizer
    for item, bound, label, color in zip(colorizer.classBreaks, bounds, labels, colors):
        item.upperBound = bound
        item.label = label
        item.color = rgba(color)
    colorizer.minimumBreak = -79
    colorizer.showInAscendingOrder = True
    layer.symbology = sym


def style_primary(layer):
    colors = [
        [49, 54, 149, 100],
        [69, 117, 180, 100],
        [116, 173, 209, 100],
        [244, 109, 67, 100],
        [165, 0, 38, 100],
    ]
    sym = layer.symbology
    sym.updateRenderer("GraduatedColorsRenderer")
    sym.renderer.classificationField = "EDGE_BTW"
    sym.renderer.breakCount = 5
    layer.symbology = sym
    sym = layer.symbology
    for item, color in zip(sym.renderer.classBreaks, colors):
        item.symbol.color = rgba(color)
        item.symbol.size = 1.8
    layer.symbology = sym


def add_layer(map_obj, key, name, position="TOP"):
    layer = map_obj.addDataFromPath(DATA[key])
    layer.name = name
    return layer


def add_hillshade(map_obj):
    url = "https://services.arcgisonline.com/ArcGIS/rest/services/Elevation/World_Hillshade/MapServer"
    try:
        layer = map_obj.addDataFromPath(url)
        layer.name = "World Hillshade (online, visual context only)"
        layer.transparency = 45
        return layer
    except Exception as exc:
        arcpy.AddWarning(f"Could not add online hillshade to {map_obj.name}: {exc}")
        return None


def add_base(map_obj, hillshade=True):
    if hillshade:
        add_hillshade(map_obj)
    countries = add_layer(map_obj, "countries", "Country boundaries")
    simple_polygon(countries, [245, 245, 245, 0], [105, 105, 105, 100], 0.6)
    protected = add_layer(map_obj, "protected", "Protected areas")
    simple_polygon(protected, [150, 150, 150, 45], [110, 110, 110, 55], 0.3)
    return countries, protected


def add_cores(map_obj, grouped=True):
    cores = add_layer(map_obj, "cores", "Cheetah cores (fixed 2010-2016)")
    simple_polygon(cores, [255, 255, 255, 100], [25, 25, 25, 100], 1.2)
    label_layer(cores, "CORE_ID", 8)
    if grouped:
        nuclei = add_layer(map_obj, "nuclei", "Descriptive core groups")
        simple_polygon(nuclei, [255, 255, 255, 0], [35, 35, 35, 100], 1.4)
        simple_line(nuclei, [35, 35, 35, 100], 1.4, dashed=True)
        label_layer(nuclei, "NUCLEUS_NAME", 10)
        return cores, nuclei
    return cores, None


def add_transport(map_obj):
    roads = add_layer(map_obj, "roads", "Major roads")
    simple_line(roads, [55, 55, 55, 75], 0.7)
    fk = add_layer(map_obj, "fences_kaza", "Available fence records - KAZA")
    simple_line(fk, [20, 20, 20, 90], 1.0, dashed=True)
    fn = add_layer(map_obj, "fences_namibia", "Available fence records - Namibia")
    simple_line(fn, [20, 20, 20, 90], 1.0, dashed=True)
    return roads, fk, fn


def add_paths(map_obj, query=None):
    primary = add_layer(map_obj, "primary", "Primary modelled links (32)")
    uncertain = add_layer(map_obj, "uncertain", "Uncertain modelled links (13)")
    if query:
        primary.definitionQuery = query
        uncertain.definitionQuery = query
    style_primary(primary)
    simple_line(uncertain, [45, 45, 45, 90], 1.4, dashed=True)
    label_layer(primary, "IMP_RANK", 8, "IMP_RANK <= 5")
    return primary, uncertain


def export_map(map_obj, filename):
    target = MAPX_DIR / filename
    if target.exists():
        target.unlink()
    map_obj.exportToMAPX(p(target))


def set_default_extent(map_obj, feature_path, where=None, expand=1.06):
    layer_name = "__extent_helper__"
    helper = map_obj.addDataFromPath(feature_path)
    helper.name = layer_name
    if where:
        helper.definitionQuery = where
    extent = arcpy.Describe(helper).extent
    try:
        map_obj.defaultCamera.setExtent(extent)
        map_obj.defaultCamera.scale *= expand
    except Exception:
        pass
    map_obj.removeLayer(helper)
    return extent


# Figure 1: study area and four descriptive groups.
m = aprx.createMap("Fig 1 - Study Area and Core Groups", "MAP")
add_base(m)
add_cores(m, grouped=True)
set_default_extent(m, DATA["cores"], expand=1.12)
export_map(m, "Fig1_Study_Area_and_Core_Groups.mapx")


# Figure 2A: paper-like blue-to-red current map for 2024.
m = aprx.createMap("Fig 2A - Modelled Current 2024", "MAP")
add_base(m)
current = add_layer(m, "current", "Modelled current percentile outside cores, 2024")
style_current(current)
add_cores(m, grouped=False)
set_default_extent(m, DATA["cores"], expand=1.12)
export_map(m, "Fig2A_Modelled_Current_2024.mapx")


# Figure 2B: supported temporal change map.
m = aprx.createMap("Fig 2B - Current Change 2012-2024", "MAP")
add_base(m)
change = add_layer(m, "change", "Change in modelled current, 2012-2024")
style_change(change)
add_cores(m, grouped=False)
set_default_extent(m, DATA["cores"], expand=1.12)
export_map(m, "Fig2B_Current_Change_2012_2024.mapx")


# Figure 3: regional link map with transportation context.
m = aprx.createMap("Fig 3 - Modelled Links and Transportation", "MAP")
add_base(m)
add_transport(m)
add_paths(m)
add_cores(m, grouped=True)
set_default_extent(m, DATA["cores"], expand=1.12)
export_map(m, "Fig3_Modelled_Links_and_Transportation.mapx")


# Figure 4: one close view for each descriptive core group.
GROUPS = {
    "Northwest": [1, 9, 13, 17, 18, 24],
    "Central": [28, 30, 33, 36, 38, 40, 41, 42, 43, 45],
    "Southern": [49, 50, 53],
    "Eastern": [26, 27, 31, 32],
}

for letter, (group_name, ids) in zip("ABCD", GROUPS.items()):
    id_text = ",".join(str(value) for value in ids)
    path_query = f"FROM_ID IN ({id_text}) OR TO_ID IN ({id_text})"
    core_query = f"NUCLEUS_NAME = '{group_name}'"
    map_obj = aprx.createMap(f"Fig 4{letter} - {group_name} Detail", "MAP")
    add_base(map_obj)
    add_transport(map_obj)
    add_paths(map_obj, path_query)
    cores, nuclei = add_cores(map_obj, grouped=True)
    cores.definitionQuery = core_query
    nuclei.definitionQuery = core_query
    set_default_extent(map_obj, DATA["nuclei"], core_query, expand=1.08)
    export_map(map_obj, f"Fig4{letter}_{group_name}_Detail.mapx")


# Save reusable styled layers from their first suitable map.
layer_exports = {
    "cores_asiatic_style.lyrx": ("Fig 1 - Study Area and Core Groups", "Cheetah cores"),
    "core_groups_dashed.lyrx": ("Fig 1 - Study Area and Core Groups", "Descriptive core groups"),
    "protected_areas_gray.lyrx": ("Fig 1 - Study Area and Core Groups", "Protected areas"),
    "current_2024_blue_to_red.lyrx": ("Fig 2A - Modelled Current 2024", "Modelled current"),
    "current_change_blue_to_red.lyrx": ("Fig 2B - Current Change 2012-2024", "Change in modelled current"),
    "primary_links_strength.lyrx": ("Fig 3 - Modelled Links and Transportation", "Primary modelled links"),
    "uncertain_links_dashed.lyrx": ("Fig 3 - Modelled Links and Transportation", "Uncertain modelled links"),
    "major_roads_gray.lyrx": ("Fig 3 - Modelled Links and Transportation", "Major roads"),
}

for filename, (map_name, layer_start) in layer_exports.items():
    layer = next(
        lyr
        for lyr in aprx.listMaps(map_name)[0].listLayers()
        if lyr.name.startswith(layer_start)
    )
    target = LYRX_DIR / filename
    if target.exists():
        target.unlink()
    layer.saveACopy(p(target))


def page_rectangle(x0, y0, x1, y1):
    return arcpy.Polygon(
        arcpy.Array(
            [
                arcpy.Point(x0, y0),
                arcpy.Point(x1, y0),
                arcpy.Point(x1, y1),
                arcpy.Point(x0, y1),
                arcpy.Point(x0, y0),
            ]
        )
    )


def create_layout(map_name, figure_title, filename, extent_path, extent_where=None):
    layout_name = "Layout - " + figure_title
    layout = aprx.createLayout(11, 8.5, "INCH", layout_name)
    frame = layout.createMapFrame(page_rectangle(0.35, 0.65, 8.45, 8.05), aprx.listMaps(map_name)[0], "Map frame")
    extent = set_default_extent(aprx.listMaps(map_name)[0], extent_path, extent_where, expand=1.08)
    try:
        frame.camera.setExtent(extent)
        frame.camera.scale *= 1.08
    except Exception:
        pass
    legend = layout.createMapSurroundElement(arcpy.Point(8.75, 7.55), "LEGEND", frame, None, "Legend")
    legend.title = figure_title
    legend.showTitle = True
    legend.elementWidth = 2.0
    legend.elementHeight = 3.9
    legend.elementPositionX = 8.75
    legend.elementPositionY = 4.0
    legend.fittingStrategy = "AdjustColumnsAndFont"
    scale = layout.createMapSurroundElement(arcpy.Point(8.85, 1.05), "SCALE_BAR", frame, None, "Scale bar")
    scale.elementWidth = 1.8
    scale.elementPositionX = 8.85
    scale.elementPositionY = 1.0
    north = layout.createMapSurroundElement(arcpy.Point(10.15, 7.55), "NORTH_ARROW", frame, None, "North arrow")
    north.elementWidth = 0.55
    north.elementHeight = 0.7
    north.elementPositionX = 10.1
    north.elementPositionY = 7.2
    target = OUT / "layouts" / filename
    target.parent.mkdir(exist_ok=True)
    if target.exists():
        target.unlink()
    layout.exportToPAGX(p(target))
    return layout


# Layouts use a journal-style landscape page. Titles are carried by the layout and
# legend; add any author/date text in the final figure editor if required.
create_layout(
    "Fig 1 - Study Area and Core Groups",
    "Figure 1. Study area and core groups",
    "Fig1_Study_Area_and_Core_Groups.pagx",
    DATA["cores"],
)
create_layout(
    "Fig 2A - Modelled Current 2024",
    "Figure 2A. Modelled current, 2024",
    "Fig2A_Modelled_Current_2024.pagx",
    DATA["cores"],
)
create_layout(
    "Fig 2B - Current Change 2012-2024",
    "Figure 2B. Current change, 2012-2024",
    "Fig2B_Current_Change_2012_2024.pagx",
    DATA["cores"],
)
create_layout(
    "Fig 3 - Modelled Links and Transportation",
    "Figure 3. Modelled links and transportation",
    "Fig3_Modelled_Links_and_Transportation.pagx",
    DATA["cores"],
)
for letter, (group_name, ids) in zip("ABCD", GROUPS.items()):
    create_layout(
        f"Fig 4{letter} - {group_name} Detail",
        f"Figure 4{letter}. {group_name} detail",
        f"Fig4{letter}_{group_name}_Detail.pagx",
        DATA["nuclei"],
        f"NUCLEUS_NAME = '{group_name}'",
    )

aprx.save()
print(f"Created ArcGIS project: {OUT_APRX}")
print(f"Created {len(list(MAPX_DIR.glob('*.mapx')))} MAPX files in: {MAPX_DIR}")
print(f"Created {len(list(LYRX_DIR.glob('*.lyrx')))} LYRX files in: {LYRX_DIR}")
print(f"Created {len(list((OUT / 'layouts').glob('*.pagx')))} PAGX layouts in: {OUT / 'layouts'}")
print(f"Self-contained data: {OUT_GDB}")
