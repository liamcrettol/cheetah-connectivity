"""Read-only fixed-route exposure screen. No least-cost or circuit solves.

Split saved polyline segments at raster grid boundaries and integrate the
piecewise-constant resistance over their planar lengths. This is a diagnostic
line integral, NOT a newly optimized path or replacement COST_RAW value.
"""
import csv
import datetime as task_datetime
import hashlib
import json
import math
from pathlib import Path
import arcpy
import numpy as np
from audit_downloaded_gee_validity import read_model, check_lattice
from compare_vcf_v2_candidate_inputs import vegetation, ROOT, GDB, YEARS, NAMES


def split_segment(x0, y0, x1, y1, xmin, ymax, cell):
    """Yield (row, column, length) without clipping; retain out-of-grid parts."""
    u0, v0 = (x0-xmin)/cell, (ymax-y0)/cell
    u1, v1 = (x1-xmin)/cell, (ymax-y1)/cell
    distance = math.hypot(x1-x0, y1-y0)
    if not distance:
        return
    cuts = [0., 1.]
    for a, b in ((u0, u1), (v0, v1)):
        if abs(b-a) < 1e-12:
            continue
        for edge in range(math.floor(min(a,b))+1, math.ceil(max(a,b))):
            t = (edge-a)/(b-a)
            if 1e-12 < t < 1-1e-12:
                cuts.append(t)
    cuts = sorted(set(cuts))
    for a,b in zip(cuts[:-1], cuts[1:]):
        if b-a < 1e-12:
            continue
        t = (a+b)/2
        yield math.floor(v0+t*(v1-v0)), math.floor(u0+t*(u1-u0)), distance*(b-a)


def self_test():
    for coords, expected in [((.5,1.5,2.5,1.5),2), ((2.5,1.5,.5,1.5),2),
                             ((.5,1.5,2.5,-.5),math.sqrt(8)), ((-.5,1.5,.5,1.5),1)]:
        parts = list(split_segment(*coords,0,2,1))
        if abs(sum(p[2] for p in parts)-expected)>1e-10:
            raise AssertionError('Segment lengths do not reconcile')
    assert list(split_segment(.5,1.5,2.5,1.5,0,2,1)) == [(0,0,.5),(0,1,1.),(0,2,.5)]
    assert list(split_segment(1,1,1,1,0,2,1)) == []


def screen(geom, old, new, coverage, ref):
    totals = dict(total_m=0., outside_m=0., old_missing_m=0., new_missing_m=0.,
                  partial_below95_m=0., comparable_m=0., above5pct_m=0.,
                  old_integral_comparable=0., new_integral_comparable=0., abs_delta_integral=0.)
    max_change = 0.
    for part in geom:
        prev = None
        for point in part:
            if point is None:
                prev = None
                continue
            if prev is not None:
                for row,col,length in split_segment(prev.X,prev.Y,point.X,point.Y,
                                                    ref.extent.XMin,ref.extent.YMax,ref.meanCellWidth):
                    totals['total_m'] += length
                    if not (0<=row<ref.height and 0<=col<ref.width):
                        totals['outside_m'] += length
                        continue
                    a,b = old[row,col],new[row,col]
                    if not np.isfinite(a):
                        totals['old_missing_m'] += length
                        continue
                    if not np.isfinite(b):
                        totals['new_missing_m'] += length
                        continue
                    totals['comparable_m'] += length
                    if coverage[row,col] < .95:
                        totals['partial_below95_m'] += length
                    pct = abs(b-a)/a*100
                    max_change = max(max_change,pct)
                    if pct > 5:
                        totals['above5pct_m'] += length
                    totals['old_integral_comparable'] += a*length
                    totals['new_integral_comparable'] += b*length
                    totals['abs_delta_integral'] += abs(b-a)*length
            prev = point
    if abs(totals['total_m']-geom.length)>max(.001,geom.length*1e-8):
        raise ValueError('Line integration length differs from saved geometry')
    denominator = totals['old_integral_comparable']
    totals['signed_integral_change_percent_comparable'] = ((totals['new_integral_comparable']/denominator-1)*100 if denominator else None)
    totals['absolute_integral_change_percent_comparable'] = (totals['abs_delta_integral']/denominator*100 if denominator else None)
    totals['max_cell_change_percent_on_line'] = float(max_change)
    totals['complete_candidate_coverage'] = (totals['outside_m']+totals['old_missing_m']+totals['new_missing_m'] < .001)
    totals['pct_line_above5pct_change'] = 100*totals['above5pct_m']/totals['total_m']
    return {k: (float(v) if isinstance(v,np.floating) else v) for k,v in totals.items()}


