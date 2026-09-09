# Current-flow input audit, 3 September 2026

## Assessment: needs input/protocol reconciliation before another production run

This is computational quality assurance, not validation against cheetah movement.
No solver was launched. No source rasters, resistance surfaces, cores, maps, or
paper files were edited during the audit. Only audit scripts and reports were
created. The local repository inspected was at commit `d818e29`; it was not
pulled or represented as the latest remote manuscript.

## Checks that passed

- Completed reference run: four years, 253 pairs/year, 1,012 finite positive
  pairwise effective resistances; no disconnected focal pairs. Pair lists match
  the 23 fixed core IDs and their resistance matrices.
- The 12 saved vegetation scenarios have the same 2,310 by 2,200 grid, 1,000 m
  cells, ESRI:102022, and 2,503,870 valid model cells. All 23 cores remain
  represented. Five core pixels are excluded by the resistance support in each
  case (one in core 18, four in core 32); no core disappears.
- All 23 formula checks passed after explicit NoData-mask handling: terrain
  from mean slope, four vegetation transforms, twelve weighted surfaces, and
  six fence multiplier/combination checks.
- Terrain implements `1 + 9 * clamp((mean_slope - 10) / 20, 0, 1)` and remains
  within 1 to 10. This verifies the saved formula, not its ecological calibration.
- Vegetation scenario weights match the later decision register:

| Scenario | Human pressure | Vegetation | Terrain | Fences included? |
|---|---:|---:|---:|---|
| Completed current-flow reference | 0.80 | 0 | 0.20 | No |
| Vegetation-low | 0.70 | 0.10 | 0.20 | No |
| Vegetation-balanced | 0.60 | 0.20 | 0.20 | No |
| Vegetation-high | 0.40 | 0.40 | 0.20 | No |

- Combined KAZA + Kruger fence multipliers use the maximum, avoiding double
  multiplication at overlaps. Documented and conservative versions penalize
  5,654 and 6,001 cells respectively within the balanced model support. Both
  cover that support without multiplier NoData holes.

## Issues requiring resolution

### 1. Wrong generation of resistance surfaces was exported

`prepare_pairwise_circuitscape_inputs.py` explicitly selected
`resistance_primary_unfenced_combined_YEAR`, not
`resistance_temporal_veg_balanced_YEAR`. Therefore the completed current-flow
maps exclude vegetation and fences. Preserve them as pressure-plus-terrain
reference results. Do not relabel them as vegetation-balanced or fence-robust.

The later vegetation scenarios do not supersede the need for a clearly defined
scenario ensemble. Balanced is one specified weighting, not an empirically
proven best model. Existing sensitivity results for 45 least-cost pairs do not
establish robustness of cumulative current from all 253 core pairs.

### 2. All-zero vegetation triplets receive an unsupported intermediate value

Inside the actual modeled landscape, the number of cells where tree, non-tree,
and bare cover all equal zero is:

| Year | All-zero VCF cells | Of these, raw land-cover code 17 |
|---|---:|---:|
| 2012 | 5,519 | 2,716 |
| 2016 | 5,519 | 3,100 |
| 2020 | 5,519 | 3,118 |
| 2024 | 5,632 | 2,691 |

The implemented vegetation formula is
`1 + 9 * mean(bare, 100 - min(100, tree + nontree)) / 100`, after clamping each
band to 0 to 100. An all-zero triplet gives vegetation resistance 5.5. This is
an arithmetic consequence, not an observation of intermediate movement cost.
Non-water-code overlaps also occur, so treating all such cells as water is not
justified. Trace the original GEE export and source QA before replacing,
excluding, or imputing them. Do not silently change valid zero tree cover into
NoData; the problem is the simultaneous all-zero composition.

### 3. Land-cover legend mismatch confirmed; water exclusion needs repair

The current crosswalk labels code 0 as water and code 17 as unclassified/NoData.
Official MCD12Q1.061 documentation instead defines **LC_Type1** code 17 as water
bodies and code 11 as permanent wetlands. **LC_Type2** uses code 0 for water.
All four local land-cover TIFFs report the band name `LC_Type1`. The current
crosswalk therefore does not match the declared band's official legend.
Unrecorded upstream remapping cannot be ruled out without the export code;
there is no evidence for such remapping in the inspected local files.

There are 3,889 to 4,251 raw code-17 cells within the model support each year;
2,909 have code 17 in all four snapshots. With the declared LC_Type1 legend,
permanent-water-class cells remain traversable despite the protocol's
water-exclusion statement. These are diagnostic cell counts, not measured
areas of pure open water. Values were read at model-cell centers using nearest
source-cell lookup; no diagnostic resampling was written to disk.

