# Existing-route screen: VCF v2

3 September 2026. Completed without recalculating paths or current flow.

All 540 saved polylines were screened: 45 pairs x four years x three vegetation
weights. Pair sets match the stored balanced-2012 report. Priority eligibility
was annotated from the existing priority table, not reassigned.

## Findings

- No saved route intersects completely missing candidate vegetation within its
  line footprint. All geometry length was accounted for on comparable cells.
- 31 route instances intersect some cells with common usable native coverage
  below 95%. These have measurements, but coverage warrants attention. The
  threshold is diagnostic, not a biological validity cutoff.
- Holding each route fixed, changes to its integrated resistance are:

| Vegetation weighting | Median signed cost change (%) | Largest absolute net cost change (%) | Median cost-weighted absolute local change (%) |
|---|---:|---:|---:|
| Low | +0.216 | 1.195 | 0.880 |
| Balanced | +0.494 | 4.704 | 1.572 |
| High | +0.913 | 8.179 | 2.480 |

The last column sums absolute local changes before dividing by original cost;
it prevents increases/decreases along a route from cancelling. Its maximum is
2.541%, 5.094% and 8.856% for low, balanced and high respectively.

Pair 17–24 in 2016 has the largest balanced absolute local-change measure:
5.094%, with net cost increase 4.704%. It remains marked eligible in the prior
priority table; this screen does not independently validate its eligibility.
It is a useful first candidate for a bounded reoptimization test, not evidence
that all other routes can be skipped or that a final rerun is unnecessary.

## Method and checks

Each existing polyline segment was split at grid boundaries. Its length inside
each cell was multiplied by old and candidate resistance. Candidate resistance
holds non-vegetation terms fixed and adds weight * (new V - old V). No new GIS
raster, route geometry, core or project state was written.

Segment traversal tests covered horizontal and reversed lines, diagonals,
out-of-grid sections and zero-length segments. Total integrated geometry
length matches saved PATH_KM. As an additional independent check, old line
integrals agree with recorded COST_RAW to a maximum relative difference of
0.000006552%. This verifies the screening integration against the saved paths;
the diagnostic integrals were not written back into COST_RAW.

## Limits and next decision

This is not optimization. Lower-cost alternatives away from existing routes
may change even when fixed-route cost changes are small. No inference of
unchanged priority ranking, temporal direction or current-flow robustness is
justified yet. The 4,866 cells with no new vegetation mean still need an explicit
missing-land/water policy before a final resistance domain is adopted.

Retain completed runs. Resolve the candidate domain and perform a bounded
test starting with the most exposed link before scheduling any full batch.
No solver run was launched or authorized by this screen.

## Prepared one-pair diagnostic

`test_vcf_v2_pair_17_24_2016.py` is ready for the user to run. Its read-only
preflight passed against the actual files: balanced 2016, source 17, destination
24, one CostDistance calculation. It retains old resistance in 4,866 cells
without candidate VCF, solely to preserve the old domain for this controlled
test. The saved route costs 56,723.332 under the old model and 59,391.812 under
the candidate. A maximum accumulated cost of 62,361.403 (5% above that feasible
route) bounds the search by cost, not geographic corridor. Positive costs ensure
the true optimum cannot require a prefix more costly than that feasible bound.

Execution will create a fresh dated folder under `C:\cheetah\diagnostics`,
with candidate resistance, source/destination copies, saved/new routes,
cost-distance/backlink rasters and JSON comparison. It does not add layers,
save the project, overwrite production data or start a batch. It will report
fallback use and directional 1 km/5 km route-buffer overlap. The preflight did
not run a solver. The user subsequently completed the test; results follow.

## Completed pilot and endpoint inspection

The balanced 2016 route from core 17 to 24 was recalculated successfully.
Optimized cost changed from 56,723.332 to 57,313.445 (+1.0403%); length
changed from 32.071 to 33.071 km. The new route costs 3.4994% less than
retaining the old route on the candidate surface. Only 21.17% of the new
route lies within 1 km of the old route, and 37.02% within 5 km. These
distances are descriptive, not biological thresholds. Neither missing-VCF
fallback cells nor cells below 95% common coverage intersect the new route.

Endpoint inspection confirms that both routes connect the same fixed core
polygons, with both endpoints inside their assigned cores. Departure within
core 17 moved 1.000 km; arrival within core 24 moved 9.055 km. Endpoint
choice therefore contributes to the geographic difference; the analysis
does not partition endpoint effects from intermediate route selection.
These are core-to-core optima, not routes between fixed point endpoints.
Small cost change does not establish spatial route stability or network-wide
robustness. Final missing-data policy and production adoption remain unresolved.

Evidence folder:
`C:\cheetah\diagnostics\vcf_v2_pair17_24_2016_20260903_155703_741091`
contains `comparison.json`, `endpoint_comparison.json`, and
`route_endpoint_comparison.png`. Endpoint inspection ran no additional solver
and changed no production datasets or maps. A separate optional ArcGIS map
script is `outputs\show_vcf_pilot_comparison.py`.

## Reproducible outputs

- Script: `outputs\screen_existing_routes_vcf_v2.py`
- Per-route CSV: `C:\cheetah\reports\existing_routes_vcf_v2_screen_20260903_154637_649911.csv`
- Pair review order, source geometry hashes and caveats:
  `C:\cheetah\reports\existing_routes_vcf_v2_screen_20260903_154637_649911.json`
