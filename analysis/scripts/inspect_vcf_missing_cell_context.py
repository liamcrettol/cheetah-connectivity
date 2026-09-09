"""Read-only missing-VCF context; writes versioned reports, never model data."""
import datetime as task_datetime
import json
from pathlib import Path
import arcpy
import numpy as np
from audit_downloaded_gee_validity import read_model, check_lattice, grid, BANDS
from compare_vcf_v2_candidate_inputs import NAMES

GDB = Path(r'C:\cheetah\gdb\cheetah_working.gdb')
ROOT = Path(r'C:\cheetah\raw\source_qa')
YEARS = (2012, 2016, 2020, 2024)

def main():
    arcpy.CheckOutExtension('Spatial')
    ref = arcpy.Raster(str(GDB / 'resistance_temporal_veg_balanced_2012'))
    support = np.isfinite(read_model(GDB / 'resistance_temporal_veg_balanced_2012', ref))
    missing = None
    categories, annuals, details = [], [], []
    for year in YEARS:
        p = ROOT / 'vcf_maskpreserved_v2_20260903' / f'vcf_maskpreserved_common_v2_{year}.tif'
        r = arcpy.Raster(str(p))
        check_lattice(r, ref)
        assert r.width == ref.width and r.height == ref.height and list(r.bandNames) == NAMES
        data = arcpy.RasterToNumPyArray(r, nodata_to_value=-9999)
        m = support & (data[3] == 0)
        assert np.array_equal(data[0] == -9999, data[3] == 0)
        if missing is None:
            missing = m.copy()
        assert np.array_equal(missing, m)
        annuals.append(data[4][m].copy())
        q = ROOT / 'gee_validity_20260903' / f'cheetah_source_validity_audit_v1_{year}.tif'
        qr = arcpy.Raster(str(q))
        check_lattice(qr, ref)
        assert list(qr.bandNames) == BANDS
        flags = arcpy.RasterToNumPyArray(qr, nodata_to_value=255)[:, :ref.height, :ref.width]
        lc, lv, lw = (flags[i][m] for i in (2, 3, 4))
        # Categories describe center flags only, not fractional water area.
        c = np.full(int(m.sum()), 3, dtype=np.uint8)
        known = (lv == 1) & np.isin(lc, np.arange(1, 18)) & np.isin(lw, [1, 2])
        c[known] = 2
        c[known & (lc == 17) & (lw == 1)] = 0
        c[known & (lc != 17) & (lw == 2)] = 1
        categories.append(c)
        vals, nums = np.unique(lc, return_counts=True)
        details.append({'year': year, 'both_water': int((c == 0).sum()),
                        'both_land': int((c == 1).sum()), 'disagree': int((c == 2).sum()),
                        'unknown': int((c == 3).sum()),
                        'LC_Type1_codes': {str(int(v)): int(n) for v, n in zip(vals, nums)},
                        'annual_usable_coverage_zero': int((data[4][m] == 0).sum()),
                        'annual_source_coverage_zero': int((data[5][m] == 0).sum())})
        print(details[-1], flush=True)
    c = np.stack(categories)
    annual = np.stack(annuals)
    water = np.all(c == 0, axis=0)
    land = np.all(c == 1, axis=0)
    other = ~(water | land)
    totals = {'missing_common_mean_cells': int(missing.sum()),
              'both_flags_water_all_four_years': int(water.sum()),
              'both_flags_land_all_four_years': int(land.sum()),
              'mixed_disagreeing_or_unknown': int(other.sum()),
              'annual_usable_coverage_zero_all_years': int(np.all(annual == 0, axis=0).sum()),
              'annual_usable_coverage_positive_every_year_but_no_common_support': int(np.all(annual > 0, axis=0).sum())}
    assert totals['missing_common_mean_cells'] == 4866
    assert int(water.sum() + land.sum() + other.sum()) == 4866
    core = read_model(GDB / 'cheetah_core_primary_density051_min500_1km', ref)
    core_missing = core[missing]
    vals, nums = np.unique(core_missing[np.isfinite(core_missing) & (core_missing > 0)], return_counts=True)
    report = {'grid': grid(ref), 'totals': totals, 'annual': details,
              'missing_cells_in_cores': {str(int(v)): int(n) for v, n in zip(vals, nums)},
              'limits': ['Water/land labels are cell-center classification evidence, not full-cell water fractions or verified barriers.',
                         'No common usable vegetation support is not equivalent to no annual usable support.',
                         'Missing land requires explicit treatment; old-value fallback has not been adopted for production.',
                         'No raster, layer, project, path or priority was changed. No solver was run.']}
    stem = Path(r'C:\cheetah\reports') / ('vcf_missing_cell_context_' + task_datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    with stem.with_suffix('.json').open('x', encoding='utf-8') as f:
        json.dump(report, f, indent=2)
    with stem.with_suffix('.md').open('x', encoding='utf-8') as f:
        f.write('# Missing candidate VCF: context inspection\n\n')
        for key, value in totals.items():
            f.write(f'- {key}: {value:,}\n')
        f.write('\n## Limits\n\n' + '\n'.join('- ' + x for x in report['limits']) + '\n')
    print(json.dumps(totals, indent=2))
    print('Report:', stem.with_suffix('.json'))
    from plot_vcf_missing_context import export_spatial
    export_spatial(ref, support, missing, water, land, other, stem)

if __name__ == '__main__':
    main()
