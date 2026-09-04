"""Read-only comparison of downloaded source flags and saved model rasters.

Creates a versioned JSON report only. No raster edits, project saves or solver.
Allows extra border rows only on the same lattice and reports their contents;
reads the exact model window without resampling. Flags sample cell centers,
not fractional native coverage of the 1 km model cells.
"""
import csv
import hashlib
import json
import datetime as task_datetime
from pathlib import Path
import arcpy
import numpy as np

GDB = Path(r'C:\cheetah\gdb\cheetah_working.gdb')
QA = Path(r'C:\cheetah\raw\source_qa\gee_validity_20260903')
POINTS = Path(r'C:\Users\lcrettol\Downloads\cheetah_input_source_qa_20260903.csv')
YEARS = (2012, 2016, 2020, 2024)
BANDS = ['vcf_triplet_valid', 'vcf_allzero_when_valid', 'lc_type1',
         'lc_type1_valid', 'land_water']


def grid(r):
    return {'columns': r.width, 'rows': r.height, 'crs_code': r.spatialReference.factoryCode,
            'xmin': r.extent.XMin, 'ymax': r.extent.YMax,
            'cell_width': r.meanCellWidth, 'cell_height': r.meanCellHeight}


def check_lattice(r, ref):
    if r.spatialReference.factoryCode != ref.spatialReference.factoryCode:
        raise ValueError('CRS mismatch')
    for x, y in zip((r.meanCellWidth, r.meanCellHeight, r.extent.XMin, r.extent.YMax),
                    (ref.meanCellWidth, ref.meanCellHeight, ref.extent.XMin, ref.extent.YMax)):
        if abs(x - y) > .001:
            raise ValueError(f'Grid origin/cell-size mismatch: {grid(r)}')
    if r.width < ref.width or r.height < ref.height:
        raise ValueError('QA raster does not cover the complete model grid')


def read_model(path, ref):
    r = arcpy.Raster(str(path))
    check_lattice(r, ref)
    if r.width != ref.width or r.height != ref.height or r.bandCount != 1:
        raise ValueError(f'Model raster shape mismatch: {path}')
    a = arcpy.RasterToNumPyArray(r).astype('float64')
    with arcpy.EnvManager(extent=r.extent, snapRaster=str(path), cellSize=str(path),
                          outputCoordinateSystem=r.spatialReference, mask=None):
        missing = arcpy.RasterToNumPyArray(arcpy.sa.IsNull(r)).astype(bool)
    if missing.shape != a.shape:
        raise ValueError('IsNull shape mismatch')
    a[missing] = np.nan
    return a


def counts(a, selection):
    values, number = np.unique(a[selection], return_counts=True)
    return {str(int(v)): int(n) for v, n in zip(values, number)}


