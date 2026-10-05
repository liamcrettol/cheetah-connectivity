"""Create an elephant-paper-style composite layout in the open ArcGIS Pro project.

Panel A is the 2012–2024 change in final balanced-fence resistance.  Panel B is
a 2x2 comparison of the 2024 baseline and three 2030 development scenarios.
The script creates new maps and one new layout; it does not alter existing maps,
layers, rasters, or analysis outputs.

Run in the ArcGIS Pro Python window with the target project open:
    import runpy
    runpy.run_path(r"C:\\path\\to\\create_historical_future_composite_layout.py",
                   run_name="__main__")
"""
from pathlib import Path
import datetime as dt
import arcpy

GDB = Path(r"C:\cheetah\gdb\cheetah_working.gdb")
BACKUPS = Path(r"C:\cheetah\backups")
CORES_NAME = "cheetah_core_primary_density051_min500"
PRIORITY_NAME = "conservation_priority_paths_temporal"
HIST_2012 = "resistance_final_balanced_fence_documented_2012"
HIST_2024 = "resistance_final_balanced_fence_documented_2024"
FUTURES = {
    "2030 low growth": "resistance_future2030_low_growth_balanced_fence",
    "2030 continuation": "resistance_future2030_continuation_balanced_fence",
    "2030 high development": "resistance_future2030_high_development_balanced_fence",
}


def find_dataset(name):
    """Resolve a dataset in the working GDB, including common raster aliases."""
    candidates = [GDB / name, GDB / (name + ".tif")]
    for p in candidates:
        if arcpy.Exists(str(p)):
            return str(p)
    # ArcGIS can expose a raster with a slightly different extension/name.
    for ras in arcpy.ListRasters("*" + name + "*") or []:
        p = GDB / ras
        if arcpy.Exists(str(p)):
            return str(p)
    raise FileNotFoundError(f"Could not find {name!r} in {GDB}")


def unique_name(aprx, base, kind="map"):
    names = {m.name for m in (aprx.listMaps() if kind == "map" else aprx.listLayouts())}
    if base not in names:
        return base
    i = 2
    while f"{base} · {i}" in names:
        i += 1
    return f"{base} · {i}"


def make_map(aprx, name, raster_path, cores_path, priority_path=None):
    m = aprx.createMap(unique_name(aprx, name))
    # A blank map keeps the panels publication-ready and avoids an unavailable
    # online basemap. The user can add the same basemap to all frames later.
    m.addDataFromPath(raster_path)
    if priority_path:
        m.addDataFromPath(priority_path)
    m.addDataFromPath(cores_path)
    return m


def box(x0, y0, x1, y1):
    return arcpy.Polygon(arcpy.Array([
        arcpy.Point(x0, y0), arcpy.Point(x1, y0),
        arcpy.Point(x1, y1), arcpy.Point(x0, y1),
        arcpy.Point(x0, y0),
    ]))


def text(layout, x, y, value, size=11, bold=False, name=None):
    """Add page text when supported; older Pro builds may lack this factory."""
    try:
        factory = getattr(arcpy.mp, "createTextElement", None)
        if factory is not None:
            el = factory(layout, arcpy.Point(x, y), "POINT", value, size,
                         "Arial", "Bold" if bold else "Regular",
                         name=name or value[:30])
        else:
            factory = getattr(layout, "createTextElement", None)
            if factory is None:
                print("WARNING: text elements are unsupported in this ArcGIS Pro build; skipped:", value)
                return None
            el = factory(arcpy.Point(x, y), "POINT", value)
        el.elementPositionX = x
        el.elementPositionY = y
        return el
    except (AttributeError, TypeError, RuntimeError) as exc:
        print("WARNING: could not add text element; skipped:", value, "|", exc)
        return None


