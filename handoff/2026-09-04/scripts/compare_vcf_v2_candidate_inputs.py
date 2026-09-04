"""Read-only input-impact audit; NO path/circuit solver or GIS writes.

Candidate total resistance = saved resistance + weight*(new V - old V).
This isolates vegetation input changes while holding every other term fixed.
It does not choose water barriers, impute missing cells or impose coverage cutoffs.
"""
import datetime as task_datetime
import hashlib
import json
from pathlib import Path
import arcpy
import numpy as np
from audit_downloaded_gee_validity import read_model, check_lattice, grid

GDB = Path(r'C:\cheetah\gdb\cheetah_working.gdb')
ROOT = Path(r'C:\cheetah\raw\source_qa\vcf_maskpreserved_v2_20260903')
YEARS = (2012, 2016, 2020, 2024)
NAMES = ['tree_pct_common_mean', 'nontree_pct_common_mean', 'bare_pct_common_mean',
         'common_usable_fraction', 'annual_usable_fraction', 'annual_source_valid_fraction',
         'annual_zero_triplet_fraction', 'annual_out_of_range_fraction']


def describe(a):
    a = a[np.isfinite(a)]
    if not a.size:
        return {'cells': 0}
    p = np.percentile(a, [0, 5, 50, 95, 99, 100])
    return dict(zip(['min', 'p05', 'median', 'p95', 'p99', 'max'], map(float, p)),
                cells=int(a.size), mean=float(a.mean()))


def vegetation(tree, nontree, bare):
    return 1 + .045 * (bare + 100 - np.minimum(100, tree + nontree))