The six-class context 'water' category also combines wetlands with water.
Do not reuse it as an impermeable-water mask without separating the classes.
The existing HydroSHEDS water mask combines rivers and lakes and likewise
must not automatically become a blanket barrier.

### 4. Decision records describe different generations of the model

`combined_anthropogenic_resistance_decision.csv` retains the older VCF weight
of zero. `temporal_vegetation_sensitivity_register.csv` records the later
10/20/40% vegetation experiment. The protocol's RES-01..RES-06 ensemble is not
the same object as these three vegetation weights. Reconcile the scenario
register and actual implementations rather than claiming that all planned
scenarios have been run. Kruger boundary status, finite fence multipliers,
and the distinction between reference results and conservation eligibility
must remain explicit.

## Limits of the numerical checks

The anthropogenic component was recovered as
`(saved_reference - 0.2 * terrain) / 0.8` to test agreement between saved model
generations. It was not independently rebuilt from native built-up, radiance,
road and livestock inputs. No new terrain-response, fence-permeability,
resolution, core-definition, or empirical movement validation was performed.
The original export code/QA and permanent-water mask therefore remain gates,
even though the formula checks passed.

Current concentration is not cheetah occupancy probability. Temporal current
differences describe redistribution under the specified pair injections;
effective resistance is a distinct measure of modeled isolation. Core-interior
source/ground effects are not automatically conservation bottlenecks.

## Safe next step

The 32-point Earth Engine diagnostic has now completed and the returned CSV
was validated. See the findings below. In all 16 selected all-zero examples, the downloaded
VCF TIFFs also have three valid numeric zeros at the nearest source-cell
centers. Thus those examples were not introduced solely by ArcGIS alignment.
The samples are deterministic diagnostic examples, not prevalence estimates.
The native Earth Engine check samples model-cell centers and is not an exact
reproduction of an unknown 1 km aggregation operation. Its server-side
execution was performed by the user in their authenticated Earth Engine session.

### Returned Earth Engine QA: 3 September 2026

Input: `C:\Users\lcrettol\Downloads\cheetah_input_source_qa_20260903.csv`.
SHA-256: `615047f6969ebf584a82171819d7c4eae744d3ba3a65cb764fec0d0dafd35fb4`.
The 32 sample-year records match every original sample ID, coordinate and local
value in the selection JSON. There are 14 distinct spatial locations, repeated
across years; these are not 32 independent random locations. Each year has
two examples from each of four diagnostic groups. No CSV fields are empty.
Source dates match requested years. Mask flags and -9999 sentinels agree.

| Diagnostic group | Records | All three native VCF bands valid | All three native VCF bands masked |
|---|---:|---:|---:|
| Locally all-zero triplets | 16 | 0 | 16 |
| Locally nonzero triplets | 16 | 15 | 1 |

All 16 local all-zero examples have no native VCF observation at the sampled
location. Fourteen carry the source LW water flag and two the land flag. The
two land-flagged cases are `2024_zero_water_2` and `2024_zero_other_4`.
Consequently missing vegetation must not automatically become either a
measured intermediate resistance (5.5) or an impermeable water barrier.

The local nonzero example `2024_nonzero_water_6` is also masked natively.
Seven records disagree between local LC and native sampled LC; native cover
values often differ from local nonzero values. Sampling resolution, grid
position and unknown aggregation/resampling can explain such discrepancies;
the point test alone cannot identify the precise original export operation.
It implicates upstream source/export handling but does not prove that a
specific `unmask(0)` command was used. Local zeros were already present in the
downloaded TIFFs, before the later ArcGIS alignment.

Of the 15 records with valid cover, seven have missing ancillary Quality and
twelve have missing ancillary Cloud values. These are separate band masks;
do not discard valid cover merely because an ancillary band is unavailable.
No ecological calibration, map-wide error prevalence, route impact or
conservation-ranking impact has been established by this diagnostic.

Reproducible analyzer: `outputs\summarize_gee_source_qa.py`.
Machine-readable report:
`C:\cheetah\reports\gee_source_qa_findings_20260903_135857_388016.json`.

Next diagnostic script: `outputs\export_gee_source_validity_audit.js`.
It creates four five-band Byte GeoTIFF export tasks at the exact model grid,
sampling native VCF validity/all-zero flags and native LC_Type1/LW flags.
It keeps missing values distinct from measured zeros. It is a full-grid
center-sample QA layer, not a fractional-water map or replacement resistance
input. LC in this export is sampled directly from its own native grid; the
earlier point CSV stacked LC on the native VCF grid, so LC boundary differences
between the two diagnostics are possible. JavaScript syntax was checked;
authenticated Earth Engine export and downloaded-grid checks remain pending.
No raster or connectivity run is launched automatically.

