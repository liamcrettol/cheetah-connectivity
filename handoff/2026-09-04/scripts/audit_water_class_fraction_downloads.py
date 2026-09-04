"""Verify the four water-class exports; write reports only, never GIS data.

ArcGIS Pro Python required. Fractions describe native classified area, not
observed inundation or fence/water permeability. No missing-data policy applied.
"""
import csv
import datetime
import hashlib
import json
from pathlib import Path
import arcpy
import numpy as np
from audit_downloaded_gee_validity import read_model, check_lattice, grid

ROOT = Path(r'C:\cheetah\raw\source_qa')
SOURCE = ROOT / 'water_class_fractions_v1_20260904'
GDB = Path(r'C:\cheetah\gdb\cheetah_working.gdb')
NAMES = ['lw_water_fraction', 'lw_land_fraction', 'lw_valid_fraction',
         'lc_water_fraction', 'lc_wetland_fraction', 'lc_barren_fraction',
         'lc_valid_fraction', 'both_water_fraction', 'both_land_fraction',
         'disagreement_fraction', 'both_valid_fraction']

def main():
    arcpy.CheckOutExtension('Spatial')
    ref = arcpy.Raster(str(GDB / 'resistance_temporal_veg_balanced_2012'))
    support = np.isfinite(read_model(GDB / 'resistance_temporal_veg_balanced_2012', ref))
    records, missing, fractions = [], None, []
    for year in (2012, 2016, 2020, 2024):
        p = SOURCE / f'water_class_fractions_v1_{year}.tif'
        r = arcpy.Raster(str(p))
        check_lattice(r, ref)
        if (r.width, r.height, list(r.bandNames)) != (ref.width, ref.height, NAMES):
            raise ValueError(f'Unexpected dimensions/bands: {p}: {r.bandNames}')
        a = arcpy.RasterToNumPyArray(r, nodata_to_value=-9999).astype('float64')
        if not np.isfinite(a).all() or np.any(a < -1e-6) or np.any(a > 1+1e-6):
            raise ValueError(f'Invalid fractions or missing exported pixels: {p}')
        errors = {'lw_sum': float(np.max(np.abs(a[0]+a[1]-a[2]))),
                  'both_sum': float(np.max(np.abs(a[7]+a[8]+a[9]-a[10]))),
                  'joint_exceeds_lw': float(np.max(a[10]-a[2])),
                  'joint_exceeds_lc': float(np.max(a[10]-a[6])),
                  'lc_classes_exceed_valid': float(np.max(a[3]+a[4]+a[5]-a[6]))}
        if any(v > 1e-6 for v in errors.values()):
            raise ValueError(f'Accounting check failed: {errors}')
        v = arcpy.Raster(str(ROOT / 'vcf_maskpreserved_v2_20260903' /
                             f'vcf_maskpreserved_common_v2_{year}.tif'))
        check_lattice(v, ref)
        if (v.width, v.height, v.bandCount) != (ref.width, ref.height, 8):
            raise ValueError('Unexpected VCF dimensions')
        va = arcpy.RasterToNumPyArray(v, nodata_to_value=-9999)
        m = support & (va[3] == 0)
        if missing is None:
            missing = m.copy()
        if not np.array_equal(missing, m) or int(m.sum()) != 4866:
            raise ValueError('Common missing-cell mask changed')
        f = a[:, m].copy()
        fractions.append(f)
        item = {'year': year, 'filename': p.name,
                'sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
                'grid': grid(r), 'band_names': list(r.bandNames), 'checks': errors,
                'missing_vcf_cells': int(m.sum()),
                'missing_vcf_cells_joint_valid_below_0999999': int((f[10] < .999999).sum()),
                'both_water_ge_095': int((f[7] >= .95).sum()),
                'both_land_ge_095': int((f[8] >= .95).sum()),
                'any_disagreement_gt_000001': int((f[9] > .000001).sum()),
                'mean_fractions_in_missing_cells': dict(zip(NAMES, map(float, f.mean(axis=1))))}
        records.append(item)
        print(f'{year}: grid, 11 bands, bounds and accounting PASSED; 4866 missing VCF cells cross-tabulated', flush=True)
    allf = np.stack(fractions)
    stable_water = np.all(allf[:, 7, :] >= .95, axis=0)
    stable_land = np.all(allf[:, 8, :] >= .95, axis=0)
    totals = {'missing_cells': int(missing.sum()),
              'both_water_ge_095_all_years': int(stable_water.sum()),
              'both_land_ge_095_all_years': int(stable_land.sum()),
              'other_cells': int((~(stable_water | stable_land)).sum())}
    report = {'assessment': 'Share with caveats: file QA passed, ecological policy unresolved',
              'annual': records, 'cross_year': totals,
              'limits': ['0.95 is a descriptive bin, not an adopted exclusion threshold.',
                         'Fractions are native classified-area fractions, not direct inundation measurements.',
                         'LW and LC_Type1 are from the same product, not independent validation.',
                         'No imputation, production edit, resistance transformation or solver was run.']}
    stem = Path(r'C:\cheetah\reports') / ('water_fraction_download_qa_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    with stem.with_suffix('.json').open('x', encoding='utf-8') as out:
        json.dump(report, out, indent=2)
    rows, cols = np.where(missing)
    with stem.with_suffix('.csv').open('x', newline='', encoding='utf-8') as out:
        writer = csv.writer(out)
        writer.writerow(['year', 'row', 'column', 'x', 'y'] + NAMES)
        for i, year in enumerate((2012, 2016, 2020, 2024)):
            for j, (row, col) in enumerate(zip(rows, cols)):
                writer.writerow([year, int(row), int(col), ref.extent.XMin+(col+.5)*1000,
                                 ref.extent.YMax-(row+.5)*1000] + allf[i, :, j].tolist())
    with stem.with_suffix('.md').open('x', encoding='utf-8') as out:
        out.write('# Water-class export QA\n\nAll four exports passed exact grid, band-order, fraction-bound and accounting checks.\n\n')
        out.write('The 4,866 common missing-VCF cells were cross-tabulated in every year.\n\n')
        for k, v in totals.items():
            out.write(f'- {k}: {v:,}\n')
        out.write('\n## Required caveats\n\n' + '\n'.join('- '+x for x in report['limits']) + '\n')
    print(json.dumps(totals))
    print('Report:', stem.with_suffix('.json'))

if __name__ == '__main__':
    main()