def main():
    arcpy.CheckOutExtension('Spatial')
    ref = arcpy.Raster(str(GDB / 'resistance_temporal_veg_balanced_2012'))
    support = np.isfinite(read_model(GDB / 'resistance_temporal_veg_balanced_2012', ref))
    common_first = None
    new_v_by_year, old_v_by_year, results = {}, {}, []
    for year in YEARS:
        path = ROOT / f'vcf_maskpreserved_common_v2_{year}.tif'
        r = arcpy.Raster(str(path))
        check_lattice(r, ref)
        if r.height != ref.height or r.width != ref.width or list(r.bandNames) != NAMES:
            raise ValueError('Exact dimensions/band names failed: ' + str(path))
        if tuple(r.getRasterInfo().getNoDataValues()) != (-9999.0,) * 8:
            raise ValueError('NoData declarations failed')
        data = arcpy.RasterToNumPyArray(r, nodata_to_value=-9999).astype('float64')
        data[data == -9999] = np.nan
        tree, nt, bare, common, annual, source, zero, bad = data
        if not np.isfinite(data[3:]).all():
            raise ValueError('Missing coverage data in exported rectangle')
        if np.any(data[3:] < -1e-6) or np.any(data[3:] > 1.000001):
            raise ValueError('Coverage outside 0..1')
        if not np.array_equal(np.isfinite(tree), np.isfinite(nt)) or not np.array_equal(np.isfinite(tree), np.isfinite(bare)):
            raise ValueError('Cover-band masks differ')
        if not np.array_equal(np.isfinite(tree), common > 0):
            raise ValueError('Mean-cover validity inconsistent with common coverage')
        if np.any(data[:3][np.isfinite(data[:3])] < 0) or np.any(data[:3][np.isfinite(data[:3])] > 100.0001):
            raise ValueError('Cover outside 0..100')
        if np.any(common > annual + 1e-6) or np.any(annual > source + 1e-6):
            raise ValueError('Common/annual/source coverage ordering failed')
        if not np.allclose(annual, source-zero-bad, rtol=0, atol=1e-6):
            raise ValueError('Annual usable coverage accounting failed')
        if common_first is None:
            common_first = common.copy()
        elif not np.allclose(common_first, common, rtol=0, atol=1e-7):
            raise ValueError('Common native support differs by year')
        old = [read_model(GDB / f'vcf_{v}_{year}_aligned_1km', ref) for v in ('tree', 'nontree', 'bare')]
        old_v = read_model(GDB / f'vegetation_resistance_{year}_1_10', ref)
        recomputed_old = vegetation(*[np.clip(a, 0, 100) for a in old])
        if not np.allclose(old_v[support], recomputed_old[support], rtol=0, atol=2e-5):
            raise ValueError('Saved old vegetation transform did not match')
        new_v = vegetation(tree, nt, bare)
        compare = support & np.isfinite(new_v) & np.isfinite(old_v)
        delta = new_v - old_v
        old_zero = support & (old[0] == 0) & (old[1] == 0) & (old[2] == 0)
        item = {'year': year, 'source': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'model_cells': int(support.sum()), 'comparable_cells': int(compare.sum()),
                'coverage_bins': {
                    'zero': int(np.count_nonzero(support & (common == 0))),
                    'above0_below50pct': int(np.count_nonzero(support & (common > 0) & (common < .5))),
                    '50_to_below95pct': int(np.count_nonzero(support & (common >= .5) & (common < .95))),
                    'at_least95pct': int(np.count_nonzero(support & (common >= .95)))},
                'old_allzero_now_with_mean': int(np.count_nonzero(old_zero & compare)),
                'old_allzero_now_without_mean': int(np.count_nonzero(old_zero & ~np.isfinite(new_v))),
                'old_nonzero_now_without_mean': int(np.count_nonzero(support & ~old_zero & ~np.isfinite(new_v))),
                'cover_sum': describe((tree+nt+bare)[compare]),
                'common_fraction': describe(common[support]),
                'source_zero_triplet_max_fraction': float(zero[support].max()),
                'source_out_of_range_max_fraction': float(bad[support].max()),
                'vegetation_delta_signed': describe(delta[compare]),
                'vegetation_delta_absolute': describe(np.abs(delta[compare])),
                'cover_delta_absolute_pp': {name: describe(np.abs(new-old_a)[compare]) for name, new, old_a in zip(['tree','nontree','bare'], [tree,nt,bare], old)},
                'resistance_change': {}}
        for label, weight in [('low', .1), ('balanced', .2), ('high', .4)]:
            saved = read_model(GDB / f'resistance_temporal_veg_{label}_{year}', ref)
            if not np.isfinite(saved[support]).all() or np.any(saved[support] <= 0):
                raise ValueError('Old scenario invalid on model support')
            percent = 100 * weight * delta / saved
            item['resistance_change'][label] = {
                'abs_delta': describe(np.abs(weight * delta[compare])),
                'abs_percent_delta': describe(np.abs(percent[compare])),
                'signed_percent_delta': describe(percent[compare]),
                'pct_comparable_cells_above_1pct': float(np.mean(np.abs(percent[compare]) > 1) * 100),
                'pct_comparable_cells_above_5pct': float(np.mean(np.abs(percent[compare]) > 5) * 100),
                'pct_comparable_cells_above_10pct': float(np.mean(np.abs(percent[compare]) > 10) * 100),
                'abs_percent_delta_at_least95pct_coverage': describe(np.abs(percent[compare & (common >= .95)]))}
        new_v_by_year[year], old_v_by_year[year] = new_v.copy(), old_v
        results.append(item)
        balanced = item['resistance_change']['balanced']
        print(f'{year}: validation passed; common coverage bins {item["coverage_bins"]}', flush=True)
        print(f'  Balanced resistance absolute percent change: median {balanced["abs_percent_delta"]["median"]:.3f}, p95 {balanced["abs_percent_delta"]["p95"]:.3f}; >5% in {balanced["pct_comparable_cells_above_5pct"]:.2f}% of comparable cells', flush=True)
    core = read_model(GDB / 'cheetah_core_primary_density051_min500_1km', ref)
    common_valid = support & (common_first > 0)
    cores = {str(int(c)): {'original_cells': int(np.count_nonzero(support & (core == c))),
                          'with_new_mean': int(np.count_nonzero(common_valid & (core == c)))}
             for c in np.unique(core[np.isfinite(core) & (core > 0)])}
    temporal_delta = (new_v_by_year[2024]-new_v_by_year[2012]) - (old_v_by_year[2024]-old_v_by_year[2012])
    report = {'grid': grid(ref), 'results': results, 'core_pixel_screen': cores,
              'vegetation_2012_2024_change_difference': describe(temporal_delta[common_valid]),
              'vegetation_2012_2024_change_absolute_difference': describe(np.abs(temporal_delta[common_valid])),
              'notes': ['No new GIS raster or model was written; candidate resistance changes computed only in arrays.',
                        'Input changes combine aggregation, alignment, validity and common-native-support changes; not only zero handling.',
                        'Coverage bins and percent-change thresholds are descriptive diagnostics, not accepted biological cutoffs.',
                        'Cell-wise resistance differences do not establish route stability, effective resistance or priority-rank stability.',
                        'Missing mean cover is not a barrier; water and missing-land treatment remain unresolved.',
                        'No route or Circuitscape run performed. Existing outputs preserved.']}
    stem = Path(r'C:\cheetah\reports') / ('vcf_v2_input_impact_' + task_datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    with stem.with_suffix('.json').open('x', encoding='utf-8') as f:
        json.dump(report, f, indent=2)
    lines = ['# VCF v2 candidate input comparison', '', 'Read-only input check; no routes or Circuitscape recalculated.', '',
             '| Year | Comparable cells | Median absolute balanced-resistance change (%) | 95th percentile (%) | Cells exceeding 5% change (%) |',
             '|---|---:|---:|---:|---:|']
    for row in results:
        b = row['resistance_change']['balanced']
        lines.append(f'| {row["year"]} | {row["comparable_cells"]:,} | {b["abs_percent_delta"]["median"]:.3f} | {b["abs_percent_delta"]["p95"]:.3f} | {b["pct_comparable_cells_above_5pct"]:.2f} |')
    lines += ['', 'All percentages above describe comparable model cells, not paths or total habitat area.', '',
              'Common coverage bins (model cells): ' + json.dumps(results[0]['coverage_bins']), '',
              'These downloads are candidate inputs, not automatically approved production replacements.', '',
              '## Limits', ''] + ['- ' + n for n in report['notes']]
    with stem.with_suffix('.md').open('x', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    print(f'Reports: {stem}.json and .md', flush=True)


if __name__ == '__main__':
    main()