### Full-grid source-validity exports checked: 3 September 2026

The user supplied the four GeoTIFFs in
`C:\Users\lcrettol\Downloads\drive-download-20260903T203616Z-1-001.zip`.
They were extracted without overwriting existing datasets into
`C:\cheetah\raw\source_qa\gee_validity_20260903`.
All five band names and flag encodings were checked. CRS, cell size and
northwest origin agree with the model. The exported files contain 2,201 rows,
not the expected 2,200, with one extra southern row containing flag data.
The audit uses the first 2,200 rows, exactly the existing model footprint;
no resampling or raster rewrite was performed. Do not directly substitute
these full 2,201-row files for the model grid.

| Year | Native VCF missing at model-cell center | Local all-zero, native masked | Local all-zero, native valid | Local nonzero, native masked |
|---|---:|---:|---:|---:|
| 2012 | 11,380 | 5,384 | 135 | 5,996 |
| 2016 | 11,385 | 5,384 | 135 | 6,001 |
| 2020 | 11,381 | 5,384 | 135 | 5,997 |
| 2024 | 9,931 | 5,467 | 165 | 4,464 |

Counts are within the 2,503,870-cell modeled landscape. There are no unknown
validity flags within that landscape and no all-zero triplets among native
valid center samples in any year. All 32 earlier point VCF-validity flags
match the corresponding full-grid raster samples.

Across years, 11,773 distinct model-cell centers (0.4702%) are missing native
VCF in at least one snapshot; 2,492,097 have valid native VCF in every year.
This percentage describes source-data availability at centers, **not** the
fraction of habitat known to be impassable or the magnitude of model error.
Spatial support differences prevent treating every center/export mismatch
as a proven error. A zero-only repair would miss 4,464–6,001 nonzero local
cells/year with masked native centers, and would discard 135–165 local
all-zero cells/year whose native centers have valid cover.

Missing centers include both source LW water and land flags: land-flagged
counts are 2,071, 2,076, 2,072 and 1,542 by year. A common source-validity mask
would therefore conflate missing land observations with physical barriers
if applied directly as the connectivity domain. Do not implement that shortcut.

There are 2,862 centers classified LC_Type1 water in all four native samples,
versus 9,760 centers flagged LW water in all four. These products/definitions
are not interchangeable, and neither result measures pure-water fraction
in the whole 1 km cell. They also differ from earlier nearest lookup of the
old 1 km categorical exports; those earlier counts have different support.

A hypothetical all-year native-validity restriction removes 111 currently
modeled core pixels across five cores (18, 26, 32, 42 and 49). All 23 cores
retain pixels and each still exceeds 500 model cells. **This does not verify
between-core connectivity**, preserve exact core geometry, or justify changing
the core definitions. No production core raster was edited.

Reproducible script: `outputs\audit_downloaded_gee_validity.py`.
Report: `C:\cheetah\reports\gee_validity_grid_audit_20260903_144026_211984.json`.
Next production-preparation step remains new, versioned mask-preserving VCF
exports with explicit spatial aggregation and valid-coverage information,
plus a separately justified permanent-water treatment. Retain originals and
recheck common temporal support, cores and pair connectivity before rerunning
production solvers. The diagnostic center flags alone are not replacement
VCF measurements or a final exclusion mask. No solver or GIS model edit was
performed for this check.

### Candidate export prepared after full-grid QA

`outputs\export_gee_vcf_maskpreserved_v2.js` prepares four new mask-preserving
VCF exports. Details, band definitions and acceptance gates are in
`outputs\VCF_MASKPRESERVED_V2_EXPORT_NOTES.md`. The script uses common usable
native pixels across the four years and overlap-weighted means at 1 km, with
annual and common coverage fractions. It does not implement a water barrier,
imputation rule or minimum coverage threshold. This changes aggregation and
subpixel support relative to the original unknown export, so it must not be
reported as merely changing resistance weights. Syntax is checked; server-side
execution and output validation are pending. No production inputs were changed.

### Candidate exports downloaded and compared (later on 3 September)

The user completed the export. Four TIFFs from
`C:\Users\lcrettol\Downloads\drive-download-20260903T213714Z-1-001.zip`
were extracted into the new directory
`C:\cheetah\raw\source_qa\vcf_maskpreserved_v2_20260903`.
The earlier pending status above is superseded for export and structural QA,
not for production acceptance.

