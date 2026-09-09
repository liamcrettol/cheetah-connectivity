"""Read a completed current raster and draw a preliminary, non-destructive preview."""
import json
from pathlib import Path

import arcpy
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm, ListedColormap
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
from matplotlib import patheffects

ROOT = Path(r'C:\cheetah\circuitscape')
YEAR = 2016
SOURCE = ROOT / 'outputs' / f'current_primary_unfenced_{YEAR}_cum_curmap.tif'
OUT = ROOT / 'previews' / f'current_flow_{YEAR}_readable_preview.png'
COUNTRIES = r'C:\cheetah\raw\boundaries\natural_earth\ne_10m_admin_0_countries\ne_10m_admin_0_countries.shp'

def rings(geometry):
    for part in geometry:
        coords = []
        for p in part:
            if p is None:
                if coords:
                    yield np.asarray(coords)
                coords = []
            else:
                coords.append((p.X, p.Y))
        if coords:
            yield np.asarray(coords)

def main():
    manifest = json.loads((ROOT / 'inputs' / 'circuitscape_input_manifest.json').read_text())
    grid = manifest['grid']
    raster = arcpy.Raster(str(SOURCE))
    if (raster.width, raster.height) != (grid['columns'], grid['rows']):
        raise RuntimeError('Preview raster dimensions differ from verified inputs.')
    bounds = [grid[k] for k in ('xmin', 'xmax', 'ymin', 'ymax')]
    actual = [raster.extent.XMin, raster.extent.XMax, raster.extent.YMin, raster.extent.YMax]
    if not np.allclose(actual, bounds, atol=.01, rtol=0):
        raise RuntimeError(f'Preview extent mismatch: {actual} versus {bounds}')
    data = arcpy.RasterToNumPyArray(raster)
    valid = np.isfinite(data) & (data > 0)
    if raster.noDataValue is not None:
        valid &= data != raster.noDataValue
    cores = arcpy.Raster(manifest['core_source'])
    core_bounds = [cores.extent.XMin, cores.extent.XMax, cores.extent.YMin, cores.extent.YMax]
    if (cores.width, cores.height) != (raster.width, raster.height) or not np.allclose(core_bounds, bounds, atol=.01, rtol=0):
        raise RuntimeError('Core grid does not match current raster.')
    core_mask = arcpy.RasterToNumPyArray(cores, nodata_to_value=0) > 0
    exterior = valid & ~core_mask
    vals = data[exterior]
    if not vals.size:
        raise RuntimeError('No positive finite current values.')
    # Cartographic limits only: retain every positive exterior value, saturating
    # the tails at the endpoint colors. Never alter the input current raster.
    low, high = [float(v) for v in np.quantile(vals, [.02, .98])]
    print('exterior display quantiles:', np.quantile(vals, [0,.02,.5,.98,1]))
    sr = arcpy.SpatialReference(grid['wkid'])
    fig, ax = plt.subplots(figsize=(11.5, 10), facecolor='#f8fafc')
    ax.set_facecolor('#e9f1f6')
    outlines = []
    with arcpy.da.SearchCursor(COUNTRIES, ['SHAPE@']) as rows:
        for (geom,) in rows:
            e = geom.extent
            if e.XMax < 10 or e.XMin > 37 or e.YMax < -36 or e.YMin > -12:
                continue
            projected = geom.projectAs(sr)
            for ring in rings(projected):
                ax.fill(ring[:, 0], ring[:, 1], color='#edf0ee', linewidth=0, zorder=0)
                outlines.append(ring)
    image = ax.imshow(np.ma.array(data, mask=~exterior), extent=bounds, origin='upper',
                      cmap='magma', norm=LogNorm(vmin=low, vmax=high, clip=True), interpolation='nearest', zorder=2)
    ax.imshow(np.ma.array(np.ones(data.shape, dtype=np.uint8), mask=~core_mask),
              extent=bounds, origin='upper', cmap=ListedColormap(['#cbd2d7']),
              interpolation='nearest', zorder=3)
    for ring in outlines:
        ax.plot(ring[:, 0], ring[:, 1], color='#8f9ba4', linewidth=.6, alpha=.8, zorder=3)
    core_polygons = r'C:\cheetah\gdb\cheetah_working.gdb\cheetah_core_primary_density051_min500'
    with arcpy.da.SearchCursor(core_polygons, ['SHAPE@']) as rows:
        for (geom,) in rows:
            for ring in rings(geom.projectAs(sr)):
                ax.plot(ring[:, 0], ring[:, 1], color='#566774', linewidth=.65, zorder=4)
    wgs = arcpy.SpatialReference(4326)
    labels = [('Namibia', 16.7, -23.8), ('Botswana', 24.0, -22.8),
              ('Zimbabwe', 29.5, -19.1), ('Zambia', 27.0, -15.5),
              ('Angola', 17.9, -16.0), ('South Africa', 24.5, -30.9),
              ('Mozambique', 33.2, -23.5)]
    for name, lon, lat in labels:
        p = arcpy.PointGeometry(arcpy.Point(lon, lat), wgs).projectAs(sr).firstPoint
        ax.text(p.X, p.Y, name, fontsize=10, color='#263849', ha='center', zorder=5,
                path_effects=[patheffects.withStroke(linewidth=2.5, foreground='white', alpha=.9)])
    ax.set_xlim(bounds[0]-70000, bounds[1]+150000)
    ax.set_ylim(bounds[2]-100000, bounds[3]+70000)
    ax.set_aspect('equal')
    ax.axis('off')
    fig.suptitle('Between-core current flow | 2016', fontsize=19, fontweight='bold',
                 color='#162b3b', x=.08, ha='left', y=.965)
    fig.text(.08, .927, 'Preliminary preview · primary unfenced resistance · 23 fixed historical cores',
             fontsize=11, color='#526676')
    cb = fig.colorbar(image, ax=ax, fraction=.035, pad=.018, shrink=.68, extend='both')
    cb.set_ticks([low, np.sqrt(low*high), high])
    cb.set_ticklabels([f'Lower\n{low:.3g}', f'{np.sqrt(low*high):.3g}', f'Higher\n{high:.3g}'])
    cb.minorticks_off()
    cb.set_label('Modeled current concentration\n(raw current; logarithmic scale)', fontsize=11, labelpad=14)
    cb.ax.tick_params(labelsize=10)
    ax.legend(handles=[Patch(facecolor='#cbd2d7', edgecolor='#566774', label='Historical core regions')],
              loc='lower left', frameon=True, fontsize=10)
    fig.text(.08, .062, 'Yellow / cream = greater current concentration between cores. Gray = historical core regions.',
             fontsize=10, color='#263849')
    fig.text(.08, .041, 'Display stretched to the 2nd–98th percentiles outside cores; tail values use endpoint colors. Data unchanged.',
             fontsize=9, color='#526676')
    fig.text(.08, .022, 'Preliminary model output—not observed routes or a validated priority map. Zero/NoData omitted; QA pending.',
             fontsize=9, color='#526676')
    fig.subplots_adjust(left=.045, right=.87, top=.9, bottom=.09)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=170, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f'preview: {OUT}')
    print(f'positive current range: {low} to {high}; cells: {vals.size}')

if __name__ == '__main__':
    main()