def main():
    arcpy.CheckOutExtension('Spatial')
    ref = arcpy.Raster(str(GDB / 'resistance_temporal_veg_balanced_2012'))
    support = np.isfinite(read_model(GDB / 'resistance_temporal_veg_balanced_2012', ref))
    core = read_model(GDB / 'cheetah_core_primary_density051_min500_1km', ref)
    valid_all = support.copy()
    missing_any = np.zeros(support.shape, bool)
    lcwater_all = support.copy()
    lwwater_all = support.copy()
    samples = list(csv.DictReader(POINTS.open(newline='', encoding='utf-8-sig')))
    results = []
    discrepancies = []
    for year in YEARS:
        path = QA / f'cheetah_source_validity_audit_v1_{year}.tif'
        r = arcpy.Raster(str(path))
        check_lattice(r, ref)
        if r.bandCount != 5 or list(r.bandNames) != BANDS:
            raise ValueError(f'Unexpected band order: {r.bandNames}')
        data = arcpy.RasterToNumPyArray(r, nodata_to_value=255)
        outside = np.ones(data.shape[1:], bool)
        outside[:ref.height, :ref.width] = False
        edge = {'extra_pixels': int(outside.sum()),
                'extra_pixels_with_any_non_nodata_band': int(np.any(data[:, outside] != 255, axis=0).sum())}
        data = data[:, :ref.height, :ref.width]
        vf, vz, lc, lv, lw = data
        for a, allowed in [(vf, [0, 1, 255]), (vz, [0, 1, 255]),
                           (lv, [0, 1, 255]), (lw, [1, 2, 255])]:
            if not np.isin(a, allowed).all():
                raise ValueError('Unexpected flag code')
        if not np.isin(lc, list(range(1, 18)) + [255]).all():
            raise ValueError('Unexpected LC_Type1 code')
        if np.any((vf == 0) & (vz != 255)) or np.any((vf == 1) & (vz == 255)):
            raise ValueError('VCF validity/allzero mask inconsistency')
        current_support = np.isfinite(read_model(GDB / f'resistance_temporal_veg_balanced_{year}', ref))
        if not np.array_equal(support, current_support):
            raise ValueError('Model support differs between years')
        local_valid = support.copy()
        local_zero = support.copy()
        for var in ('tree', 'nontree', 'bare'):
            a = read_model(GDB / f'vcf_{var}_{year}_aligned_1km', ref)
            local_valid &= np.isfinite(a)
            local_zero &= a == 0
        missing = support & (vf == 0)
        native_valid = support & (vf == 1)
        valid_all &= native_valid
        missing_any |= missing
        lcwater_all &= (lc == 17) & (lv == 1)
        lwwater_all &= lw == 1
        native_missing_nonzero = missing & local_valid & ~local_zero
        item = {'year': year, 'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'download_grid': grid(r), 'model_window_border_check': edge,
                'model_cells': int(support.sum()), 'native_missing_inside_model': int(missing.sum()),
                'native_valid_inside_model': int(native_valid.sum()),
                'unknown_validity_inside_model': int(np.count_nonzero(support & (vf == 255))),
                'local_allzero_inside_model': int(local_zero.sum()),
                'local_allzero_native_missing': int(np.count_nonzero(local_zero & missing)),
                'local_allzero_native_valid': int(np.count_nonzero(local_zero & native_valid)),
                'local_nonzero_native_missing': int(native_missing_nonzero.sum()),
                'native_valid_allzero_inside_model': int(np.count_nonzero(native_valid & (vz == 1))),
                'local_missing_inside_model': int(np.count_nonzero(support & ~local_valid)),
                'native_missing_by_LW': counts(lw, missing),
                'native_missing_by_LC_Type1': counts(lc, missing),
                'native_missing_nonzero_local_by_LW': counts(lw, native_missing_nonzero),
                'lc17_inside_model': int(np.count_nonzero(support & (lc == 17))),
                'lw_water_inside_model': int(np.count_nonzero(support & (lw == 1))),
                'missing_at_core_pixels_by_core': counts(core, missing & np.isfinite(core) & (core > 0))}
        for s in [s for s in samples if int(s['year']) == year]:
            row, col = int(s['row']), int(s['col'])
            expected = int(all(float(s[f'gee_{v}_valid']) == 1 for v in ('tree', 'nontree', 'bare')))
            if int(vf[row, col]) != expected:
                discrepancies.append({'sample_id': s['sample_id'], 'point_vcf_valid': expected,
                                      'raster_vcf_valid': int(vf[row, col])})
        results.append(item)
        print(f'{year}: native missing {item["native_missing_inside_model"]:,}; '
              f'local zero/native valid {item["local_allzero_native_valid"]:,}; '
              f'local nonzero/native missing {item["local_nonzero_native_missing"]:,}', flush=True)
    core_keep = {}
    for c in np.unique(core[np.isfinite(core) & (core > 0)]):
        in_core = (core == c) & support
        core_keep[str(int(c))] = {'original_model_pixels': int(in_core.sum()),
                                  'native_valid_all_years_pixels': int((in_core & valid_all).sum())}
    report = {'model_grid': grid(ref), 'results': results,
              'point_vs_raster_VCF_validity_disagreements': discrepancies,
              'native_missing_any_year_inside_model': int(missing_any.sum()),
              'native_valid_all_years_inside_model': int(valid_all.sum()),
              'lc17_all_years_inside_model': int(lcwater_all.sum()),
              'lw_water_all_years_inside_model': int(lwwater_all.sum()),
              'hypothetical_core_retention_if_all_year_native_validity_required': core_keep,
              'caveats': ['Native center flags are not fractions of a 1 km cell.',
                          'Missing native center plus valid local export is not necessarily an export error: spatial support differs.',
                          'NoData is not an ecological barrier; no production mask was changed.',
                          'Core pixel counts are hypothetical screening, not a prescription to shrink cores.',
                          'LC boundary samples can differ from point CSV because LC uses its own native grid here.',
                          'No route connectivity, current changes or conservation rankings were computed.']}
    out = Path(r'C:\cheetah\reports') / ('gee_validity_grid_audit_' + task_datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.json')
    with out.open('x', encoding='utf-8') as f:
        json.dump(report, f, indent=2)
    print(f'Report: {out}', flush=True)
    print('Point flag disagreements:', len(discrepancies))
    print('Missing in any year:', int(missing_any.sum()))
    print('All-year-valid cells:', int(valid_all.sum()))
    print('Only the report was written. No model, project or raw raster was changed.')


if __name__ == '__main__':
    main()
