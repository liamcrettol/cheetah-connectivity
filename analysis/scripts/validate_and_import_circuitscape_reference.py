"""Validate completed current outputs; import explicitly labelled reference copies.

--audit-only performs read-only GIS checks and writes a JSON report.
Default mode also creates normalized rasters and adds them to CURRENT.
This run contains pressure + terrain, NOT VCF vegetation or fence penalties.
Raw solver files and existing analysis datasets are never overwritten.
"""
import datetime as task_datetime
from itertools import combinations
from pathlib import Path
import configparser
import json
import os
import sys

import arcpy
import numpy as np

ROOT = Path(r'C:\cheetah\circuitscape')
YEARS = (2012, 2016, 2020, 2024)
REPORT = ROOT / 'reference_output_qc.json'
GROUP = '17 Current flow - pressure + terrain reference'
SCOPE = ('Reference scenario: 80% anthropogenic pressure and 20% terrain; '
         'no VCF vegetation component and no fence penalties. Not the final '
         'vegetation-balanced model or a validated conservation-priority map.')


def ascii_grid(path):
    header = {}
    with Path(path).open() as handle:
        for _ in range(6):
            key, value = handle.readline().split()
            header[key.lower()] = float(value)
        data = np.loadtxt(handle, dtype=np.float64)
    if data.shape != (int(header['nrows']), int(header['ncols'])):
        raise RuntimeError(f'ASCII shape mismatch: {path}')
    return header, data


def check_header(header, grid):
    expected = [grid[k] for k in ('xmin', 'ymin', 'cell_width', 'cell_height')]
    actual = [header['xllcorner'], header['yllcorner'], header['cellsize'], header['cellsize']]
    if not np.allclose(actual, expected, atol=.001, rtol=0):
        raise RuntimeError(f'ASCII grid mismatch: {actual} versus {expected}')
    if (header['ncols'], header['nrows']) != (grid['columns'], grid['rows']):
        raise RuntimeError('ASCII dimensions differ from manifest.')


def current_array(path, grid):
    raster = arcpy.Raster(str(path))
    expected = [grid[k] for k in ('xmin', 'ymin', 'xmax', 'ymax', 'cell_width', 'cell_height')]
    actual = [raster.extent.XMin, raster.extent.YMin, raster.extent.XMax,
              raster.extent.YMax, raster.meanCellWidth, raster.meanCellHeight]
    if (raster.width, raster.height) != (grid['columns'], grid['rows']) or not np.allclose(actual, expected, atol=.001, rtol=0):
        raise RuntimeError(f'Output raster grid mismatch: {path}')
    data = arcpy.RasterToNumPyArray(raster)
    nodata = raster.noDataValue
    valid = np.ones(data.shape, dtype=bool)
    if nodata is not None:
        valid &= ~np.isnan(data) if np.isnan(nodata) else data != nodata
    if np.any(valid & (~np.isfinite(data) | (data < 0))):
        raise RuntimeError(f'Invalid current values: {path}')
    return raster, data, valid


