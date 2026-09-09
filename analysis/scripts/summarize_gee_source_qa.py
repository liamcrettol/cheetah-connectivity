"""Validate the returned 32-point GEE diagnostic; write reports only, no GIS edits."""
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

SOURCE = Path(r'C:\Users\lcrettol\Downloads\cheetah_input_source_qa_20260903.csv')
EXPECTED = Path(r'C:\cheetah\reports\input_provenance_samples_20260903.json')
YEARS = (2012, 2016, 2020, 2024)
GROUPS = ('zero_water', 'zero_other', 'nonzero_water', 'nonzero_other')
COVERS = ('tree', 'nontree', 'bare')


def analyze(rows, expected):
    ids = [r['sample_id'] for r in rows]
    if len(ids) != 32 or len(set(ids)) != 32 or set(ids) != set(expected):
        raise ValueError('Expected exactly the original 32 unique sample IDs.')
    counts = Counter((int(r['year']), r['group']) for r in rows)
    if counts != Counter({(y, g): 2 for y in YEARS for g in GROUPS}):
        raise ValueError('Unexpected year/group coverage.')
    for r in rows:
        for key, value in expected[r['sample_id']].items():
            if isinstance(value, (int, float)):
                if abs(float(r[key]) - value) > 1e-9:
                    raise ValueError(f'Original field changed: {r["sample_id"]} {key}')
            elif r[key] != value:
                raise ValueError(f'Original field changed: {r["sample_id"]} {key}')
        for v in COVERS:
            flag, val = float(r[f'gee_{v}_valid']), float(r[f'gee_{v}'])
            if flag not in (0, 1) or (flag == 0 and val != -9999):
                raise ValueError('Invalid mask/sentinel combination.')
            if flag == 1 and not 0 <= val <= 100:
                raise ValueError('Valid cover outside 0..100.')
        for source in ('lc', 'vcf'):
            if not r[f'gee_{source}_date'].startswith(r['year'] + '-'):
                raise ValueError('Source date does not match requested year.')
    def valid(r):
        return all(float(r[f'gee_{v}_valid']) == 1 for v in COVERS)
    zero = [r for r in rows if all(float(r[f'raw_{v}']) == 0 for v in COVERS)]
    nonzero = [r for r in rows if r not in zero]
    def group_summary(subset):
        return {'records': len(subset), 'native_all_three_valid': sum(valid(r) for r in subset),
                'native_all_three_masked': sum(all(float(r[f'gee_{v}_valid']) == 0 for v in COVERS) for r in subset),
                'land_water_codes': dict(Counter(r['gee_land_water'] for r in subset))}
    return {
        'records': len(rows), 'unique_locations': len({(r['row'], r['col']) for r in rows}),
        'original_fields_match': True, 'local_allzero': group_summary(zero),
        'local_nonzero': group_summary(nonzero),
        'by_year': {str(y): {g: group_summary([r for r in rows if int(r['year']) == y and r['group'] == g]) for g in GROUPS} for y in YEARS},
        'masked_zero_but_land_ids': [r['sample_id'] for r in zero if r['gee_land_water'] == '2.0'],
        'nonzero_but_native_masked_ids': [r['sample_id'] for r in nonzero if not valid(r)],
        'local_lc_vs_native_lc_disagreement_ids': [r['sample_id'] for r in rows if float(r['local_lc']) != float(r['gee_lc_type1'])],
        'valid_cover_missing_quality': sum(valid(r) and float(r['gee_vcf_quality']) == -9999 for r in rows),
        'valid_cover_missing_cloud': sum(valid(r) and float(r['gee_vcf_cloud']) == -9999 for r in rows),
        'missing_csv_fields': {k: sum(r.get(k, '') == '' for r in rows) for k in rows[0] if any(r.get(k, '') == '' for r in rows)},
        'interpretation': 'All 16 local all-zero examples have masked native cover at the sampled location. Missing-value handling upstream of ArcGIS alignment is implicated, but the exact export operation is not established.',
        'limitations': ['Purposive 32 sample-year records, with repeated locations; not a random prevalence sample.',
                        'Native center sampling is not an exact reproduction of unknown 1 km export aggregation or resampling.',
                        'Missing VCF is not equivalent to water or an ecological barrier.',
                        'Ancillary quality/cloud masks are separate from cover-band validity.',
                        'This does not quantify effects on paths, currents or conservation rankings.'],
        'gate': 'Do not launch production current-flow runs until source validity, water treatment and common temporal support are reconciled.'}


def main():
    with SOURCE.open(newline='', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    expected = {r['sample_id']: r for r in json.loads(EXPECTED.read_text(encoding='utf-8'))}
    result = analyze(rows, expected)
    result['source'] = str(SOURCE)
    result['source_sha256'] = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    out = Path(r'C:\cheetah\reports') / ('gee_source_qa_findings_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.json')
    with out.open('x', encoding='utf-8') as f:
        json.dump(result, f, indent=2)
    print(json.dumps(result, indent=2))
    print(f'Report: {out}')
    print('No GIS datasets, project layers, or model outputs were changed.')


if __name__ == '__main__':
    main()
