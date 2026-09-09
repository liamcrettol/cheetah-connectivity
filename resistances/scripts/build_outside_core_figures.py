"""Rebuild the current-derived paper figures on the outside-core domain.

Replaces three source-inclusive figures whose visible pattern was the fixed core
footprint rather than connecting landscape, and replaces the straight-line
priority-link figure with the actual least-cost geometry.

    fig1_current_outside_cores_2024        modelled current outside cores, 2024
    fig2_current_change_outside_cores      change in that current, 2012 to 2024
    fig3_priority_links_least_cost_paths   the 32 primary and 13 uncertainty links
                                           drawn as least-cost paths, not straight lines

The coverage-versus-percentile figure produced by
``recompute_outside_core_current_context.py`` is the fourth.

Design decisions worth knowing
------------------------------
Cores are drawn as outlines, never as filled patches, because filling them is
what made the earlier figures look like a corridor result.

Current is classed by percentile of the outside-core distribution rather than by
raw value. Raw outside-core current spans roughly 1e-13 to 3e-3 and no linear or
log ramp reads usefully; the analysis is percentile-based anyway.

There is no north arrow. In Africa Albers Equal Area Conic across a 2,310 km
extent, grid north and true north diverge visibly away from the central
meridian, so a single arrow would be wrong over most of the map. A graticule is
drawn instead.

Protected areas come from the 1 km coverage raster rather than the dissolved
polygon, which carries 376,991 vertices and is slow to render.

Read-only. Writes PNG and PDF to REPORTS and to this folder's figures/.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np
from osgeo import gdal, ogr, osr

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

gdal.UseExceptions()

WORK_GDB = r"C:\cheetah\gdb\cheetah_working.gdb"
CURRENT_GDB = r"C:\cheetah\circuitscape\derived\current_final_balanced_fence.gdb"
CORE_RASTER = "cheetah_core_primary_density051_min500_1km"
PA_RASTER = "wdpa_aug2026_coverage_1km"
CURRENT_TEMPLATE = "current_final_balanced_fence_{year}_mean"

CORE_POLYGONS = "cheetah_core_primary_density051_min500"
COUNTRIES = "countries_in_study_extent"
PRIORITY_PATHS = "conservation_priority_paths_temporal"
UNCERTAINTY_PATHS = "conservation_uncertainty_paths_temporal"

REPORTS = Path(r"C:\cheetah\reports")
FIGURES = Path(__file__).resolve().parent.parent / "figures"

CURRENT_CLASSES = (0, 50, 80, 90, 95, 99, 100)
CURRENT_LABELS = ("below 50th", "50th-80th", "80th-90th",
                  "90th-95th", "95th-99th", "99th and above")
CURRENT_COLORS = ("#fbf7ef", "#cfe0e8", "#9dc3d4", "#5f97b5", "#2f6d92", "#14415e")

CHANGE_COLORS = ("#8c3d1f", "#c97b4e", "#eabf9a", "#f2f0eb",
                 "#a8c9bd", "#5a9782", "#1f6350")

INK = "#1a1a1a"
GRID_GREY = "#b9b6ae"
PA_GREY = "#dedbd2"

NP_DTYPE = {
    gdal.GDT_Byte: "u1", gdal.GDT_Int16: "i2", gdal.GDT_UInt16: "u2",
    gdal.GDT_Int32: "i4", gdal.GDT_UInt32: "u4",
    gdal.GDT_Float32: "f4", gdal.GDT_Float64: "f8",
}


def read_raster(gdb: str, name: str):
    dataset = gdal.Open(f'OpenFileGDB:"{gdb}":{name}')
    band = dataset.GetRasterBand(1)
    raw = band.ReadRaster(0, 0, dataset.RasterXSize, dataset.RasterYSize)
    array = np.frombuffer(raw, dtype=NP_DTYPE[band.DataType])
    array = array.reshape(dataset.RasterYSize, dataset.RasterXSize)
    return array, band.GetNoDataValue(), dataset.GetGeoTransform(), dataset.GetProjection()


def extent_from(geotransform, shape):
    rows, cols = shape
    left = geotransform[0]
    top = geotransform[3]
    right = left + cols * geotransform[1]
    bottom = top + rows * geotransform[5]
    return (left, right, bottom, top)


def read_geometries(gdb: str, layer_name: str):
    """Return each feature as a list of coordinate arrays, plus its attributes."""
    source = ogr.Open(gdb)
    layer = source.GetLayerByName(layer_name)
    features = []
    for feature in layer:
        geometry = feature.GetGeometryRef()
        if geometry is None:
            continue
        parts = []

        def walk(node):
            count = node.GetGeometryCount()
            if count == 0:
                if node.GetPointCount():
                    parts.append(np.asarray(node.GetPoints())[:, :2])
                return
            for index in range(count):
                walk(node.GetGeometryRef(index))

        walk(geometry)
        attributes = {feature.GetFieldDefnRef(i).GetName(): feature.GetField(i)
                      for i in range(feature.GetFieldCount())}
        features.append((parts, attributes))
    source = None
    return features


def draw_lines(axis, features, **kwargs):
    for parts, _ in features:
        for coords in parts:
            axis.plot(coords[:, 0], coords[:, 1], **kwargs)
            kwargs.pop("label", None)


def draw_graticule(axis, projection_wkt, extent, step=5):
    """Graticule in place of a north arrow; see module docstring."""
    target = osr.SpatialReference(wkt=projection_wkt)
    source = osr.SpatialReference()
    source.ImportFromEPSG(4326)
    source.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    transform = osr.CoordinateTransformation(source, target)

    left, right, bottom, top = extent
    for lon in range(-10, 51, step):
        pts = [transform.TransformPoint(lon, lat)[:2] for lat in np.linspace(-40, 0, 120)]
        pts = np.asarray(pts)
        axis.plot(pts[:, 0], pts[:, 1], color=GRID_GREY, linewidth=0.4,
                  linestyle=(0, (1, 4)), zorder=1.5)
    for lat in range(-40, 1, step):
        pts = [transform.TransformPoint(lon, lat)[:2] for lon in np.linspace(-10, 50, 160)]
        pts = np.asarray(pts)
        axis.plot(pts[:, 0], pts[:, 1], color=GRID_GREY, linewidth=0.4,
                  linestyle=(0, (1, 4)), zorder=1.5)
    axis.set_xlim(left, right)
    axis.set_ylim(bottom, top)


def draw_scalebar(axis, extent, length_km=500):
    left, right, bottom, top = extent
    span = right - left
    x0 = left + 0.05 * span
    y0 = bottom + 0.055 * (top - bottom)
    length = length_km * 1000.0
    axis.plot([x0, x0 + length], [y0, y0], color=INK, linewidth=2.4,
              solid_capstyle="butt", zorder=6)
    for offset in (0, length):
        axis.plot([x0 + offset, x0 + offset], [y0, y0 + 0.012 * (top - bottom)],
                  color=INK, linewidth=2.4, zorder=6)
    axis.text(x0 + length / 2, y0 + 0.02 * (top - bottom), f"{length_km} km",
              ha="center", va="bottom", fontsize=8, color=INK, zorder=6)


def base_axes(title, subtitle, extent, projection_wkt, countries, cores,
              pa_masked, valid):
    figure, axis = plt.subplots(figsize=(9.2, 8.4))
    axis.set_facecolor("#ffffff")

    # Protected areas are clipped to the analysis domain. The WDPA raster covers
    # the whole grid, and drawing designations the model never evaluated
    # implies a coverage claim outside the study extent.
    axis.imshow(pa_masked, extent=extent, origin="upper",
                cmap=ListedColormap([PA_GREY]), interpolation="nearest", zorder=1)

    draw_graticule(axis, projection_wkt, extent)
    draw_lines(axis, countries, color="#8d8a82", linewidth=0.7, zorder=4)

    # Analysis-domain boundary, so a reader can see where the model stops
    # rather than inferring it from where colour fades out.
    axis.contour(valid.astype(float), levels=[0.5], extent=extent, origin="upper",
                 colors="#6f6b63", linewidths=0.8, zorder=4.5)

    draw_lines(axis, cores, color=INK, linewidth=0.9, zorder=5)
    axis.set_aspect("equal")
    axis.set_xticks([])
    axis.set_yticks([])
    for spine in axis.spines.values():
        spine.set_edgecolor("#5a5750")
        spine.set_linewidth(0.8)

    lines = subtitle.count("\n") + 1
    axis.text(0, 1.008, subtitle, transform=axis.transAxes, fontsize=8.6,
              color="#57544d", va="bottom", linespacing=1.45)
    axis.text(0, 1.028 + 0.019 * lines, title, transform=axis.transAxes,
              fontsize=13.5, color=INK, va="bottom", weight="semibold")
    draw_scalebar(axis, extent)
    return figure, axis


def save(figure, stem, stamp):
    FIGURES.mkdir(parents=True, exist_ok=True)
    for directory in (REPORTS, FIGURES):
        figure.savefig(directory / f"{stem}_{stamp}.png", dpi=240,
                       bbox_inches="tight", facecolor="white")
    figure.savefig(FIGURES / f"{stem}_{stamp}.pdf", bbox_inches="tight",
                   facecolor="white")
    plt.close(figure)
    print(f"  {stem}_{stamp}")


def main() -> None:
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    REPORTS.mkdir(parents=True, exist_ok=True)

    core_raster, _, geotransform, projection = read_raster(WORK_GDB, CORE_RASTER)
    pa_raster, _, _, _ = read_raster(WORK_GDB, PA_RASTER)
    current_2024, nodata, _, _ = read_raster(CURRENT_GDB, CURRENT_TEMPLATE.format(year=2024))
    current_2012, _, _, _ = read_raster(CURRENT_GDB, CURRENT_TEMPLATE.format(year=2012))

    extent = extent_from(geotransform, core_raster.shape)
    in_core = core_raster > 0
    valid_2024 = np.isfinite(current_2024) & (current_2024 != nodata)
    valid_2012 = np.isfinite(current_2012) & (current_2012 != nodata)
    domain = valid_2024 & ~in_core & (current_2024 > 0)

    analysis_domain = valid_2024
    pa_masked = np.ma.masked_where((pa_raster == 0) | ~analysis_domain, pa_raster)

    countries = read_geometries(WORK_GDB, COUNTRIES)
    cores = read_geometries(WORK_GDB, CORE_POLYGONS)

    print("figures:")

    # ---------------------------------------------------------------- figure 1
    values = current_2024[domain]
    edges = [values.min()] + [np.percentile(values, p) for p in CURRENT_CLASSES[1:-1]]
    edges = edges + [values.max()]
    classed = np.digitize(current_2024, edges[1:-1], right=False).astype(float)
    classed[~domain] = np.nan

    figure, axis = base_axes(
        "Modelled current concentration outside range cores, 2024",
        "Vegetation-balanced resistance with documented finite fences. Classed by percentile of "
        "outside-core current.\nInput cores shown as outlines and excluded; protected areas in grey. "
        "Structural flow, not observed movement.",
        extent, projection, countries, cores, pa_masked, analysis_domain)
    axis.imshow(np.ma.masked_invalid(classed), extent=extent, origin="upper",
                cmap=ListedColormap(CURRENT_COLORS),
                norm=BoundaryNorm(range(len(CURRENT_COLORS) + 1), len(CURRENT_COLORS)),
                interpolation="nearest", zorder=3)
    axis.legend(handles=[Patch(facecolor=c, edgecolor="none", label=l)
                         for c, l in zip(CURRENT_COLORS, CURRENT_LABELS)]
                        + [Line2D([], [], color=INK, lw=0.9, label="range core (excluded)"),
                           Patch(facecolor=PA_GREY, edgecolor="none", label="protected area")],
                loc="lower right", fontsize=8, frameon=True, framealpha=0.94,
                edgecolor="#c8c5bd", title="Percentile of current", title_fontsize=8.4)
    save(figure, "fig1_current_outside_cores_2024", stamp)

    # ---------------------------------------------------------------- figure 2
    # Percent rather than absolute difference. Absolute change is on the order
    # of 7e-6 against a median current of 2.8e-4, which is unreadable; the
    # median relative change is 4.3% and the 90th percentile 10.7%, which is
    # both interpretable and comfortably above solver convergence noise.
    shared = domain & valid_2012 & (current_2012 > 0)
    difference = np.where(
        shared, 100.0 * (current_2024 - current_2012) / np.where(shared, current_2012, 1.0),
        np.nan)
    bounds = [-20, -10, -5, -2, 2, 5, 10, 20]
    figure, axis = base_axes(
        "Change in modelled current outside range cores, 2012 to 2024",
        "Percent change in cumulative current on the shared outside-core domain; median absolute "
        "change 4.3%. Brown lost, green gained.\nLandscape-side change only: cores are fixed at the "
        "2010-2016 baseline. Read against Figure 1: the low-current periphery, including the western\n"
        "strip, carries negligible absolute flow, so a large relative change there is not a "
        "conservation signal.",
        extent, projection, countries, cores, pa_masked, analysis_domain)
    colormap = ListedColormap(CHANGE_COLORS).with_extremes(
        under="#5e2410", over="#0e402f")
    image = axis.imshow(np.ma.masked_invalid(difference), extent=extent, origin="upper",
                        cmap=colormap, norm=BoundaryNorm(bounds, len(CHANGE_COLORS)),
                        interpolation="nearest", zorder=3)
    colorbar = figure.colorbar(image, ax=axis, fraction=0.031, pad=0.015,
                               extend="both", ticks=bounds)
    colorbar.set_label("Change in modelled current, 2012 to 2024 (%)", fontsize=8.4)
    colorbar.ax.tick_params(labelsize=7)
    colorbar.ax.set_yticklabels([f"{v:+d}%" for v in bounds])
    save(figure, "fig2_current_change_outside_cores", stamp)

    # ---------------------------------------------------------------- figure 3
    priority = read_geometries(WORK_GDB, PRIORITY_PATHS)
    uncertainty = read_geometries(WORK_GDB, UNCERTAINTY_PATHS)
    figure, axis = base_axes(
        "Priority and uncertainty links as modelled least-cost paths",
        f"{len(priority)} links robust to weighting, fencing and vegetation direction; "
        f"{len(uncertainty)} retained as uncertainty and survey priorities.\nRoutes are modelled "
        "least-cost paths between fixed cores, not observed crossings, and route location is less "
        "stable than route cost.",
        extent, projection, countries, cores, pa_masked, analysis_domain)
    draw_lines(axis, uncertainty, color="#c07a33", linewidth=1.5, zorder=6,
               linestyle=(0, (5, 2)), label=f"uncertainty link (n={len(uncertainty)})")
    draw_lines(axis, priority, color="#14415e", linewidth=1.9, zorder=7,
               label=f"primary priority link (n={len(priority)})")
    axis.legend(handles=[Line2D([], [], color="#14415e", lw=1.9,
                                label=f"primary priority link (n={len(priority)})"),
                         Line2D([], [], color="#c07a33", lw=1.5, linestyle=(0, (5, 2)),
                                label=f"uncertainty link (n={len(uncertainty)})"),
                         Line2D([], [], color=INK, lw=0.9, label="range core"),
                         Patch(facecolor=PA_GREY, edgecolor="none", label="protected area")],
                loc="lower right", fontsize=8, frameon=True, framealpha=0.94,
                edgecolor="#c8c5bd")
    save(figure, "fig3_priority_links_least_cost_paths", stamp)

    print(f"\nwritten to {FIGURES}")
    print(f"and {REPORTS}")


if __name__ == "__main__":
    main()
