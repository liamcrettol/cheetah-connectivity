"""Select 32 diagnostic model-cell centers; read-only GIS, JSON report only."""
import json
from pathlib import Path
import arcpy
import numpy as np

GDB = Path(r'C:\cheetah\gdb\cheetah_working.gdb')
GEE = Path(r'C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah\rasters\gee_exports')


def main():
    arcpy.CheckOutExtension('Spatial')
    ref = arcpy.Raster(str(GDB / 'resistance_temporal_veg_balanced_2012'))
    shape = (ref.height, ref.width)
    xs = ref.extent.XMin + (np.arange(ref.width) + .5) * ref.meanCellWidth
    ys = ref.extent.YMax - (np.arange(ref.height) + .5) * ref.meanCellHeight

    def read(path, align=False):
        r = arcpy.Raster(str(path))
        if r.spatialReference.factoryCode != ref.spatialReference.factoryCode:
            raise ValueError(f'CRS mismatch: {path}')
        a = arcpy.RasterToNumPyArray(r).astype(float)
        with arcpy.EnvManager(extent=r.extent, mask=None, snapRaster=str(path), cellSize=str(path),
                              outputCoordinateSystem=r.spatialReference):
            nodata = arcpy.RasterToNumPyArray(arcpy.sa.IsNull(r)).astype(bool)
        a[nodata] = np.nan
        if align:
            cols = np.floor((xs - r.extent.XMin) / r.meanCellWidth).astype(int)
            rows = np.floor((r.extent.YMax - ys) / r.meanCellHeight).astype(int)
            if cols.min() < 0 or rows.min() < 0 or cols.max() >= r.width or rows.max() >= r.height:
                raise ValueError(f'Source does not cover model centers: {path}')
            a = a[np.ix_(rows, cols)]
        elif a.shape != shape or not np.allclose(
            [r.extent.XMin,r.extent.YMax,r.meanCellWidth,r.meanCellHeight],
            [ref.extent.XMin,ref.extent.YMax,ref.meanCellWidth,ref.meanCellHeight],rtol=0,atol=.001):
            raise ValueError(f'Grid mismatch: {path}')
        return a

    support = np.isfinite(read(GDB / 'resistance_temporal_veg_balanced_2012'))
    records = []
    for year in (2012, 2016, 2020, 2024):
        lc = read(GEE / f'lc_{year}_1km.tif', True)
        aligned = {v: read(GDB / f'vcf_{v}_{year}_aligned_1km') for v in ('tree','nontree','bare')}
        zero = (aligned['tree'] == 0) & (aligned['nontree'] == 0) & (aligned['bare'] == 0)
        groups = {'zero_water': support & zero & (lc == 17),
                  'zero_other': support & zero & np.isfinite(lc) & (lc != 17),
                  'nonzero_water': support & ~zero & (lc == 17),
                  'nonzero_other': support & ~zero & np.isfinite(lc) & (lc != 17)}
        current = []
        for group, condition in groups.items():
            eligible = np.flatnonzero(condition)
            if not len(eligible):
                continue
            # Spatially separated deterministic diagnostic examples, not random
            # statistical samples and not chosen to estimate prevalence.
            picks = eligible[np.unique(np.linspace(0, len(eligible)-1, min(2,len(eligible))).astype(int))]
            for index in picks:
                row, col = np.unravel_index(index, shape)
                point = arcpy.PointGeometry(arcpy.Point(float(xs[col]),float(ys[row])),ref.spatialReference)
                lonlat = point.projectAs(arcpy.SpatialReference(4326)).firstPoint
                item = {'sample_id': f'{year}_{group}_{len(current)+1}', 'year': year,
                        'group': group,'row': int(row),'col':int(col),
                        'longitude':lonlat.X,'latitude':lonlat.Y,'local_lc':int(lc[row,col])}
                for v,a in aligned.items():
                    item['aligned_'+v] = float(a[row,col])
                current.append(item)
        del aligned
        for v in ('tree','nontree','bare'):
            raw = read(GEE / f'vcf_{v}_{year}_1km.tif',True)
            for item in current:
                val = raw[item['row'], item['col']]
                item['raw_'+v] = float(val) if np.isfinite(val) else None
            del raw
        records.extend(current)
        print(f'{year}: {len(current)} provenance samples selected',flush=True)
    out = Path(r'C:\cheetah\reports\input_provenance_samples_20260903.json')
    if out.exists():
        raise FileExistsError(f'Preserving existing report: {out}')
    out.write_text(json.dumps(records,indent=2),encoding='utf-8')
    print(f'report: {out}',flush=True)
    print('Only a diagnostic JSON report was created; no GIS data or project changed.')


if __name__ == '__main__':
    main()
