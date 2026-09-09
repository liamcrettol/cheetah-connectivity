"""Read-only GIS preflight. Writes timestamped audit reports only; runs no solver.

Checks saved arrays against recorded formulas, not ecological validity. Does not
repair, export, resample, calculate statistics, or modify map/project datasets.
Run in ArcGIS Pro Python or its bundled Python interpreter.
"""
import csv
import datetime as task_datetime
import hashlib
import json
import os
from pathlib import Path

import arcpy
import numpy as np

GDB = Path(r'C:\cheetah\gdb\cheetah_working.gdb')
SOURCE_GDB = Path(r'C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah_connectivity.gdb')
REPORTS = Path(r'C:\cheetah\reports')
YEARS = (2012, 2016, 2020, 2024)
WEIGHTS = {'veg_low': (0.7, 0.1, 0.2), 'veg_balanced': (0.6, 0.2, 0.2),
           'veg_high': (0.4, 0.4, 0.2)}
TOL = 0.00005  # float32 arithmetic tolerance on the 1--10 surfaces


def main():
    failures, inventory, comparisons, coverage = [], [], [], []
    arcpy.CheckOutExtension('Spatial')
    manifest_path = Path(r'C:\cheetah\circuitscape\inputs\circuitscape_input_manifest.json')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    ref = manifest['grid']

    def read(name, check_grid=True):
        candidates = [GDB / name, SOURCE_GDB / name]
        path = next((p for p in candidates if arcpy.Exists(str(p))), None)
        if path is None:
            raise FileNotFoundError(name)
        r = arcpy.Raster(str(path))
        sr = r.spatialReference
        grid = [r.width, r.height, r.meanCellWidth, r.meanCellHeight,
                r.extent.XMin, r.extent.YMin, r.extent.XMax, r.extent.YMax]
        expected = [ref['columns'], ref['rows'], ref['cell_width'], ref['cell_height'],
                    ref['xmin'], ref['ymin'], ref['xmax'], ref['ymax']]
        same = bool(np.allclose(grid, expected, rtol=0, atol=0.001))
        same_crs = sr.factoryCode == ref['wkid'] and sr.type == 'Projected'
        a = arcpy.RasterToNumPyArray(r).astype(np.float64)
        # File-geodatabase Raster.noDataValue may be None while the raster has
        # a separate validity mask. Never infer validity from numeric zeros.
        with arcpy.EnvManager(extent=r.extent, snapRaster=str(path), cellSize=str(path),
                              mask=None, outputCoordinateSystem=sr):
            nulls = arcpy.RasterToNumPyArray(arcpy.sa.IsNull(r)).astype(bool)
        if nulls.shape != a.shape:
            raise ValueError(f'NoData mask grid differs: {name}')
        a[nulls] = np.nan
        valid = np.isfinite(a)
        record = {'name': name, 'path': str(path), 'grid': grid,
                  'same_grid': same, 'same_crs': same_crs, 'wkid': sr.factoryCode,
                  'valid_cells': int(valid.sum()),
                  'minimum': float(a[valid].min()) if valid.any() else None,
                  'maximum': float(a[valid].max()) if valid.any() else None,
                  'array_sha256': hashlib.sha256(a.tobytes()).hexdigest()}
        inventory.append(record)
        if check_grid and not (same and same_crs):
            raise ValueError(f'Grid/CRS mismatch: {name}')
        if not valid.any():
            raise ValueError(f'No finite data: {name}')
        return a

    def compare(label, actual, expected):
        av, ev = np.isfinite(actual), np.isfinite(expected)
        common = av & ev
        mismatch = int(np.count_nonzero(av != ev))
        delta = float(np.max(np.abs(actual[common] - expected[common]))) if common.any() else None
        ok = mismatch == 0 and delta is not None and delta <= TOL
        comparisons.append({'test': label, 'pass': ok, 'mask_mismatch_cells': mismatch,
                            'max_absolute_error': delta, 'tolerance': TOL})
        if not ok:
            failures.append(label)

    cores = read('cheetah_core_primary_density051_min500_1km')
    ids = sorted(int(v) for v in np.unique(cores[np.isfinite(cores) & (cores > 0)]))
    if ids != manifest['core_ids'] or len(ids) != 23:
        failures.append('Fixed core IDs differ from completed reference run')
    terrain = read('terrain_resistance_1_10')
    if np.nanmin(terrain) < 1 - TOL or np.nanmax(terrain) > 10 + TOL:
        failures.append('Terrain outside 1--10')
    slope = read('slope_mean_1km')
    terrain_expected = 1 + 9 * np.clip((slope - 10) / 20, 0, 1)
    compare('terrain reconstructed from mean slope', terrain, terrain_expected)
    del slope, terrain_expected
    register_path = REPORTS / 'temporal_vegetation_sensitivity_register.csv'
    with register_path.open(encoding='utf-8-sig', newline='') as f:
        register = list(csv.DictReader(f))
    vcf_notes = []
    common_support = None
    for year in YEARS:
        reference = read(f'resistance_primary_unfenced_combined_{year}')
        # Recover A from saved reference = .8*A + .2*T. This checks agreement
        # between model generations, not independent accuracy of source A.
        anthropogenic = (reference - .2 * terrain) / .8
        vegetation = read(f'vegetation_resistance_{year}_1_10')
        tree = read(f'vcf_tree_{year}_aligned_1km')
        non = read(f'vcf_nontree_{year}_aligned_1km')
        bare = read(f'vcf_bare_{year}_aligned_1km')
        valid_vcf = np.isfinite(tree) & np.isfinite(non) & np.isfinite(bare)
        vcf_notes.append({'year': year,
            'valid_triplets': int(valid_vcf.sum()),
            'out_of_0_100_cells': int(np.count_nonzero(valid_vcf &
                ((tree < 0) | (tree > 100) | (non < 0) | (non > 100) | (bare < 0) | (bare > 100)))),
            'all_zero_triplets': int(np.count_nonzero(valid_vcf & (tree == 0) & (non == 0) & (bare == 0))),
            'sum_differs_from_100_by_more_than_5': int(np.count_nonzero(valid_vcf &
                (np.abs(tree + non + bare - 100) > 5)))})
        expected_v = 1 + 9 * (np.clip(bare, 0, 100) +
            100 - np.minimum(100, np.clip(tree, 0, 100) + np.clip(non, 0, 100))) / 200
        compare(f'{year} vegetation transform', vegetation, expected_v)
        del tree, non, bare, expected_v
        for label, (wa, wv, wt) in WEIGHTS.items():
            rows = [r for r in register if r['scenario'] == label and int(r['year']) == year]
            if len(rows) != 1 or not np.allclose(
                [float(rows[0][k]) for k in ('anthropogenic_weight', 'vegetation_weight', 'terrain_weight')],
                [wa, wv, wt], rtol=0, atol=1e-12):
                failures.append(f'{label} {year}: decision register mismatch')
            name = f'resistance_temporal_{label}_{year}'
            actual = read(name)
            compare(name, actual, wa * anthropogenic + wv * vegetation + wt * terrain)
            support = np.isfinite(actual)
            if np.nanmin(actual) < 1 - TOL or np.nanmax(actual) > 10 + TOL:
                failures.append(f'{name}: outside 1--10')
            if common_support is None:
                common_support = support.copy()
            elif not np.array_equal(common_support, support):
                failures.append(f'{name}: support differs between scenarios/years')
            counts = {str(cid): int(np.count_nonzero((cores == cid) & support)) for cid in ids}
            excluded = int(np.count_nonzero(np.isfinite(cores) & (cores > 0) & ~support))
            coverage.append({'scenario': label, 'year': year, 'retained_core_cells': counts,
                             'excluded_core_cells': excluded})
            if any(n == 0 for n in counts.values()):
                failures.append(f'{name}: a core completely excluded')
            del actual
        print(f'{year}: vegetation formula, all three weights, grid and core coverage checked', flush=True)
        del reference, anthropogenic, vegetation

    fence_notes = []
    kaza = read('fence_presence_1km')
    kaza_main = read('fence_multiplier_main_1km')
    kaza_barrier = read('fence_multiplier_nearbarrier_1km')
    for value, multiplier, label in [(25, kaza_main, 'KAZA crossable'), (1000, kaza_barrier, 'KAZA near-barrier')]:
        expected = np.where(np.isfinite(kaza), np.where(kaza == 1, value, 1), np.nan)
        compare(label, multiplier, expected)
    for variant in ('documented', 'conservative'):
        presence = read(f'kruger_fence_presence_{variant}_1km')
        multiplier = read(f'kruger_fence_multiplier_{variant}_1km')
        expected = np.where(np.isfinite(presence), np.where(presence == 1, 25, 1), np.nan)
        compare(f'Kruger {variant}', multiplier, expected)
        combined = read(f'fence_multiplier_main_kruger_{variant}_1km')
        compare(f'KAZA plus Kruger {variant}, no double penalty', combined, np.fmax(kaza_main, multiplier))
        holes = int(np.count_nonzero(common_support & ~np.isfinite(combined)))
        if holes:
            failures.append(f'Fence multiplier {variant}: missing within balanced landscape')
        fence_notes.append({'variant': variant,
                            'penalized_cells_in_balanced_landscape': int(np.count_nonzero(common_support & (combined > 1))),
                            'missing_cells_in_balanced_landscape': holes})
    print('Fence presence, multipliers and overlap rule checked; none applied to inputs.', flush=True)

    stamp = task_datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    report = {'assessment': 'Needs reconciliation before a full-model run',
              'numerical_failures': failures, 'dataset_inventory': inventory,
              'formula_checks': comparisons, 'core_coverage': coverage, 'vcf_checks': vcf_notes,
              'fence_checks': fence_notes,
              'scope': 'Read-only raster/formula preflight, not movement validation or connectivity solve',
              'planned_candidate': {str(y): str(GDB / f'resistance_temporal_veg_balanced_{y}') for y in YEARS},
              'unresolved_and_required_caveats': [
                  'Completed current flow uses pressure+terrain, not vegetation-balanced inputs.',
                  'Balanced surfaces contain no fence penalties; fence sensitivity remains a separate factor.',
                  '25 and 1000 are assumed multipliers, not measured cheetah permeability.',
                  'An older decision CSV assigns VCF zero weight; later temporal register supersedes that scope.',
                  'Vegetation transform is a sparse/bare proxy, not a fitted vegetation-structure response.',
                  'All-zero VCF triplets and noncomplementary fractions require contextual inspection, not silent clamping.',
                  'Recovered anthropogenic component checks inter-version consistency, not independent raw-source reconstruction.',
                  'Current-flow runs use all 253 core pairs, not the 45 selected least-cost pairs.',
                  'Existing fence/weight robustness of selected LCPs does not establish current-flow robustness.',
                  'No solver execution, GIS edits, source repairs, or automatic approval performed.']}
    REPORTS.mkdir(exist_ok=True)
    out = REPORTS / f'circuitscape_full_model_preflight_{stamp}.json'
    out.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f'numerical checks: {len(comparisons)}; failures: {len(failures)}', flush=True)
    for failure in failures:
        print('REVIEW: ' + failure)
    print(f'VCF checks: {json.dumps(vcf_notes)}', flush=True)
    print(f'report: {out}', flush=True)
    print('No solver started. No rasters, statistics, map layers or project files changed.')
    return report


if __name__ == '__main__':
    _audit = main()
