"""Create a draft three-panel landscape layout for the final connectivity maps.

The layout is intentionally a starting point for manual finishing: legend
placement, typography, citations, scale bars, and local inset/callout choices
remain with the author. It changes ArcGIS Pro layout/map display only.
"""
import datetime as dt
from pathlib import Path

import arcpy


BACKUPS = Path(r"C:\cheetah\backups")
LAYOUT_NAME = "LAYOUT · Final connectivity evidence · draft"
CORE_SOURCE = r"C:\cheetah\gdb\cheetah_working.gdb\cheetah_core_primary_density051_min500"
PANELS = (
    ("FIG 1 · Final structural current · 2024", "A  Final structural current (2024)", (0.40, 0.50, 6.15, 7.55)),
    ("FIG 2 · Structural-current endpoint evidence · 2012–2024", "B  Endpoint high-current evidence (2012–2024)", (6.65, 4.20, 10.60, 7.55)),
    ("FIG 3 · Robust conservation-priority core links", "C  Robust conservation-priority core links", (6.65, 0.50, 10.60, 3.85)),
)


def rectangle(xmin, ymin, xmax, ymax):
    return arcpy.Polygon(arcpy.Array([
        arcpy.Point(xmin, ymin), arcpy.Point(xmin, ymax),
        arcpy.Point(xmax, ymax), arcpy.Point(xmax, ymin),
    ]))


def layout_by_name(aprx, name):
    found = aprx.listLayouts(name)
    if found:
        # Preserve a previous draft; subsequent runs create a fresh dated page.
        return None
    return aprx.createLayout(11.0, 8.5, "INCH", name)


def add_title(layout, x, y, text):
    # ArcGIS Pro's installed Python API can create map frames but does not
    # expose a supported text-element constructor. Keep the panel caption in
    # the map-frame name so it is visible in Contents, then add final styled
    # titles manually in the Layout pane.
    print("manual layout title needed:", text)
    return None


def main():
    if not arcpy.Exists(CORE_SOURCE):
        raise FileNotFoundError(CORE_SOURCE)
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    BACKUPS.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUPS / f"Resistance_before_final_draft_layout_{stamp}.aprx"
    aprx.saveACopy(str(backup))

    layout = layout_by_name(aprx, LAYOUT_NAME)
    if layout is None:
        layout = aprx.createLayout(11.0, 8.5, "INCH", f"{LAYOUT_NAME} · {stamp}")
        print("NOTE: a prior draft layout was retained; created a dated new draft.")

    core_extent = arcpy.Describe(CORE_SOURCE).extent
    for map_name, title, bounds in PANELS:
        maps = aprx.listMaps(map_name)
        if len(maps) != 1:
            raise RuntimeError(f"Expected one prepared map named {map_name!r}; found {len(maps)}")
        map_object = maps[0]
        xmin, ymin, xmax, ymax = bounds
        frame = layout.createMapFrame(rectangle(xmin, ymin, xmax, ymax), map_object, map_name)
        frame.name = "Draft map frame | " + map_name
        frame.camera.setExtent(core_extent)
        frame.camera.scale *= 1.12
        add_title(layout, xmin, ymax + 0.10, title)

    add_title(layout, 0.40, 8.15, "Cheetah structural connectivity: final model outputs")
    aprx.save()
    print("backup:", backup)
    print("created layout:", layout.name)
    print("page: 11 x 8.5 inches, landscape")
    print("panel A: final 2024 structural current")
    print("panel B: endpoint temporal evidence")
    print("panel C: robust priority core-pair links")
    print("Complete. Add legends, scale bars, north arrows, source credits, and any local insets manually in the layout.")


if __name__ == "__main__":
    main()