All four files have exactly 2310 x 2200 cells, the correct origin, 1 km cell
size, ESRI:102022, eight expected bands and -9999 NoData. Cover bands share
their validity mask; means are present exactly where common coverage is
positive. Coverage fractions are finite, within 0..1, and satisfy common <=
annual usable <= annual source-valid. Annual exclusions reconcile. Common
coverage is identical across years. Cover values are within 0..100 and sum
to 100 to Float32 precision over the comparable model cells.

Within the existing 2,503,870-cell model footprint, common native coverage is:

- Zero: 4,866 cells (0.1943%). No candidate vegetation mean; **not automatically barriers**.
- Greater than zero but below 50%: 5,328 cells.
- 50% to below 95%: 13,941 cells.
- At least 95%: 2,479,735 cells (99.0361%).

These bins are descriptive, not approved inclusion thresholds. All 23 cores
retain candidate mean-covered pixels; only one additional currently modeled
pixel in core 18 has no candidate vegetation mean. This is not a test of
between-core connectivity or proof that exact core geometry should change.

The comparison holds every non-vegetation term fixed and computes the
candidate change in memory as weight * (new V - saved old V), retaining the
existing vegetation transform. Saved old V was independently recomputed from
the old aligned cover components and matched within numerical tolerance.
Results below use 2,499,004 comparable cells, not missing-mean cells:

| Year | Median absolute balanced-resistance change (%) | 95th percentile (%) | Comparable cells with >5% change (%) |
|---|---:|---:|---:|
| 2012 | 0.891 | 5.529 | 6.22 |
| 2016 | 0.914 | 5.931 | 7.06 |
| 2020 | 0.885 | 5.645 | 6.47 |
| 2024 | 0.849 | 5.366 | 5.81 |

The report also contains low/high weights, individual cover-component changes,
common-coverage strata and temporal vegetation-change differences. Changes are
not confined to formerly missing centers: aggregation, alignment and shared
native support change vegetation values throughout the grid. A small median
does not establish unchanged optimal routes; localized changes are much larger.
The unchanged pressure-plus-terrain Circuitscape reference has no vegetation
term and is not directly changed by this VCF replacement.

Script: `outputs\compare_vcf_v2_candidate_inputs.py`.
Reports: `C:\cheetah\reports\vcf_v2_input_impact_20260903_154132_775857.json`
and `.md`. Only reports and extracted new files were written. No production
rasters, project layers, path results or current-flow outputs were changed.
No route/circuit solver was run. Next: screen existing routes for exposure to
larger changes and unresolved coverage, then choose bounded tests after
missing-land/water treatment is explicit. No full rerun is authorized by this
input-only result, nor can previous vegetation-based routes yet be certified
unchanged. Keep all existing work and avoid another unconditional overnight run.

### Existing routes screened without reoptimization

The subsequent fixed-route screen covered all 540 stored path instances.
None intersects a completely missing candidate-vegetation cell along its
polyline; 31 intersect some cells with common native coverage below 95%.
For the balanced weighting, the largest absolute net fixed-route cost change
is 4.704%; for high vegetation weight it is 8.179%. Old line-integral costs
match recorded COST_RAW within 0.000006552% relative difference. These results
do not establish unchanged optimal routes, temporal conclusions or rankings.
See `outputs\VCF_V2_EXISTING_ROUTE_SCREEN.md` for methods, results and report
paths. The first bounded-review candidate is pair 17–24 in 2016; a domain
policy for missing land/water remains necessary before final reoptimization.
No production dataset or project was changed and no path/circuit solver ran.

Also obtain/inspect the GEE code that exported `lc_YEAR_1km.tif` and the three VCF
bands when available. Verify remapping, masking/unmasking,
reducer/resampling, source year and QA treatment. Then prepare new versioned
copies with a documented common support and re-audit. Do not overwrite the
reference outputs or launch another expensive solver until the input gate is
resolved. If support changes, check retained core geometry and pair
connectivity before comparing old and new runs as if only weights changed.

## Evidence files

- `C:\cheetah\circuitscape\reference_output_qc.json`
- `C:\cheetah\reports\circuitscape_full_model_preflight_20260903_133617_757780.json`
- `C:\cheetah\reports\circuitscape_model_mask_context_20260903_133927_835506.json`
- `C:\cheetah\reports\input_provenance_samples_20260903.json`
- `C:\cheetah\reports\temporal_vegetation_sensitivity_register.csv`
- `C:\cheetah\reports\terrain_resistance_decision.csv`
- `C:\cheetah\reports\veterinary_fence_scenario_decision.csv`
- `C:\cheetah\reports\kruger_fence_resistance_scenario_decision.csv`

