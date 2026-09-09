# resistances

Reanalysis and diagnostic work arising from the September 2026 evidence audits.
Separate from `analysis/`, which is the archive of the original production run.
Nothing here overwrites a production raster or geodatabase; every script is
read-only against the model outputs and writes to `C:\cheetah\reports`, with
copies landing in `reports/` and `figures/` here.

## Why this exists

Two audits on 9 September found that several current-derived results describe
the fixed core footprint rather than the connecting landscape. Every cell in the
top 10%, 5% and 1% of positive modelled current lies inside an input core, in all
four snapshot years. The mechanism is the pairwise source/ground design: each of
the 23 focal regions participates in 22 of the 253 pairs, and 22/253 = 0.08696
against a reported 90th-percentile current of 0.08702, so core cells sit on a
plateau created by focal-node current injection. The cores also cover 246,654 of
2,503,870 valid model cells, which is 9.85%, slightly more than a top decile.

The Circuitscape solves are fine. This is an output-domain and interpretation
problem. `set_focal_node_currents_to_zero` is documented as not implemented in
Circuitscape 5 (installed 5.17.1), so the repair is post-hoc domain masking with
the changed domain reported, not a config change and not a re-solve.

## Contents

    scripts/    reanalysis scripts, read-only against model outputs
    reports/    CSV and JSON results
    figures/    figures generated here

### `scripts/recompute_outside_core_current_context.py`

Recomputes protected-area coverage and temporal persistence on the domain of
valid model cells outside input cores carrying positive modelled current.
Produces a coverage-versus-percentile curve for all four years, core-exclusion
buffer sensitivity at 0/1/5/10 km, a block-based spatial null, and top-decile
Jaccard overlap between years.

Run with the ArcGIS Pro conda environment, which supplies GDAL with the
OpenFileGDB raster driver:

    "C:\Users\lcrettol\AppData\Local\ESRI\conda\envs\arcgispro-py3-network\python.exe" scripts\recompute_outside_core_current_context.py

`arcpy` itself is not needed and currently does not import in that environment
(binaries at 3.6 against Pro 3.7). `gdal_array` is also broken there against
numpy 2.2, so rasters are read through `band.ReadRaster` into a numpy buffer
rather than `ReadAsArray`.

## Results so far

Matched background, meaning protected-area coverage across the outside-core
positive-current domain the selection is drawn from: **31.26%**.

An earlier audit used 30.13%, which is coverage across all outside-core cells
including 165,765 with zero current. Those cells can never be selected, so the
matched figure is the right comparison and the gap is slightly wider than first
reported.

| Percentile of current | 2012 | 2024 |
|---|---:|---:|
| 50th | 27.52% | 27.09% |
| 80th (minimum) | 24.23% | 23.27% |
| 90th | 26.31% | 25.54% |
| 95th | 35.57% | 33.45% |
| 99th | 44.17% | 44.63% |

Three things follow.

**Coverage is lowest in the middle of the distribution, not at the top.** The
minimum sits at the 80th percentile in every year, 7 to 8 points below
background. The moderately-high-current connecting landscape is the least
protected part of the model domain.

**Coverage crosses background at about the 93rd percentile** and rises steeply
above it, reaching roughly 44% at the 99th. The most concentrated flow is inside
parks; the broad connecting landscape is not.

**The gap widened over the study period**, from -7.03 points at the 80th
percentile in 2012 to -7.99 in 2024, and from -4.95 to -5.72 at the 90th. The
source-inclusive analysis could not show this because the core plateau dominated
the upper tail.

Direction is stable under 0, 1, 5 and 10 km core-exclusion buffers, and the gap
widens slightly as the buffer grows. Outside-core top-decile geography is stable
across years, Jaccard 0.912 to 0.927.

### On significance

Do not lean on a p-value here. Under a block null preserving clumping at 25 km,
the top-decile under-protection gives a one-sided p of 0.006; at 50 km blocks it
is 0.096. The 99th-percentile over-protection gives 0.040 and 0.112 at the same
two scales. The apparent significance is largely a function of the assumed
autocorrelation scale, which is exactly what the original uniform hypergeometric
null concealed by returning 0.001 everywhere.

A toroidal-shift null was tried first and abandoned. The domain is irregular and
covers only 41% of the grid, so rigid shifts pushed most of the selection
off-domain, median retention 46% of the observed cell count, and the resulting
interval spanned almost the whole range.

The defensible reporting is the descriptive comparison against the matched
background, with the direction shown to be robust across years and buffers, and
the scale dependence of any formal test stated plainly.

## Figures

`scripts/build_outside_core_figures.py` rebuilds the current-derived figures on
the outside-core domain and replaces the straight-line link figure with real
least-cost geometry.

| Figure | Replaces | What changed |
|---|---|---|
| fig1, current outside cores 2024 | Figure 1, high-current concentration | Core plateau removed, cores drawn as outlines, classed by percentile of outside-core current |
| fig2, current change 2012 to 2024 | Figure 2, temporal current evidence | The old one was near-uniform because it was showing fixed core geometry. This shows real regional structure |
| fig3, priority links as least-cost paths | Figure 3, robust priority links | The old figure drew `final_priority_core_links_paper`, which has exactly two vertices per feature, i.e. straight centroid-to-centroid lines. This draws `conservation_priority_paths_temporal`, the actual modelled routes |
| coverage curve | Figure 4, protected-area context | Replaced by the percentile curve above |

All four now carry a legend, a scale bar, the analysis-domain boundary and a
consistent palette. Protected areas are clipped to the analysis domain, because
the WDPA raster spans the whole grid and drawing designations the model never
evaluated implies a coverage claim outside the study extent.

There is deliberately no north arrow. Across a 2,310 km extent in Africa Albers
Equal Area Conic, grid north and true north diverge visibly away from the
central meridian, so one arrow would be wrong over most of the map. A graticule
is drawn instead.

### On the change figure

It reports percent change, not absolute. Absolute change is on the order of
7e-6 against a median current of 2.8e-4, which is unreadable. Median relative
change is 4.3% and the 90th percentile 10.7%.

That is comfortably above solver noise, so the fine texture is signal. The run
used double precision with CG-accelerated AMG; a default relative tolerance
would put convergence error around 1e-10 in absolute terms, four orders below
the changes being mapped.

Percent change is not inflated at low baseline current, which was the obvious
thing to suspect. Binned by 2012 baseline decile, the share of cells changing by
more than 20% is 0.1 to 0.6% in every band and the 95th percentile of absolute
change sits near 12% throughout. The green western strip is therefore real in
the model rather than a small-denominator artefact. It is still not a
conservation signal, because absolute flow there is negligible; read it against
figure 1.

## Also worth knowing

The Circuitscape logs record that the resistance graph has **34 connected
components**, and per-pair node counts vary from 2,500,425 to 2,502,163 out of
2,503,870. All core pairs returned finite effective resistance, so the pairs
themselves sit in the main component, but the fragmentation is undocumented
elsewhere and should be stated in Methods.

## Limits

Post-hoc masking removes the core plateau from the reported statistics. It does
not remove focal-region influence from the underlying solve. The block null is
not habitat-matched and none of this is a causal test. Protected-area coverage
is legal designation, not management effectiveness.
