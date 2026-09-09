"""Create four separate full-page draft layouts for the final paper figures.

Figure 1: high-current concentration areas (descriptive, not biological pinch points)
Figure 2: temporal endpoint current evidence
Figure 3: robust conservation-priority core-pair links
Figure 4: protected-area context of high-current concentration

No existing layout is removed; this creates/reuses only the named draft layouts.
"""
import datetime as dt
from pathlib import Path

import arcpy


BACKUPS = Path(r"C:\cheetah\backups")
CORES = r"C:\cheetah\gdb\cheetah_working.gdb\cheetah_core_primary_density051_min500"
FIGURES = (
    ("FIG 1 · High-current concentration areas · 2024",
     "LAYOUT · Figure 1 · High-current concentration · draft"),
    ("FIG 2 · Structural-current endpoint evidence · 2012–2024",
     "LAYOUT · Figure 2 · Temporal current evidence · draft"),
    ("FIG 3 · Robust conservation-priority core links",
     "LAYOUT · Figure 3 · Robust priority links · draft"),
    ("FIG 4 · Protected-area context of high-current concentration · 2024",
     "LAYOUT · Figure 4 · Protected-area context · draft"),
)


def rectangle(xmin, ymin, xmax, ymax):
    return arcpy.Polygon(arcpy.Array([
        arcpy.Point(xmin, ymin), arcpy.Point(xmin, ymax),
        arcpy.Point(xmax, ymax), arcpy.Point(xmax, ymin),
    ]))


def get_high_current_map(aprx):
    """Rename an older candidate map if it was created before terminology cleanup."""
    desired = aprx.listMaps("FIG 1 · High-current concentration areas · 2024")
    if desired:
        return desired[0]
    old = aprx.listMaps("FIG 1b · Candidate current-concentration areas · 2024")
    if len(old) == 1:
        old[0].name = "FIG 1 · High-current concentration areas · 2024"
        for layer in old[0].listLayers():
            if "pinch" in layer.name.lower() or "candidate structural" in layer.name.lower():
                layer.name = "High-current concentration areas | 2024 modeled current"
        return old[0]
    raise RuntimeError("Figure 1 map is missing. Run create_candidate_current_concentration_map.py first.")


def fresh_layout(aprx, layout_name):
    existing = aprx.listLayouts(layout_name)
    if existing:
        # Retain prior author edits and make a new dated version instead.
        return aprx.createLayout(11.0, 8.5, "INCH", f"{layout_name} · {dt.datetime.now():%Y%m%d_%H%M%S}")
    return aprx.createLayout(11.0, 8.5, "INCH", layout_name)


def main():
    if not arcpy.Exists(CORES):
        raise FileNotFoundError(CORES)
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    BACKUPS.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUPS / f"Resistance_before_three_final_figure_layouts_{stamp}.aprx"
    aprx.saveACopy(str(backup))
    core_extent = arcpy.Describe(CORES).extent

    figure_maps = {"FIG 1 · High-current concentration areas · 2024": get_high_current_map(aprx)}
    for map_name, _ in FIGURES[1:]:
        matches = aprx.listMaps(map_name)
        if len(matches) != 1:
            raise RuntimeError(f"Expected exactly one prepared map named {map_name!r}; found {len(matches)}")
        figure_maps[map_name] = matches[0]

    layouts = []
    for map_name, layout_name in FIGURES:
        layout = fresh_layout(aprx, layout_name)
        # Leave 0.7 inches at the top for a manual title and 0.35-inch margins.
        frame = layout.createMapFrame(rectangle(0.35, 0.35, 10.65, 7.80), figure_maps[map_name], map_name)
        frame.name = "Map frame | " + map_name
        frame.camera.setExtent(core_extent)
        frame.camera.scale *= 1.08
        layouts.append(layout.name)

    aprx.save()
    print("backup:", backup)
    print("created individual draft layouts:")
    for name in layouts:
        print(" ", name)
    print("Suggested manual titles:")
    print(" Figure 1. High-current concentration areas under the final 2024 structural-connectivity model")
    print(" Figure 2. Persistence and endpoint change in high modeled current, 2012–2024")
    print(" Figure 3. Robust conservation-priority core-pair links")
    print(" Figure 4. Protected-area context of high-current concentration under the final 2024 model")
    print("Complete. No existing layout, map, raster, or analysis result was deleted or changed.")


if __name__ == "__main__":
    main()
