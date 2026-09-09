# Water-class export QA

All four exports passed exact grid, band-order, fraction-bound and accounting checks.

The 4,866 common missing-VCF cells were cross-tabulated in every year.

- missing_cells: 4,866
- both_water_ge_095_all_years: 715
- both_land_ge_095_all_years: 14
- other_cells: 4,137

## Required caveats

- 0.95 is a descriptive bin, not an adopted exclusion threshold.
- Fractions are native classified-area fractions, not direct inundation measurements.
- LW and LC_Type1 are from the same product, not independent validation.
- No imputation, production edit, resistance transformation or solver was run.
