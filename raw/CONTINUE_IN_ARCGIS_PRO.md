# Continue the Cheetah workflow in ArcGIS Pro

## 1. Finish roads now

Run `finalize_road_density_and_distance.py` again after the Euclidean Distance fix.

Expected outputs: `roaddens_1km`, `dist_road_major_1km`, and
`dist_road_minor_1km`. Keep `roaddens_10km_1km` as the sensitivity option.

## 2. Water (Step 09.4)

Download HydroRIVERS and a permanent-water polygon layer. Project/clip both to
`extent_buffered`; use **Euclidean Distance** with `cell_size = snapgrid_1km`
and environments `snapRaster = snapgrid_1km`, `mask = extent_buffered`.
Output: `dist_water_1km`. Treat it as a resource/context variable unless a
specific river/barrier mechanism is justified.

## 3. Terrain (Step 09.5)

Download SRTM/DEM. Project and aggregate to the 1 km grid. Run **Slope** to
produce `slope_1km`. Run **Focal Statistics**, statistic `RANGE`, on the DEM
using a documented neighborhood to produce `rugged_1km`. Record the
aggregation and neighborhood settings.

## 4. Livestock (Step 09.6)

Download Gridded Livestock of the World v4 for the relevant species/combined
exposure measure. Project, clip, and resample to snap grid. Output:
`livestock_1km`. Describe it as static exposure, not conflict.

## 5. Veterinary fences (Step 10)

Acquire a vector source from veterinary agencies/AHEAD-WCS material; use OSM
only as a last-resort contingency. Project and clip; rasterize on snap grid.
Output: `fence_resist_1km`. Preserve both a no-fence and fence scenario if the
source is uncertain.

## 6. Evidence surfaces (Step 11)

Use the baseline observation CSV. Make: `evid_density_1km` (Kernel Density),
`evid_age_10km` (latest record year by grid cell), and `evid_sources.csv`
(source composition by 10 km grid). These are monitoring context, not
resistance covariates.

## 7. Range cores (Step 12)

From the baseline distribution raster, create three binary definitions:
C1 confirmed only, C2 confirmed + likely, C3 confirmed + likely + possible.
Run Region Group with **EIGHT** neighbors. Apply minimum patch sizes:
C1 2000 cells/km2; C2 1000; C3 500. Convert retained patches to polygons
without simplification. Outputs: `cores_c1`, `cores_c2`, `cores_c3`.
Record and freeze the core definitions before connectivity runs.

## 8. Resistance specification (Step 13)

Create `resistance_spec.csv` before making surfaces. It needs six scenarios
(RES-01 habitat, RES-02 human pressure, RES-03 livestock, RES-04 balanced,
RES-05 low contrast, RES-06 composite) x four years. For every covariate,
record function, range/weight, source or explicit scenario assumption. Freeze
it and tag the commit before Step 15.

## 9. Pressure overlap check (Step 14)

Composite Bands: built, flare-masked lights, `roaddens_1km`, livestock. Run
**Band Collection Statistics** with covariance/correlation. Save
`pressure_corr.txt` and report it as a robustness check, not regression.

## 10. Resistance surfaces (Step 15)

Rescale every included input to a common scale (for example 1--100) using the
function in `resistance_spec.csv`. Build a scripted weighted sum for each
scenario x year. Required output names: `res01_2012_1km` through
`res06_2024_1km` (24 rasters). QC min/max, NoData, and visual differences.

## 11. Connectivity analysis (Step 16)

First make a pilot region. Use **Distance Accumulation** with cores as source
and one resistance surface as cost; time it. Then use **Optimal Region
Connections** with cores and resistance. Export its connectivity table. Only
after the pilot completes cleanly, loop across scenarios, years, and core
definitions to make effective-distance tables.

## ArcGIS environment for every raster operation

Set: processing coordinate system = Africa Albers; snap raster = `snapgrid_1km`;
cell size = `snapgrid_1km`; extent/mask = `extent_buffered`; resampling =
Bilinear for continuous and Majority/Nearest for categorical. Do not overwrite
raw input files.
