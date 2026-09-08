# Final model and current-flow handoff — 8 September 2026

## Status at handoff

The **final pairwise Circuitscape current-flow run is in progress**. Do not
describe final current-flow results, maps, rankings, or conservation priorities
as complete until the job has finished and its output QC has passed.

The final resistance surfaces were successfully built in ArcGIS Pro on 8
September 2026. They are separate from the earlier reference current-flow
model, which used anthropogenic pressure plus terrain only and is retained for
comparison, not final reporting.

## Final resistance specification

For each year (2012, 2016, 2020, 2024), the final input is:

```
resistance_final_balanced_fence_documented_YEAR
  = resistance_temporal_veg_balanced_YEAR
    x fence_multiplier_main_kruger_documented_1km
```

The temporal vegetation-balanced surface is the weighted sum of:

| Component | Weight | Notes |
| --- | ---: | --- |
| Anthropogenic pressure | 0.60 | Built-up, roads, livestock index, and flare-masked VIIRS lights; lights have the smallest pressure sub-weight (0.10). |
| Vegetation structure | 0.20 | A sparse/bare-cover proxy derived from VCF tree, non-tree, and bare fractions. |
| Terrain | 0.20 | Mean slope transformed to 1–10 resistance. |

The fence multiplier is finite/crossable. It combines KAZA and documented
Kruger fence cells with a cell-wise maximum, so overlapping fence sources are
not penalized twice. It is an explicit scenario assumption, not an empirical
cheetah-permeability estimate.

## VCF zero and water-context decision

All-zero VCF triplets are **not** treated as terrestrial bare ground, permanent
water barriers, or NoData. In the existing VCF formula an all-zero triplet has
a finite midpoint vegetation score of 5.5/10. The 8 September audit found:

| Persistent all-zero VCF triplets | Cells |
| --- | ---: |
| Total | 174,975 |
| Persistent water-class context | 169,283 (96.7%) |
| Persistent land-class context | 0 |
| Persistent unresolved/mixed context | 5,692 |

This supports describing the cells as **water-context uncertainty**, especially
around the seasonally dynamic Makgadikgadi pan system. It does not establish
that a cheetah cannot cross a 1-km cell, and annual land cover is not measured
inundation. The baseline therefore retains finite values and does not impose a
static water barrier. A future analysis may use time-resolved inundation to
test a finite seasonal-water sensitivity; that would be supplementary, not a
retroactive claim about the present baseline.

Relevant literature and cautions are in `makgadikgadi_missing_vcf_evidence.md`.

## Completed checks and sensitivity evidence

- Fixed historical core baseline: **23 cores**.
- Selected least-cost-path network: **45 neighbouring core pairs** across four
  snapshots.
- Vegetation sensitivity comparison: **180/180 pair-year comparisons**
  verified; median absolute optimized-cost difference **0.2213%**, maximum
  **1.9625%**, and no 2012–2024 endpoint temporal sign reversals.
- Route geometry is less stable than route cost: **49/180** route-years fell
  below the descriptive 80% minimum directional overlap review trigger. This
  is not a biological threshold and should be reported as spatial uncertainty,
  not a priority exclusion rule.
- Final full-model preflight passed formula, grid, core-coverage, and fence
  overlap checks for all four years and three vegetation weights.
- Earlier reference Circuitscape current flow completed **253/253 core pairs
  per year**, but it was pressure+terrain only, with no VCF vegetation or fence
  penalties. Do not present it as the final model.

## Current job

The running job is pairwise Circuitscape current flow on the final surfaces:

- 23 fixed focal regions;
- 253 undirected core pairs per year;
- 4 years = **1,012 pairwise solves**;
- 8-neighbour raster connectivity; CG+AMG solver; double precision;
- output folder:
  `C:\cheetah\circuitscape\outputs\final_balanced_fence_documented`.

The job is expected to create cumulative current rasters and logs for each
year. A year finishing is not by itself sufficient for paper claims: verify
that all 253 pairs completed, grids align, current normalization is consistent
across years, and map outputs preserve NoData outside valid model support.

## Reproducibility artefacts created locally

These are intentionally not committed because they depend on the large local
ArcGIS dataset and Circuitscape installation:

- `outputs/build_final_balanced_fence_resistance.py`
- `outputs/prepare_final_pairwise_circuitscape_inputs.py`
- `outputs/run_final_pairwise_current_flow.jl`
- `outputs/run_final_pairwise_current_flow.ps1`
- `C:\cheetah\reports\vcf_zero_triplet_context_20260908_080240.{csv,json}`
- `C:\cheetah\reports\final_balanced_fence_resistance_register_20260908_080959.{csv,json}`

The ArcGIS build reported four successful final surfaces and a project backup:
`C:\cheetah\backups\Resistance_before_final_balanced_fence_20260908_080726.aprx`.

## Paper claim boundary

Use: “temporally comparative, scenario-based **structural connectivity** among
fixed cheetah cores.”

Do not use: “observed corridors,” “validated dispersal routes,” “permanent
water barriers,” or empirically calibrated fence permeability. Conservation
recommendations must await the final current-flow QC and remain decision
support, not proof of realized movement or intervention success.