The earlier file
`circuitscape_full_model_preflight_20260903_133426_484607.json` is an INVALID
first diagnostic pass: it mistook geodatabase NoData for numeric zeros because
`Raster.noDataValue` returned None. Its 34 flags are not GIS-data failures.
Use the later `133617_757780` report, which reads explicit IsNull masks and
has zero formula failures. No model datasets were altered by either pass.

## Product documentation checked

### Completed controlled VCF pilot: spatial sensitivity despite similar cost

The user completed one balanced-2016 CostDistance test for core pair 17-24.
Optimized cost increased 1.0403%; path length increased from 32.071 to
33.071 km. Nevertheless, only 21.17% of the candidate path is within 1 km
of the saved path (37.02% within 5 km). No candidate-path length intersects
old-resistance fallback or below-95%-coverage cells. This is one diagnostic,
not evidence of network-wide robustness or authorization for a full rerun.

Read-only endpoint inspection confirmed both endpoints remain inside their
assigned fixed core polygons. Core-17 departure moved 1.000 km and core-24
arrival moved 9.055 km. Core-to-core endpoint choice contributes to the
shift; its contribution has not been separated from intermediate routing.
Do not describe these as fixed-point routes or infer spatial stability from
the small optimized-cost change.

Evidence: `C:\cheetah\diagnostics\vcf_v2_pair17_24_2016_20260903_155703_741091`
(`comparison.json`, `endpoint_comparison.json`, `route_endpoint_comparison.png`).
Production surfaces, routes and rankings were not replaced. Final water/
missing-land policy remains unresolved. The endpoint inspection required no
new solver run. An optional separate comparison-map script was prepared but
has not been run in the user's ArcGIS Pro session.

### Sources

### 2026-09-04 completed-run review

See `VCF_POSTRUN_DECISIONS_20260904.md` for verified 180-path results, spatial
sensitivity of 21 previously eligible pairs, unchanged temporal signs but
changed magnitudes, the conditional missing-cell monotonicity argument, and
the independently verified edge-normalization correction (ranks unchanged).
New water-class area-fraction export script prepared; user GEE execution and
download are the next dependency. Original outputs and live sheet unchanged.


### Prepared resumable balanced-model overnight diagnostic

User requested an overnight analysis package while credits are limited.
Prepared `run_vcf_v2_balanced_overnight.py` and a background launcher/status
checker; see `VCF_OVERNIGHT_HANDOFF.md`. Scope is 45 existing pairs x four
years, balanced weights only (180 comparisons, at most 84 source solves).
This is controlled old-value fallback, not a final water/missing-land policy.
No production outputs, priorities, other weights or Circuitscape are replaced.
Completed-source and cost-distance checkpoints are fingerprinted/verified;
input/code/version changes stop stale reuse. Positive-cost feasible-route
bounds constrain accumulated cost, not a spatial corridor crop.

All 180 saved routes passed preflight. Comparison and real extraction tests
reproduced the completed 17-24 2016 pilot using its existing distance raster.
The assistant did not launch the overnight batch. It requires the user to run
the launcher; completion must be established from STATUS.json and the final
180-comparison check, not from this preparation entry.


### Missing candidate VCF cell context (read-only follow-up)

Of 4,866 model cells without common-support VCF means, 1,712 have both
LC_Type1=17 and LW=1 at their centers in all four snapshots; 57 have both
land classifications throughout; 3,097 have changing or disagreeing flags.
All flags are known, but agreement is not proof of whole-cell water extent.
There are 3,984 cells with zero annual usable coverage in every snapshot;
9 have some annual usable coverage in every snapshot but no common native
support across all years. Missing common means cannot be equated with water.

These findings do not authorize replacing missing vegetation by zero,
permanent old-value fallback, or blanket barriers. No solver or GIS edits
were performed. Evidence:
`C:\cheetah\reports\vcf_missing_cell_context_20260903_161406_032093.json`.


- [MCD12Q1.061 bands and class legends](https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MCD12Q1)
- [MOD44B.061 VCF bands and quality fields](https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD44B)

These sources establish product definitions, not provenance of the local
exports. The literature already logged in
`C:\cheetah\github_repo\outputs\methodology_comparison_temporal_resistance.md`
supports sensitivity testing, not the exact numerical weights or a universal
bare-cover response.
