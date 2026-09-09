"""Read-only companion: locate VCF zero triplets inside the actual model support.

Raw land-cover codes are reported without assuming their legend. Nearest-cell
lookup is used for diagnostic counts only; no rasters are resampled or written.
"""
import datetime as task_datetime
import json
from pathlib import Path
import arcpy
import numpy as np

GDB = Path(r'C:\cheetah\gdb\cheetah_working.gdb')
GEE = Path(r'C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah\rasters\gee_exports')


def main():
    arcpy.CheckOutExtension('Spatial')
    reference = arcpy.Raster(str(GDB / 'resistance_temporal_veg_balanced_2012'))

    def array(path, nearest=False):
        r = arcpy.Raster(str(path))
        if r.spatialReference.factoryCode != reference.spatialReference.factoryCode:
            raise ValueError(f'CRS mismatch: {path}')
        a = arcpy.RasterToNumPyArray(r).astype(float)
        with arcpy.EnvManager(extent=r.extent, mask=None, snapRaster=str(path),
                              cellSize=str(path), outputCoordinateSystem=r.spatialReference):
            nulls = arcpy.RasterToNumPyArray(arcpy.sa.IsNull(r)).astype(bool)
        a[nulls] = np.nan
        if nearest:
            xs = reference.extent.XMin + (np.arange(reference.width) + .5) * reference.meanCellWidth
            ys = reference.extent.YMax - (np.arange(reference.height) + .5) * reference.meanCellHeight
            cols = np.floor((xs - r.extent.XMin) / r.meanCellWidth).astype(int)
            rows = np.floor((r.extent.YMax - ys) / r.meanCellHeight).astype(int)
            if cols.min() < 0 or cols.max() >= r.width or rows.min() < 0 or rows.max() >= r.height:
                raise ValueError('Reference centers extend outside categorical source')
            a = a[np.ix_(rows, cols)]
        else:
            if a.shape != (reference.height, reference.width) or not np.allclose(
                [r.extent.XMin, r.extent.YMin, r.meanCellWidth, r.meanCellHeight],
                [reference.extent.XMin, reference.extent.YMin, reference.meanCellWidth, reference.meanCellHeight],
                rtol=0, atol=.001):
                raise ValueError(f'Grid mismatch: {path}')
        return a

    support = np.isfinite(array(GDB / 'resistance_temporal_veg_balanced_2012'))
    persistent_code17 = support.copy()
    rows = []
    for year in (2012, 2016, 2020, 2024):
        bands = [array(GDB / f'vcf_{v}_{year}_aligned_1km') for v in ('tree', 'nontree', 'bare')]
        zeros = support & (bands[0] == 0) & (bands[1] == 0) & (bands[2] == 0)
        lc = array(GEE / f'lc_{year}_1km.tif', nearest=True)
        persistent_code17 &= lc == 17
        codes, counts = np.unique(lc[zeros & np.isfinite(lc)], return_counts=True)
        rows.append({'year': year, 'model_cells': int(support.sum()),
                     'all_zero_vcf_inside_model': int(zeros.sum()),
                     'raw_landcover_codes_at_zero_triplets': {str(int(c)): int(n) for c, n in zip(codes, counts)},
                     'missing_landcover_at_zero_triplets': int(np.count_nonzero(zeros & ~np.isfinite(lc))),
                     'class_17_cells_inside_model': int(np.count_nonzero(support & (lc == 17))),
                     'class_0_cells_inside_model': int(np.count_nonzero(support & (lc == 0))),
                     'class_11_cells_inside_model': int(np.count_nonzero(support & (lc == 11)))})
    stamp = task_datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    out = Path(r'C:\cheetah\reports') / f'circuitscape_model_mask_context_{stamp}.json'
    report = {'notes': ['Diagnostic raw codes, not a validated permanent-water classification.',
                        'No inference that all-zero triplets are missing without source QA.',
                        'Category lookup uses nearest source pixel at model cell center; no data edits.'],
              'class_17_in_all_four_years_inside_model': int(persistent_code17.sum()),
              'results': rows}
    out.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2), flush=True)
    print(f'report: {out}')


if __name__ == '__main__':
    main()
