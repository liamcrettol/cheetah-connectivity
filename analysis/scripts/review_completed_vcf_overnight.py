"""Verify completed diagnostic paths and join existing priorities; no solver."""
import csv
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import statistics
import arcpy

ROOT = Path(r'C:\cheetah\diagnostics\vcf_v2_balanced_overnight_v1')
PRIORITY = Path(r'C:\cheetah\reports\conservation_priority_links_temporal.csv')

def main():
    status = json.loads((ROOT/'STATUS.json').read_text())
    manifest = json.loads((ROOT/'manifest.json').read_text())
    if status['state'] != 'COMPLETE': raise ValueError('Run not complete')
    with (ROOT/'comparisons.csv').open(newline='',encoding='utf-8-sig') as f: rows=list(csv.DictReader(f))
    with PRIORITY.open(newline='',encoding='utf-8-sig') as f: priorities=list(csv.DictReader(f))
    pmap={tuple(sorted((int(r['from_core']),int(r['to_core'])))):r for r in priorities}
    if len(pmap)!=len(priorities): raise ValueError('Duplicate priority rows')
    expected={(y,*p) for y in manifest['years'] for p in manifest['pairs']}
    seen=set()
    for r in rows:
        for k in ('year','from_core','to_core'): r[k]=int(r[k])
        for k in r.keys()-{'year','from_core','to_core','candidate_path','geometry_sha256'}:
            r[k]=float(r[k])
            if not math.isfinite(r[k]): raise ValueError('Nonfinite metric')
        key=(r['year'],r['from_core'],r['to_core'])
        if key in seen: raise ValueError('Duplicate comparison')
        seen.add(key)
        fc=r['candidate_path']
        field=next(f.name for f in arcpy.ListFields(fc) if f.name.upper() in ('PATHCOST','PATH_COST'))
        with arcpy.da.SearchCursor(fc,['SHAPE@',field]) as cur: found=list(cur)
        if len(found)!=1: raise ValueError('Wrong output feature count')
        geom,cost=found[0]
        if hashlib.sha256(bytes(geom.WKB)).hexdigest()!=r['geometry_sha256']: raise ValueError('Changed geometry')
        if cost != r['new_cost'] or abs(geom.length/1000-r['new_length_km'])>1e-6: raise ValueError('Changed cost/length')
        if abs(100*(r['new_cost']/r['old_cost']-1)-r['optimized_cost_change_pct'])>1e-9: raise ValueError('Cost delta mismatch')
        r['minimum_directional_overlap_1km_pct']=min(r['new_within_1000m_of_old_pct'],r['old_within_1000m_of_new_pct'])
        r['minimum_directional_overlap_5km_pct']=min(r['new_within_5000m_of_old_pct'],r['old_within_5000m_of_new_pct'])
        p=pmap.get((r['from_core'],r['to_core']),{})
        r['previous_priority_eligible']=p.get('primary_priority_eligible_final','not_in_priority_table')
        r['previous_importance_rank']=p.get('importance_rank','')
        for k in ('minimum_directional_overlap_1km_pct','minimum_directional_overlap_5km_pct'):
            if not -1e-6<=r[k]<=100.000001: raise ValueError('Overlap out of range')
    if seen!=expected or len(rows)!=180: raise ValueError('Incomplete pair/year set')
    records=list(ROOT.glob('*/source_*/complete.json'))
    checkpoint_rows=[r for p in records for r in json.loads(p.read_text())]
    if len(checkpoint_rows)!=180: raise ValueError('Checkpoint count mismatch')
    for r in checkpoint_rows:
        key=(r['year'],r['from_core'],r['to_core'])
        match=next(x for x in rows if (x['year'],x['from_core'],x['to_core'])==key)
        if r['geometry_sha256']!=match['geometry_sha256'] or r['new_cost']!=match['new_cost']: raise ValueError('Checkpoint differs from CSV')
    temporal=[]
    pairreviews=[]
    for a,b in manifest['pairs']:
        subset=[r for r in rows if (r['from_core'],r['to_core'])==(a,b)]
        byyear={r['year']:r for r in subset}
        old=100*(byyear[2024]['old_cost']/byyear[2012]['old_cost']-1)
        new=100*(byyear[2024]['new_cost']/byyear[2012]['new_cost']-1)
        p=pmap.get((a,b),{})
        t={'from_core':a,'to_core':b,'old_change_pct':old,'candidate_change_pct':new,'difference_pp':new-old,
           'sign_changed':(old>0)!=(new>0) or (old==0)!=(new==0),
           'previous_priority_eligible':p.get('primary_priority_eligible_final','not_in_priority_table')}
        temporal.append(t)
        worst=min(subset,key=lambda r:r['minimum_directional_overlap_1km_pct'])
        pairreviews.append({'from_core':a,'to_core':b,'worst_year':worst['year'],
                            'worst_min_directional_overlap_1km_pct':worst['minimum_directional_overlap_1km_pct'],
                            'worst_min_directional_overlap_5km_pct':min(r['minimum_directional_overlap_5km_pct'] for r in subset),
                            'max_abs_cost_change_pct':max(abs(r['optimized_cost_change_pct']) for r in subset),
                            'max_endpoint_shift_km':max(max(r['source_endpoint_shift_km'],r['destination_endpoint_shift_km']) for r in subset),
                            'previous_priority_eligible':t['previous_priority_eligible'],
                            'previous_importance_rank':p.get('importance_rank','')})
    pairreviews.sort(key=lambda r:r['worst_min_directional_overlap_1km_pct'])
    summary={'verified_routes':180,'source_checkpoints':len(records),'pairs':45,
             'previous_priority_pairs':sum(p.get('primary_priority_eligible_final')=='yes' for p in priorities),
             'median_abs_cost_change_pct':statistics.median(abs(r['optimized_cost_change_pct']) for r in rows),
             'max_abs_cost_change_pct':max(abs(r['optimized_cost_change_pct']) for r in rows),
             'median_min_directional_overlap_1km_pct':statistics.median(r['minimum_directional_overlap_1km_pct'] for r in rows),
             'routes_below80pct_min_overlap_1km':sum(r['minimum_directional_overlap_1km_pct']<80 for r in rows),
             'pairs_below80pct_in_any_year':sum(r['worst_min_directional_overlap_1km_pct']<80 for r in pairreviews),
             'previous_priority_pairs_below80pct_in_any_year':sum(r['worst_min_directional_overlap_1km_pct']<80 and r['previous_priority_eligible']=='yes' for r in pairreviews),
             'routes_touching_fallback':sum(r['fallback_length_m']>.001 for r in rows),
             'routes_touching_valid_below95pct_coverage':sum(r['below95pct_coverage_valid_length_m']>.001 for r in rows),
             'temporal_sign_changes':sum(r['sign_changed'] for r in temporal),
             'max_temporal_difference_pp':max(abs(r['difference_pp']) for r in temporal)}
    out=Path(r'C:\cheetah\reports')/('vcf_completed_review_'+dt.datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    report={'summary':summary,'pair_reviews':pairreviews,'temporal':temporal,
            'limits':['80% overlap is a descriptive review trigger, not a biological stability criterion.',
                      'Previous priority eligibility is contextual; no ranking or eligibility was recalculated.',
                      'Only balanced-weight diagnostic results are verified; no inference of final current-flow robustness.',
                      'No route touching fallback does not rule out alternative routes becoming cheaper if fallback cost is lowered.']}
    out.with_suffix('.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    with out.with_suffix('.csv').open('x',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(pairreviews[0]));w.writeheader();w.writerows(pairreviews)
    lines=['# Completed VCF diagnostic review','','All 180 output geometries, costs and lengths verified against receipts; no solver run.','']
    lines += [f'- {k}: {v}' for k,v in summary.items()]
    lines += ['','## Most spatially sensitive pairs','','| Pair | Worst year | Min. directional 1 km overlap (%) | Previously priority eligible | Prior importance rank |','|---|---:|---:|---|---:|']
    lines += [f'| {r["from_core"]}-{r["to_core"]} | {r["worst_year"]} | {r["worst_min_directional_overlap_1km_pct"]:.2f} | {r["previous_priority_eligible"]} | {r["previous_importance_rank"]} |' for r in pairreviews[:12]]
    lines += ['','## Limits','']+['- '+x for x in report['limits']]
    out.with_suffix('.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2));print('REPORT:',out.with_suffix('.md'))

if __name__=='__main__':main()