def audit():
    if not (ROOT / 'outputs' / 'PAIRWISE_CURRENT_FLOW_COMPLETE.txt').exists():
        raise RuntimeError('Solver completion marker is missing; do not import incomplete results.')
    manifest = json.loads((ROOT / 'inputs' / 'circuitscape_input_manifest.json').read_text())
    grid = manifest['grid']
    ids = sorted(manifest['core_ids'])
    expected_pairs = set(combinations(ids, 2))
    if len(ids) != 23 or len(expected_pairs) != 253:
        raise RuntimeError('Unexpected focal core inventory.')
    core_header, cores = ascii_grid(manifest['core_ascii'])
    check_header(core_header, grid)
    if sorted(np.unique(cores[cores > 0]).tolist()) != ids:
        raise RuntimeError('Exported focal IDs differ from manifest.')
    core_mask = cores > 0
    results, first_support = [], None
    for year in YEARS:
        base = ROOT / 'outputs' / f'current_primary_unfenced_{year}'
        triples = np.loadtxt(str(base) + '_resistances_3columns.out', ndmin=2)
        if triples.shape != (253, 3) or not np.all(np.isfinite(triples)):
            raise RuntimeError(f'{year}: invalid pair table.')
        pairs = [tuple(sorted((int(a), int(b)))) for a, b, value in triples]
        if not np.all(triples[:, :2] == triples[:, :2].astype(int)) or set(pairs) != expected_pairs or len(set(pairs)) != 253:
            raise RuntimeError(f'{year}: missing, duplicate or unexpected pairs.')
        if np.any(triples[:, 2] <= 0):
            raise RuntimeError(f'{year}: disconnected or invalid resistance result.')
        matrix = np.loadtxt(str(base) + '_resistances.out')
        if matrix.shape != (24, 24) or not np.array_equal(matrix[0, 1:], ids) or not np.array_equal(matrix[1:, 0], ids):
            raise RuntimeError(f'{year}: unexpected resistance matrix labels.')
        if not np.allclose(matrix[1:, 1:], matrix[1:, 1:].T) or not np.allclose(np.diag(matrix[1:, 1:]), 0):
            raise RuntimeError(f'{year}: resistance matrix is not symmetric with zero diagonal.')
        lookup = {node: index+1 for index, node in enumerate(ids)}
        for a, b, value in triples:
            if not np.isclose(matrix[lookup[int(a)], lookup[int(b)]], value):
                raise RuntimeError(f'{year}: resistance matrix and pair table disagree.')
        config = configparser.ConfigParser(interpolation=None)
        config.read(base)
        options = {key: value for section in config.sections() for key, value in config[section].items()}
        if options.get('set_null_currents_to_nodata', '').lower() != 'true':
            raise RuntimeError('Unexpected zero-current encoding; review before import.')
        expected_input = ROOT / 'inputs' / f'resistance_primary_unfenced_{year}.asc'
        if os.path.normcase(options['habitat_file']) != os.path.normcase(str(expected_input)):
            raise RuntimeError('Solver habitat file differs from expected export.')
        header, resistance = ascii_grid(expected_input)
        check_header(header, grid)
        support = resistance != header['nodata_value']
        if np.any(support & (~np.isfinite(resistance) | (resistance <= 0))):
            raise RuntimeError(f'{year}: invalid input resistance.')
        core_coverage = []
        for core_id in ids:
            cells = cores == core_id
            retained = int((cells & support).sum())
            total = int(cells.sum())
            if retained == 0:
                raise RuntimeError(f'{year}: core {core_id} has no cells in valid habitat.')
            core_coverage.append({'core_id': core_id, 'exported_cells': total,
                                  'retained_cells': retained, 'excluded_cells': total-retained})
        if first_support is None:
            first_support = support.copy()
        elif not np.array_equal(support, first_support):
            raise RuntimeError(f'{year}: resistance support changed across years.')
        path = Path(str(base) + '_cum_curmap.tif')
        raster, current, valid = current_array(path, grid)
        if np.any(valid & ~support):
            raise RuntimeError(f'{year}: current outside valid resistance support.')
        if not np.any(valid & (current > 0)):
            raise RuntimeError(f'{year}: empty current map.')
        results.append({
            'year': year, 'pairs_verified': 253, 'disconnected_pairs': 0,
            'matrix_matches_pair_table': True, 'grid_matches': True,
            'valid_habitat_cells': int(support.sum()),
            'core_cells_excluded_by_resistance_mask': int((core_mask & ~support).sum()),
            'core_coverage': core_coverage,
            'mapped_current_cells': int(valid.sum()),
            'zero_current_encoded_as_nodata_inside_habitat': int((support & ~valid).sum()),
            'raw_maximum_current': float(current[valid].max()),
            'output_crs_name': raster.spatialReference.name,
            'current_raster': str(path), 'exported_resistance': str(expected_input),
        })
        print(f'{year}: 253/253 connected pairs; matrix and raster grid verified', flush=True)
        del raster, current, valid, resistance
    report = {'checked_at': task_datetime.datetime.now().isoformat(),
              'assessment': 'Numerical checks passed; reference-scenario caveats required',
              'scope': SCOPE, 'grid': grid, 'core_count': 23,
              'normalization_divisor': 253, 'years': results,
              'caveats': [
                  'Current concentration is not cheetah occurrence probability.',
                  'Temporal current change represents redistribution; use effective resistance to assess modeled isolation.',
                  'Core interiors retain source/ground effects; do not label them as bottlenecks.',
                  'This run does not test vegetation or fence sensitivity.',
                  'Focal raster cells outside the habitat mask are excluded by the solver; per-core coverage is recorded.',
                  'GeoTIFF CRS may be unnamed; assign verified source CRS on derived copies only.',
              ]}
    REPORT.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f'QC report: {REPORT}')
    return report, manifest


