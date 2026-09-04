# Candidate mask-preserving VCF exports

Prepared 3 September 2026. User executed the export; four downloads passed the
local structural/input checks on 3 September. Not yet adopted as production inputs.

Results: `C:\cheetah\reports\vcf_v2_input_impact_20260903_154132_775857.json`
and matching `.md`. Exact grid, band order, NoData declarations, coverage accounting,
cross-year common support and component ranges passed. See the full input audit
for findings and remaining water/missing-data and route-stability decisions.

Runtime correction: Earth Engine `Projection.transform()` returns a WKT string,
not an array of affine coefficients. The native-grid guard now compares CRS
and nonempty transform strings exactly and rejects incomplete metadata. The
guard was locally tested for matching strings, changed grids, wrong dates,
missing records and malformed transforms. The subsequent Earth Engine export completed.

Script: `export_gee_vcf_maskpreserved_v2.js`. Run in Earth Engine Code Editor.
Four new GeoTIFF tasks, one per year, named `vcf_maskpreserved_common_v2_YEAR`.
Download completed files from `cheetah_gee_exports` into Downloads.

## Explicit choices

- Source is MODIS/061/MOD44B for calendar years 2012, 2016, 2020 and 2024.
  Require exactly one annual image and matching native grids before creating tasks.
- Preserve masks on all three cover bands. A usable native pixel has all three
  bands available, each within 0..100, and is not an all-zero triplet. Individual
  valid zero components are retained. Values are not clamped or renormalized.
- Compute a native-pixel intersection across the four years, before aggregation.
  Mean cover for each year uses that same native spatial support. This avoids
  attributing changes in contributing native locations to vegetation change.
  This is a project-specific temporal comparability choice, not a universally
  mandated ecological method or a claim that missing land is impassable.
- Overlap-weighted means use Earth Engine `reduceResolution(mean)` to the verified
  Africa Albers grid. `bestEffort` is false; no silent coarser source level.
- Export common and annual usable coverage separately. Native zero/out-of-range
  exclusions and original source-mask validity also have separate fractions.
  These refer to the whole target cell; cover means refer only to common usable
  native area. A partly water-covered cell's land-only vegetation mean is not a
  measurement of vegetation over its entire area.
- No cloud/quality-bit cutoff, minimum usable-area threshold, water exclusion,
  fence penalty or resistance transform is imposed here. Mask validity does not
  guarantee source accuracy. Missing ancillary Quality/Cloud values alone do not
  discard otherwise available cover.
- Fill -9999 only after aggregation on the target grid, and declare it as TIFF
  NoData. Coverage zero remains numeric zero; missing mean cover remains NoData.
- Use the existing model affine transform and a 1 cm inward region inset to
  avoid the previous extra-border-row export issue. Verify dimensions after
  download; this has not been authenticated against Earth Engine yet.

## Band order (all Float32)

1. `tree_pct_common_mean`
2. `nontree_pct_common_mean`
3. `bare_pct_common_mean`
4. `common_usable_fraction`
5. `annual_usable_fraction`
6. `annual_source_valid_fraction`
7. `annual_zero_triplet_fraction`
8. `annual_out_of_range_fraction`

## Acceptance checks after download

Verify exact 2310 x 2200 grid, projection, affine transform, band names, sentinel,
range 0..100 for cover, 0..1 for coverage. Common coverage must match across years
and not exceed annual usable coverage. Annual usable coverage must not exceed
original source-valid coverage. Common cover must be missing where common coverage
is zero. Check the sum of the three cover means without assuming an exact sum
of 100, since source components may be rounded.

Quantify partial-coverage cells within the existing model, especially near cores,
water and narrow connections. Choose/document water treatment separately from
missing-data handling. Check core retention and pair connectivity before any
production rerun. Do not silently replace old inputs or present changed results
as a weights-only sensitivity test: this also changes aggregation/support.

Existing maps, reference runs, LCP results and source files remain unchanged.

## Technical sources checked

- [Google's aggregation and pixel weighting guidance](https://developers.google.com/earth-engine/guides/resample)
- [reduceResolution API](https://developers.google.com/earth-engine/apidocs/ee-image-reduceresolution)
- [MOD44B.061 product bands](https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD44B)

These sources justify the documented API behavior and product definitions, not
cheetah-specific vegetation response weights or a validated barrier rule.
