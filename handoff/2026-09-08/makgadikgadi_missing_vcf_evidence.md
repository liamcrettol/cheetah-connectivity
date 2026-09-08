# Makgadikgadi missing-VCF cells: evidence memo

**Status: evidence review completed; final production policy is pending the
analyst's explicit approval.** This memo is deliberately separate from the
model specification so that a map-display diagnosis cannot silently become a
resistance-model assumption.

## What the diagnostic shows

The 1-km common VCF-support mask contains 4,866 cells without common VCF
support across the historical snapshots. Area-fraction diagnostics derived from
MCD12Q1 classify:

| Context across all four snapshots | Cells |
| --- | ---: |
| Both land-cover schemes identify >=95% water | 715 |
| Both land-cover schemes identify >=95% land | 14 |
| Mixed, temporally variable, or disagreeing | 4,137 |

These are *classified-area fractions*, not direct measurements of inundation or
of whether a cheetah could cross a cell. Both land-cover schemes derive from the
same MODIS MCD12Q1 product, so their agreement is useful internal evidence but
is not independent validation.

The resulting map shows the largest concentration around the Makgadikgadi Pans
system in northeastern Botswana. It is an uncertainty map, not a map of known
impassable water.

## What the literature supports

1. **Makgadikgadi is seasonal and dynamic.** Wildlife and carnivore studies
   describe it as a seasonal wetland, with ephemeral pans, rainfall-dependent
   movement, and the Boteti River providing critical dry-season water. The
   landscape also supports seasonal zebra and wildebeest migrations.
2. **This supports a time-varying interpretation, not a static barrier.** The
   relevant Botswana evidence documents seasonal wildlife dynamics, but it does
   not demonstrate that cheetahs categorically avoid or cannot cross each
   1-km pan/floodplain cell.
3. **Flooded-landscape connectivity studies use flood-state information when
   they assign flood resistance.** The analogous Okavango lion study modelled
   monthly flood conditions and treated flood effects as temporal. An annual
   categorical water label is not a substitute for that evidence.

## Recommended model treatment

Keep the production historical resistance surface unchanged for this issue and
retain the cells as a documented **data-uncertainty layer**. Do not:

- convert every missing-VCF cell to NoData;
- convert all 715 water-context cells into permanent barriers; or
- use the MCD12Q1 fraction as a proxy for fractional inundation.

This is conservative in both directions: a NoData mask would manufacture
barriers, while a permanent water penalty would overstate a dynamic pan system.
The completed least-cost-path diagnostics already show that no saved route
touches the fallback cells, so this decision does not alter the reported LCP
comparison. It must nevertheless remain visible as an uncertainty limitation
for current-flow and future scenario work.

## Planned sensitivity (only if a suitable temporal inundation data set is
available)

Do a separate seasonal-water sensitivity analysis, never a replacement of the
historical baseline. The input must be a time-resolved flood/inundation product
whose dates match the connectivity question. Compare the baseline with a
finite, explicitly justified flood-resistance scenario and report any changes
as sensitivity results. Do not use a binary permanent-barrier scenario as the
main conservation-priority map.

## Sources

- Winterbach, H. E. K., Winterbach, C. W., Somers, M. J. & Hayward, M. W.
  (2015). *Relative availability of natural prey versus livestock predicts
  landscape suitability for cheetahs Acinonyx jubatus in Botswana.* PeerJ 3,
  e972. https://pmc.ncbi.nlm.nih.gov/articles/PMC4512768/
- Winterbach, H. E. K., et al. (2013). *Landscape suitability in Botswana for
  the conservation of its six large African carnivores.* PLOS ONE 8(6),
  e66825. https://doi.org/10.1371/journal.pone.0100202
- Bartlam-Brooks, H. L. A., Bonyongo, M. C. & Harris, S. (2011). *Will
  reconnecting ecosystems allow long-distance mammal migrations to resume? A
  case study of a zebra Equus burchelli migration in Botswana.* Oryx 45,
  210-216. https://doi.org/10.1017/S0030605310000414
- Ebigbo, N. O., Henschel, P., van der Meer, E. & Braczkowski, A. R. (2026).
  *Temporal effects of flooding regimes on lion population core habitat and
  connectivity across a seasonally flooded landscape, the Okavango Delta.*
  Frontiers in Ecology and Evolution 14, 1638706.
  https://doi.org/10.3389/fevo.2026.1638706

## Wording boundary for the paper

Say that cells were *flagged as water-context or mixed-context uncertainty*.
Do not call them water barriers, and do not claim direct cheetah avoidance
without cheetah movement data that evaluates that claim.