def main():
    self_test()
    arcpy.CheckOutExtension('Spatial')
    ref = arcpy.Raster(str(GDB / 'resistance_temporal_veg_balanced_2012'))
    with Path(r'C:\cheetah\reports\conservation_priority_links_temporal.csv').open(newline='',encoding='utf-8-sig') as f:
        eligible = {tuple(sorted((int(r['from_core']),int(r['to_core'])))): r for r in csv.DictReader(f)}
    with Path(r'C:\cheetah\reports\least_cost_paths_temporal_veg_balanced_2012.csv').open(newline='',encoding='utf-8-sig') as f:
        expected_pairs = {tuple(sorted((int(r['from_core']),int(r['to_core'])))) for r in csv.DictReader(f)}
    if len(expected_pairs) != 45:
        raise ValueError('Expected 45 pairs in stored balanced 2012 path report')
    rows, manifest = [], []
    for year in YEARS:
        source = ROOT / f'vcf_maskpreserved_common_v2_{year}.tif'
        r = arcpy.Raster(str(source))
        check_lattice(r,ref)
        if r.width!=ref.width or r.height!=ref.height or list(r.bandNames)!=NAMES:
            raise ValueError('Candidate grid or bands changed')
        a = arcpy.RasterToNumPyArray(r,nodata_to_value=-9999).astype(float)
        a[a==-9999] = np.nan
        new_v, coverage = vegetation(*a[:3]),a[3]
        old_v = read_model(GDB / f'vegetation_resistance_{year}_1_10',ref)
        for label,weight in [('low',.1),('balanced',.2),('high',.4)]:
            old = read_model(GDB / f'resistance_temporal_veg_{label}_{year}',ref)
            new = old + weight*(new_v-old_v)
            fc = GDB / f'least_cost_paths_temporal_veg_{label}_{year}'
            if arcpy.Describe(str(fc)).spatialReference.factoryCode != ref.spatialReference.factoryCode:
                raise ValueError('Route CRS mismatch')
            found = set()
            digest = hashlib.sha256()
            with arcpy.da.SearchCursor(str(fc),['FROM_ID','TO_ID','STATUS','SHAPE@','PATH_KM','COST_RAW']) as cursor:
                for from_id,to_id,status,geom,path_km,cost_raw in cursor:
                    pair = tuple(sorted((int(from_id),int(to_id))))
                    if pair in found or status!='OK' or geom is None or geom.length<=0:
                        raise ValueError('Duplicate, empty or unsuccessful stored path')
                    found.add(pair)
                    if abs(geom.length/1000-path_km)>1e-5:
                        raise ValueError('PATH_KM does not match geometry')
                    digest.update(bytes(geom.WKB))
                    record = dict(year=year,scenario='veg_'+label,from_core=pair[0],to_core=pair[1],
                                  previously_primary_eligible=eligible.get(pair,{}).get('primary_priority_eligible_final','unknown'),
                                  stored_path_km=path_km,stored_cost_raw=cost_raw)
                    record.update(screen(geom,old,new,coverage,ref))
                    rows.append(record)
            if found != expected_pairs:
                raise ValueError(f'Pair set mismatch: {fc}')
            manifest.append(dict(feature_class=str(fc),paths=len(found),geometry_cursor_order_sha256=digest.hexdigest()))
            print(f'Screened saved {label} {year}: {len(found)} paths; no optimization',flush=True)
    pair_summary = []
    for pair in sorted(expected_pairs):
        subset = [r for r in rows if (r['from_core'],r['to_core'])==pair]
        balanced = [r for r in subset if r['scenario']=='veg_balanced']
        pair_summary.append(dict(from_core=pair[0],to_core=pair[1],
            previously_primary_eligible=eligible.get(pair,{}).get('primary_priority_eligible_final','not_in_priority_table'),
            paths_with_missing_candidate=sum(not r['complete_candidate_coverage'] for r in subset),
            balanced_paths_with_missing_candidate=sum(not r['complete_candidate_coverage'] for r in balanced),
            max_balanced_absolute_integral_change_percent_comparable=max(r['absolute_integral_change_percent_comparable'] or 0 for r in balanced),
            max_balanced_pct_line_above5pct_change=max(r['pct_line_above5pct_change'] for r in balanced),
            max_missing_length_m=max(r['new_missing_m'] for r in subset)))
    ranked = sorted(pair_summary,key=lambda r:(r['paths_with_missing_candidate']>0,r['max_balanced_absolute_integral_change_percent_comparable']),reverse=True)
    report = dict(paths_screened=len(rows),pairs_screened=len(expected_pairs),
        paths_without_complete_candidate_coverage=sum(not r['complete_candidate_coverage'] for r in rows),
        pairs_without_complete_candidate_coverage=sum(r['paths_with_missing_candidate']>0 for r in pair_summary),
        balanced_paths_without_complete_candidate_coverage=sum(r['scenario']=='veg_balanced' and not r['complete_candidate_coverage'] for r in rows),
        pair_review_order=ranked,manifest=manifest,
        limitations=['Fixed-line exposure, not route reoptimization or current-flow analysis.',
                    'Line integrals are diagnostic and must not replace stored CostDistance COST_RAW.',
                    'Comparable-only values omit missing sections, explicitly quantified in meters.',
                    '95% coverage and 5% cell-change markers are descriptive review flags, not biological cutoffs.',
                    'Off-route alternatives may change even if a saved route has little change.',
                    'Review order does not authorize a solver run or establish a conservation-priority ranking.',
                    'Original rasters, model support, routes, priority decisions and project remain unchanged.'])
    stem = Path(r'C:\cheetah\reports') / ('existing_routes_vcf_v2_screen_'+task_datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    with stem.with_suffix('.csv').open('x',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    with stem.with_suffix('.json').open('x',encoding='utf-8') as f:
        json.dump(report,f,indent=2)
    print(f'Report: {stem}.json and .csv',flush=True)
    print('Paths with incomplete candidate coverage:',report['paths_without_complete_candidate_coverage'])
    print('Pairs with incomplete candidate coverage:',report['pairs_without_complete_candidate_coverage'])
    print('First five for review:',json.dumps(ranked[:5]))


if __name__=='__main__':
    main()