def main():
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    cores = find_dataset(CORES_NAME)
    priority = find_dataset(PRIORITY_NAME)
    r2012 = find_dataset(HIST_2012)
    r2024 = find_dataset(HIST_2024)

    # Build the historical-change raster only if no existing change raster is present.
    change_name = "layout_historical_resistance_change_2012_2024"
    try:
        change = find_dataset(change_name)
    except FileNotFoundError:
        change = str(GDB / change_name)
        if not arcpy.Exists(change):
            from arcpy.sa import Raster
            (Raster(r2024) - Raster(r2012)).save(change)

    future_paths = {label: find_dataset(name) for label, name in FUTURES.items()}
    maps = {}
    maps["historical"] = make_map(aprx, "FIG A · Historical resistance change 2012–2024", change, cores, priority)
    maps["2024 baseline"] = make_map(aprx, "FIG B0 · 2024 baseline resistance", r2024, cores)
    for label, path in future_paths.items():
        maps[label] = make_map(aprx, "FIG B · " + label, path, cores)

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    BACKUPS.mkdir(parents=True, exist_ok=True)
    backup = BACKUPS / f"Resistance_before_historical_future_composite_layout_{stamp}.aprx"
    aprx.saveACopy(str(backup))

    layout_name = unique_name(aprx, "LAYOUT · Historical change + 2030 scenarios · draft", "layout")
    layout = aprx.createLayout(16.0, 10.0, "INCH", layout_name)
    # Shared map extent comes from the final 2024 surface, so all panels align.
    extent = arcpy.Describe(r2024).extent
    frames = [
        ("A", maps["historical"], 0.45, 0.65, 8.65, 8.55, "Historical resistance change | 2012–2024"),
        ("B", maps["2024 baseline"], 9.45, 5.05, 15.55, 8.85, "2024 baseline"),
        ("C", maps["2030 low growth"], 9.45, 0.65, 15.55, 4.45, "2030 low growth"),
        ("D", maps["2030 continuation"], 10.05, 5.05, 15.55, 8.85, "2030 continuation"),
        ("E", maps["2030 high development"], 10.05, 0.65, 15.55, 4.45, "2030 high development"),
    ]
    # Use a clean 2x2 right column; B/C occupy the left half and D/E the right.
    frames = [
        ("A", maps["historical"], 0.45, 0.65, 8.85, 8.85, "Historical resistance change | 2012–2024"),
        ("B", maps["2024 baseline"], 9.25, 5.05, 12.55, 8.85, "2024 baseline"),
        ("C", maps["2030 low growth"], 12.75, 5.05, 15.55, 8.85, "2030 low growth"),
        ("D", maps["2030 continuation"], 9.25, 0.65, 12.55, 4.45, "2030 continuation"),
        ("E", maps["2030 high development"], 12.75, 0.65, 15.55, 4.45, "2030 high development"),
    ]
    text(layout, 0.55, 9.45, "Connectivity change and projected 2030 resistance scenarios", 20, True, "Figure title")
    text(layout, 0.55, 9.05, "Modeled structural resistance; scenario comparison, not a movement-occurrence forecast", 9, False, "Figure subtitle")
    for label, m, x0, y0, x1, y1, title in frames:
        frame = layout.createMapFrame(box(x0, y0, x1, y1), m, f"Panel {label} map frame")
        frame.camera.setExtent(extent)
        frame.camera.scale *= 1.03
        text(layout, x0 + 0.08, y1 + 0.10, f"{label}. {title}", 11, True, f"Panel {label} title")
    text(layout, 0.55, 0.25, "Cores and robust links are shown as contextual overlays; apply final neutral paper symbology and legend before export.", 8, False, "Figure note")
    aprx.save()
    print("backup:", backup)
    print("created maps:", ", ".join(m.name for m in maps.values()))
    print("created layout:", layout.name)
    print("historical change raster:", change)
    print("Complete. Existing maps, layers, rasters, and analysis outputs were not modified.")


if __name__ == "__main__":
    main()
