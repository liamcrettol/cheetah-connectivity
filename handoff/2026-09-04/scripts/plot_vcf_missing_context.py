"""Spatial diagnostic artifacts only; no GIS data or project edits."""
import csv
import json
from pathlib import Path
import arcpy
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

def export_spatial(ref, support, missing, water, land, other, stem):
    rows, cols = np.where(missing)
    x = ref.extent.XMin + (cols + .5) * ref.meanCellWidth
    y = ref.extent.YMax - (rows + .5) * ref.meanCellHeight
    labels = np.where(water, 'water_agreement_all_years', np.where(land, 'land_agreement_all_years', 'mixed_or_disagreeing'))
    with Path(str(stem) + '_cells.csv').open('x', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['row', 'column', 'easting_m', 'northing_m', 'center_classification_evidence'])
        writer.writerows(zip(rows.tolist(), cols.tolist(), x.tolist(), y.tolist(), labels.tolist()))
    # Deterministic 100 km bins anchored at projected coordinate zero.
    bins = np.column_stack((np.floor(x[other]/100000), np.floor(y[other]/100000))).astype(int)
    keys, nums = np.unique(bins, axis=0, return_counts=True)
    order = np.argsort(-nums, kind='stable')
    top = [{'xmin_m': int(keys[i,0]*100000), 'ymin_m': int(keys[i,1]*100000), 'ambiguous_cells': int(nums[i])} for i in order[:10]]
    with Path(str(stem) + '_spatial.json').open('x', encoding='utf-8') as f:
        json.dump({'top_100km_bins': top, 'note': 'Bins are descriptive, grid-origin dependent, not ecological regions.'}, f, indent=2)
    fig, axes = plt.subplots(1, 2, figsize=(13, 7))
    fig.subplots_adjust(left=.07, right=.98, bottom=.20, top=.83, wspace=.22)
    extent = [ref.extent.XMin/1000, ref.extent.XMax/1000, ref.extent.YMin/1000, ref.extent.YMax/1000]
    for ax in axes:
        ax.imshow(np.where(support, 1., np.nan), extent=extent, origin='upper', cmap=ListedColormap(['#eeeeee']), interpolation='nearest')
        for sel, color, marker, label in [(water, '#0072B2', 'o', 'Water agreement: 1,712'), (other, '#D55E00', 's', 'Mixed / disagreement: 3,097'), (land, '#7B3294', '^', 'Land agreement: 57')]:
            ax.scatter(x[sel]/1000, y[sel]/1000, s=8 if marker != '^' else 24, c=color, marker=marker, linewidths=0, label=label, zorder=3)
        ax.set_aspect('equal')
        ax.set_xlabel('Africa Albers easting (km)')
        ax.set_ylabel('Northing (km)')
    boundaries = r'C:\cheetah\raw\boundaries\natural_earth\ne_10m_admin_0_countries\ne_10m_admin_0_countries.shp'
    wanted = {'Namibia', 'Botswana', 'South Africa', 'Angola', 'Zambia', 'Zimbabwe', 'Mozambique'}
    with arcpy.da.SearchCursor(boundaries, ['ADMIN', 'SHAPE@']) as cursor:
        for name, geo in cursor:
            if name not in wanted:
                continue
            projected = geo.projectAs(ref.spatialReference)
            for part in projected:
                points = []
                for p in part:
                    if p is None:
                        if points:
                            for ax in axes: ax.plot(*np.array(points).T, color='#999999', linewidth=.5, zorder=2)
                        points = []
                    else: points.append((p.X/1000, p.Y/1000))
                if points:
                    for ax in axes: ax.plot(*np.array(points).T, color='#999999', linewidth=.5, zorder=2)
            p = projected.labelPoint
            axes[0].text(p.X/1000, p.Y/1000, name, fontsize=8, color='#555555', clip_on=True)
    axes[0].set_xlim(extent[:2]); axes[0].set_ylim(extent[2:])
    b = top[0]
    axes[1].set_xlim(b['xmin_m']/1000-25, b['xmin_m']/1000+125)
    axes[1].set_ylim(b['ymin_m']/1000-25, b['ymin_m']/1000+125)
    axes[0].set_title('All missing common-support cells')
    axes[1].set_title('Zoom: most populated ambiguous 100 km bin')
    fig.suptitle('Where vegetation is missing — and water classifications disagree', fontsize=16)
    handles, legend_labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, legend_labels, loc='lower center', bbox_to_anchor=(.5,.09), ncol=3, frameon=False)
    fig.text(.07,.045,'2012 / 2016 / 2020 / 2024 center flags; gray = existing model support. Markers enlarged for visibility.', fontsize=10)
    fig.text(.07,.018,'Diagnostic only: these are not whole-cell water fractions, barrier assignments, or conservation priorities.', fontsize=10)
    output = Path(str(stem) + '_map.png')
    fig.savefig(output, dpi=160)
    plt.close(fig)
    print('Spatial map:', output, flush=True)
    print('Largest ambiguous bins:', top[:3], flush=True)
