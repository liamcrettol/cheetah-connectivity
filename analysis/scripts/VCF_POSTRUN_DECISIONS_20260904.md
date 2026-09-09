# Post-run review and next dependency — 2026-09-04

## Verified completed work

All 180 candidate path geometries, stored lengths and solver costs match their
recorded receipts. All 84 source checkpoints reconcile. All 45 pairs occur in
each of the four years. No production data were edited and no additional
CostDistance or Circuitscape calculation was started during this review.

Evidence: `C:\cheetah\reports\vcf_completed_review_20260904_074611_029018.json`
(matching CSV/Markdown). Visualization:
`C:\cheetah\reports\vcf_review_examples_20260904.png`.

## Interpretation

- Median absolute optimized cost difference is 0.2213%; maximum is 1.9625%.
- Median minimum of the two directional 1 km overlaps is 96.8992%.
- 49 route-year comparisons fall below 80% using that overlap measure;
  29 pairs do so in at least one year, including 21 of the 32 previously
  eligible priority pairs. This is descriptive screening, not a biological
  threshold or an automatic removal from priorities.
- No 2012-2024 cost-change sign reversal across 45 pairs. Magnitudes still
  differ: maximum absolute difference is 2.7156 percentage points. Link
  38-40 changes from +2.6250% to +1.0393%.
- No route touches fallback cells. Eight touch some valid VCF area below
  95% common coverage. Coverage is not itself an ecological-accuracy test.
- Link-level temporal direction is more stable than exact path location in
  this controlled balanced test. Do not label narrow lines as validated
  conservation corridors. Corrected low/high and current-flow results have
  not been established by this run.

## Missing-cell monotonicity: conditional computational result

Let P be a minimum-cost route under the diagnostic raster. If a modification
only increases costs on cells P never traverses, P retains its cost while
every alternative route's cost can only increase or stay equal. P therefore
remains an optimum, subject to the same graph/solver conventions and numerical
tolerances. Removing only such cells has the analogous effect when P and its
endpoints remain feasible. This observation does NOT establish ecological
validity of raising costs or masking water, nor uniqueness of an optimum.

Since none of the 180 routes uses fallback cells, higher-cost treatment of
only those cells need not automatically require another path optimization.
Lower-cost imputation could make a new alternative attractive; unchanged
fallback exposure cannot rule that out. Other changed cells, low/high weights,
current flow, focal-area definitions and changes to connectivity rules are
outside this argument. Do not use it as a blanket production approval.

## Additional centrality reporting correction

The original `calculate_core_link_betweenness.py` uses unweighted shortest
paths and divides undirected raw edge scores by (n-1)(n-2)/2 = 231. Standard
edge normalization divides by n(n-1)/2 = 253 for 23 nodes. Independent
NetworkX 3.6 verification confirms that all 45 corrected scores equal the
old scores times 21/23. All ties and rankings remain unchanged. Top link
38-40 is 0.4090909 rather than 0.4480519.

Source: [NetworkX edge-betweenness documentation](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.centrality.edge_betweenness_centrality.html).
The corrected versioned values are in
`C:\cheetah\reports\edge_normalization_audit_20260904_074907_825273.csv`.
Original tables, script and paper remain untouched; propagate the arithmetic
correction consistently at the production-update stage. No GIS rerun needed.
Because the graph is unweighted and fixed, unchanged centrality is structural
and does not validate route or ecological robustness.

## Next required input

Prepared `export_gee_water_class_fractions_v1.js`. Run it in the GEE Code
Editor and start its FOUR tasks. Download `water_class_fractions_v1_YEAR.tif`
for 2012, 2016, 2020 and 2024 into Downloads. Script syntax checked with Node;
Earth Engine execution has not been performed locally. Runtime source-count
and native-grid checks must pass before exports are created.

These new diagnostics estimate the fraction of native 500 m area classified
as water, land, wetland, barren, or disagreement inside each 1 km model cell.
They are not direct fractional inundation observations. LW and LC_Type1 come
from the same product; their agreement is not independent validation. All
validity fractions are exported so missing values cannot silently become land.
No exclusion threshold, interpolation or resistance calculation is applied.

Product/API definitions checked against:

- [MCD12Q1.061 catalog](https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MCD12Q1)
- [Earth Engine reduceResolution](https://developers.google.com/earth-engine/apidocs/ee-image-reduceresolution)

After download: verify dimensions/affine/CRS, all 11 bands, fraction bounds,
water+land=LW valid, and both-water+both-land+disagreement=both-valid.
Then cross-tabulate the 4,866 missing cells and the Botswana cluster against
these area classifications. Final missing-land treatment still requires
evidence; class-11 wetlands and all VCF NoData must not be blanket barriers.

## What is not yet updated

No live spreadsheet, GitHub commit, manuscript, production priority layer or
final map was changed. This local review preserves the distinction between
verified diagnostics and pending production decisions.
