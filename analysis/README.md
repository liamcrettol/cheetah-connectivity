# Analysis archive

This directory is the reproducible archive of the ArcGIS Pro and Circuitscape
work completed for the southern African cheetah structural-connectivity study.

## Contents

- `scripts/` — copied analysis, QA, figure, and ArcGIS Pro automation scripts.
- `reports/` — CSV, JSON, Markdown, and log outputs copied from `C:\cheetah\reports`.
- `figures/` — generated publication and diagnostic figures.
- `../tex/figures/` — the four publication PNG/PDF figures used by the manuscript.

## Important status notes

- The final historical model is the vegetation-balanced resistance surface with
  documented finite fence treatment, evaluated for 2012, 2016, 2020, and 2024.
- Historical current-flow outputs are structural-flow evidence, not cheetah
  occurrence probabilities or validated corridors.
- The 2030 products are scenario-based prospective permeability stress tests,
  not calibrated forecasts. `low_growth` is anchored to the verified 2024
  surface; continuation and high-development project only the documented
  dynamic built-up and VCF components.
- The 2030 path run is resumable. The copied `future2030_paths_*.csv` files
  reflect the run state at archive time; verify that all three scenarios report
  45/45 successful links before treating the comparison as complete.
- The cheetah observation table contains assessment years (mostly 2010–2016)
  but the published density raster is pooled/static. The temporal consistency
  audit is exploratory and is not independent validation.

The ArcGIS project, geodatabases, raw rasters, Circuitscape binaries, and local
backup APRX files are intentionally not copied into this Git archive.
