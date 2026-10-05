# Paper figure and table production plan

Updated 2026-09-02 after pulling `main` (`d3f581b`). This plan reconciles the manuscript scaffold with the analyses currently completed in ArcGIS Pro. It is a production plan, not a claim that every result is already available.

## Recommended main-text set

| Item | Decision | What it should show | Current status | Production dependency |
|---|---|---|---|---|
| Figure 1: temporal change | Keep, revise caption | Maps of absolute change in modelled effective distance/current-flow proxy for 2012–2016, 2016–2020, 2020–2024, and 2012–2024, with a common scale and an uncertainty panel or hatching | Not ready; temporal primary resistance surfaces exist and the 45-link temporal path run is in progress | Finish temporal LCP run, summarize per-cell/per-link change, then map only outputs supported by the chosen connectivity method. Do not call a surface “current flow” unless Circuitscape current has actually been run. |
| Figure 2: robust pinch points | Revise terminology | Robust candidate connectivity links/locations, with protected-area status shown as context | Partly ready: 32 primary-priority eligible links and 13 uncertainty/data-collection links; edge-betweenness ranking exists | Add protected-area overlay and a reproducible spatial aggregation. Use “robust candidate links” unless a high-current convergence analysis creates defensible pinch-point cells. |
| Figure 3: ensemble agreement | Keep, expand | Agreement across resistance scenarios, core definitions, resolutions, and snapshots; low-agreement areas clearly marked as uncertainty | Partly ready: 90 weight comparisons, 34 robust and 11 sensitive comparisons; link-level robustness exists, but no raster agreement surface | Run/aggregate the full predeclared sensitivity grid and create an agreement raster or link map. Keep this figure central because uncertainty is a substantive result. |
| Figure 4: monitoring priorities | Revise | Ranked robust links with component scores and uncertainty flags; optionally add cells only if cell-level current output is available | Not ready as drafted; link-level betweenness and priority worksheet exist, but no defensible cell-level monitoring index yet | Build the priority index from robust link importance, change, protection gap, and data uncertainty. If cell scores are not produced, rename to “Ranked monitoring links.” |
| Table 1: covariates | Keep | Layer, native resolution, years, dynamic/static treatment, role in resistance | Ready to assemble from the protocol and completed data inventory | Generate from `protocol/temporal_alignment.csv` plus the final resistance-scenario register. Explicitly state that categorical land cover supplies context/masking, not an independent temporal resistance penalty. |
| Table 2: top 20 robust pinch points | Revise | Top 20 robust candidate links: link ID, endpoint cores, importance score, robustness, country, PA context, fence sensitivity | Partly ready; top-link betweenness and 32 eligible links exist, but PA and final temporal fields are pending | Replace “pinch points” with “candidate links” unless current-flow cells are available. Populate from `conservation_link_importance_betweenness.csv`, `conservation_priority_worksheet.csv`, fence-sensitivity outputs, and PA overlay. |
| Table 3: protected-area coverage | Keep, but defer | Observed high-current/high-priority area outside protected areas, null expectation, permutation distribution, effect size and uncertainty | Not ready; no completed current-flow/PA permutation result | Run the predeclared polygon-only PA overlap and 999 area-standardized permutations. Keep the null definition fixed before inspecting the result. |
| Table 4: monitoring priority ranking | Keep, revise title | Rank, robust link/cell ID, component scores, composite score, alternative-weight ranks, rank stability | Partly ready at link level; alternative weighting and robustness results exist | Use link-level table unless cell-level scores are explicitly created. Include alternative-weight results and Spearman/Kendall stability, not just one opaque composite. |

## Additions that strengthen the paper

1. **Fence-scenario sensitivity figure or table.** Five links were affected by the KAZA/Kruger fence scenarios. Show route-shift and effective-cost changes, while keeping the interpretation as a scenario/review trigger rather than a biological cutoff. These links should be discussed but excluded from the primary conservation-priority tier when the evidence is uncertain.
2. **Uncertainty/robustness table.** Report the 32 primary-priority eligible links and 13 uncertainty/data-collection links, including the rule used to classify them. This makes the decision-support framing auditable.
3. **Supplementary methods table.** Include resistance functions, fixed versus dynamic covariates, raster scale/alignment, and all alternative weight sets. This is especially important because roads, livestock, terrain, hydrography, and fences are static while built-up, lights, and VCF fields carry temporal signal.
4. **Temporal summary table.** Once the temporal path run finishes, report per-period and 2012–2024 changes by country and core pair, with absolute and proportional change separated. Proportional VCF outputs should remain supplementary because the QC flagged high ratios; absolute change is the safer primary temporal summary.

## Items to remove or postpone

- Do not publish a “ranked monitoring priority cells” figure if the workflow only produces link-level scores. Either create a true cell-level index or change the unit of analysis to links.
- Do not label candidate links as observed animal crossings, functional corridors, or biological pinch points. They are modelled structural priorities that require field verification.
- Do not make proportional VCF-change maps the primary result. The QC flagged high proportional change for most VCF change layers; use absolute change and describe proportional maps as supplementary context.
- Do not report current-flow language for Figure 1 or Figure 2 until a current-flow solver output exists. Least-cost/effective-distance outputs and Circuitscape current surfaces are not interchangeable.
- Do not treat categorical MODIS land-cover class changes as an independent temporal resistance driver; retain them for context/masking as already decided.

## Production sequence

1. Finish the current temporal primary-path run for all four snapshots.
2. Generate the temporal summary CSV (country × period × core pair) and absolute/proportional QC.
3. Finalize the link-level robustness and monitoring-priority tables, including alternative-weight rank stability.
4. Add the PA polygon overlay and run the predeclared 999-permutation test.
5. Decide whether a Circuitscape current-flow surface is required for the paper’s hypotheses. If yes, run it consistently across the declared sensitivity subset; otherwise revise captions and hypotheses to effective-distance/link connectivity.
6. Produce figures using common extent, projection, cell alignment, color scales, and explicit uncertainty overlays.
7. Populate `tex/sections/03_results.tex`, then update Methods/Discussion/Limitations so every reported number is traceable to a saved CSV or raster report.
8. Build the PDF and inspect every figure/table at print size before submission.

## Current manuscript mismatch to resolve

The protocol and manuscript currently promise “current flow,” “protected-area status,” “robust pinch points,” and “monitoring cells,” while the completed workflow currently supports strongest claims about temporally varying resistance, effective-distance/link connectivity, robustness across alternative weights/scenarios, and ranked candidate links. The safest publication path is to either complete the missing current-flow/PA/cell-level analyses or revise those terms before filling the Results section.
