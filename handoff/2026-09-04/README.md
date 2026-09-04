# Resume here: 4 September 2026

This is the current home/work handoff, not a replacement manuscript. It supersedes
the older "next action" instructions in the archived context documents and the
root CLAUDE.md wherever those describe earlier project stages.

## At work

In your Codespace or personal project checkout, run:

```sh
git pull --ff-only origin main
```

Read this file first, then [post-run decisions](context/VCF_POSTRUN_DECISIONS_20260904.md).
All relative links below work on GitHub. You can review the results and write your
own Methods/Results/limitations without ArcGIS or another solver run. Keep the
academic project separate from employer data and software licensing.

Your existing manuscript and bibliography were not edited for this handoff.
The uncommitted bibliography changes in the home checkout were left untouched.

## What is completed

- Balanced candidate VCF diagnostic: **180/180 pair-year comparisons**, 45 fixed
  pairs in 2012, 2016, 2020 and 2024; 84 source checkpoints. Completed September 3.
  Independent geometry/length/cost receipt review passed September 4.
- Median absolute optimized-cost difference: **0.2213%**; maximum **1.9625%**.
  None of the 45 endpoint-year temporal comparisons reversed sign. This does
  not imply the exact route locations are stable.
- **49/180** route-year comparisons have minimum directional 1 km overlap below
  80%; 29 pairs have at least one flagged year, including 21 of the 32 previously
  priority-eligible pairs. This is a review trigger, not a biological cutoff or
  automatic exclusion from conservation priorities.
- No candidate route uses fallback cells. Eight touch valid VCF cells with less
  than 95% common coverage. These are distinct checks.
- All four newly downloaded `water_class_fractions_v1_YEAR.tif` exports passed
  exact grid, CRS, 11-band order, [0,1] range and accounting checks.
- All **4,866** common missing-VCF cells were cross-tabulated for all four years.
  Using 95% only as a descriptive bin, 715 have at least 95% both-water classified
  area in every year, 14 at least 95% both-land, and 4,137 meet neither persistent
  criterion. These are area-based classifications, NOT the earlier cell-center
  counts, direct inundation measurements or an adopted masking policy.

## Open these results

| Purpose | File |
|---|---|
| Verified route/cost summary | [Review](reports/vcf_completed_review_20260904_074611_029018.md) |
| Pair-level review data | [CSV](reports/vcf_completed_review_20260904_074611_029018.csv) |
| All 180 diagnostic comparisons | [CSV](reports/comparisons.csv) |
| Endpoint-year temporal comparison | [JSON](reports/temporal_comparison.json) |
| Selected old/candidate map examples | [PNG](figures/vcf_review_examples_20260904.png) |
| Missing-VCF location/context | [PNG](figures/vcf_missing_cell_context_20260903_161626_656919_map.png) |
| New water-class checks | [Report](reports/water_fraction_download_qa_20260904_084317_357951.md), [full JSON](reports/water_fraction_download_qa_20260904_084317_357951.json), [cell-year CSV](reports/water_fraction_download_qa_20260904_084317_357951.csv) |
| Corrected centrality values | [CSV](reports/edge_normalization_audit_20260904_074907_825273.csv), [explanation](reports/edge_normalization_audit_20260904_074907_825273.md) |
| Earlier figure/table planning, reconcile before use | [Plan](context/paper_figure_table_plan.md) |
| Earlier methodological comparison | [Notes](context/methodology_comparison_temporal_resistance.md) |

The map examples were selected to illustrate discrepancies, not as an unbiased
sample; panel scales differ. The older missing-cell figure uses center classes,
whereas the new report uses native classified-area fractions.

## Reporting correction to carry forward

The old edge-betweenness calculation used the node-normalization denominator 231.
For 23 nodes, standard undirected edge normalization uses 253. All 45 values
are multiplied by **21/23**, with ties and ranks unchanged. Link 38-40 is
**0.4090909**, not 0.4480519. This was independently checked with NetworkX 3.6.
Production tables and the manuscript still need this correction propagated;
there is no need to rerun GIS for this arithmetic correction.

Source: [NetworkX edge betweenness](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.centrality.edge_betweenness_centrality.html).

## At home: next dependency, not another overnight launch

1. Review the new water-class fractions for the 4,866 missing cells, including
   their spatial context. Decide and document missing-land/water treatment from
   evidence. Do not blanket-mask VCF NoData or class-11 wetlands. LW and LC_Type1
   come from the same product and are not independent validation.
2. Determine which calculations the final policy actually changes. Raising costs
   only on cells unused by an existing optimal path cannot improve another path
   relative to it, under the same graph/endpoint conventions. This conditional
   result does not cover lowering costs, changing other cells, current flow or
   different weights. Do not infer blanket permission to reuse all outputs.
3. Keep candidate outputs separate until a production decision is documented.
   Then propagate centrality normalization, route geometry uncertainty and any
   resulting priority revisions consistently into tables, figures and Methods.
4. Reconcile the figure/table plan against the verified model actually used.
   Predictive extensions, corrected low/high sensitivity and final current-flow
   analysis remain separate work, not completed by the balanced diagnostic.

The completed Circuitscape reference model was 80% anthropogenic pressure and
20% terrain, without VCF or fence penalties. Do not present it as the final
vegetation-balanced conservation map. All results remain modeled structural
connectivity among fixed historical cores, not verified cheetah movement.

## Local data and reproducibility

This bundle contains scripts, report snapshots and figures, not a portable GIS
installation. ArcPy scripts retain the home paths and require the home working
geodatabase and licensed ArcGIS Python. Do not blindly launch the overnight worker.

- Main geodatabase: `C:\cheetah\gdb\cheetah_working.gdb`
- Completed diagnostic: `C:\cheetah\diagnostics\vcf_v2_balanced_overnight_v1`
- New water TIFFs: `C:\cheetah\raw\source_qa\water_class_fractions_v1_20260904`
- Original download: `C:\Users\lcrettol\Downloads\drive-download-20260904T143515Z-1-001.zip`
- Original scripts: `C:\Users\lcrettol\Documents\Codex\2026-08-25\i-am-working-on-this-spreadsheet\outputs`

Input SHA-256 receipts are retained in the JSON reports and diagnostic manifest.
The four water TIFFs, geodatabases, project backups and credentials were deliberately
not added to GitHub. The scripts folder includes the sibling helper modules needed
by the recent diagnostic/review scripts. No production rasters, paths or project
layers were changed in preparing this handoff.

Live project memory: [Cheetah Execution Guide](https://docs.google.com/spreadsheets/d/1w6-QUxsCIAG7mq-7VY0Uws2BAo3irKzT2nqesRZu4Z8/edit),
especially Next Up and Decision Log. Earlier plans in the sheet are historical;
the September 4 entries distinguish completed evidence from pending work.
The Dashboard note, Next Up queue and Decision Log entries D30-D35 were updated
and read back successfully. A [cell-value snapshot](context/spreadsheet_snapshot_20260904.json)
preserves all 35 logged decisions and the current queue for offline reference.