def main():
    report, manifest = audit()
    if '--audit-only' in sys.argv:
        print(SCOPE)
        return
    aprx = arcpy.mp.ArcGISProject('CURRENT')
    maps = aprx.listMaps('Map')
    m = maps[0] if maps else aprx.activeMap
    if m is None:
        raise RuntimeError('No map found.')
    source_sr = arcpy.Describe(manifest['resistance_surfaces'][0]['source']).spatialReference
    if source_sr.factoryCode != manifest['grid']['wkid']:
        raise RuntimeError('Source coordinate system differs from export manifest.')
    stamp = task_datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    backup = Path(r'C:\cheetah\backups') / f'{Path(aprx.filePath).stem}_before_current_reference_import_{stamp}.aprx'
    backup.parent.mkdir(parents=True, exist_ok=True)
    aprx.saveACopy(str(backup))
    print(f'backup: {backup}')
    folder = ROOT / 'derived'
    folder.mkdir(exist_ok=True)
    gdb = folder / 'current_reference.gdb'
    if not arcpy.Exists(str(gdb)):
        arcpy.management.CreateFileGDB(str(folder), gdb.name)
    parents = [layer for layer in m.listLayers() if layer.isGroupLayer and layer.longName == 'Cheetah project']
    parent = parents[0] if len(parents) == 1 else None
    group_path = 'Cheetah project\\' + GROUP if parent else GROUP
    groups = [layer for layer in m.listLayers() if layer.isGroupLayer and layer.longName == group_path]
    group = groups[0] if groups else m.createGroupLayer(GROUP, parent)
    grid = report['grid']
    for entry in report['years']:
        year = entry['year']
        raster, data, valid = current_array(entry['current_raster'], grid)
        header, resistance = ascii_grid(entry['exported_resistance'])
        support = resistance != header['nodata_value']
        # Restore zero ONLY where the exported habitat is valid, because the
        # verified solver option intentionally encoded zero current as NoData.
        normalized = np.full(data.shape, -9999.0, dtype=np.float64)
        normalized[support] = 0.0
        normalized[valid] = data[valid] / 253.0
        out = str(gdb / f'current_pressure_terrain_ref_{year}_mean')
        if arcpy.Exists(out):
            existing, values, existing_valid = current_array(out, grid)
            if not np.allclose(values, normalized, rtol=1e-6, atol=1e-10) or existing.spatialReference.factoryCode != grid['wkid']:
                raise RuntimeError(f'Existing derived output differs; not overwriting: {out}')
            del existing, values, existing_valid
        else:
            with arcpy.EnvManager(outputCoordinateSystem=source_sr, overwriteOutput=False,
                                  extent=None, mask=None, snapRaster=None):
                new = arcpy.NumPyArrayToRaster(normalized,
                    arcpy.Point(grid['xmin'], grid['ymin']), grid['cell_width'],
                    grid['cell_height'], -9999.0)
                new.save(out)
                del new
                arcpy.management.DefineProjection(out, source_sr)
                arcpy.management.CalculateStatistics(out, 1, 1)
        target = os.path.normcase(out)
        matches = [layer for layer in m.listLayers() if not layer.isGroupLayer
                   and layer.supports('DATASOURCE') and os.path.normcase(layer.dataSource) == target
                   and layer.longName.startswith(group_path + '\\')]
        if not matches:
            loose = m.addDataFromPath(out)
            m.addLayerToGroup(group, loose, 'BOTTOM')
            matches = [layer for layer in m.listLayers() if not layer.isGroupLayer
                       and layer.supports('DATASOURCE') and os.path.normcase(layer.dataSource) == target
                       and layer.longName.startswith(group_path + '\\')]
            if matches:
                m.removeLayer(loose)
        if not matches:
            raise RuntimeError(f'Could not add {out} to group.')
        matches[0].name = f'{year} | mean current | pressure + terrain reference'
        matches[0].visible = year == 2024
        print(f'available in map: {year} reference mean current')
        del raster, data, valid, normalized, resistance
    group.visible = True
    aprx.save()
    print('Complete. Four reference copies imported; raw outputs and model inputs unchanged.')
    print('Zero-current cells restored only inside verified valid habitat; CRS assigned from verified source.')
    print(SCOPE)


if __name__ == '__main__':
    main()
