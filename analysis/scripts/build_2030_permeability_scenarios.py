"""Build transparent 2030 land-permeability stress-test surfaces.

These are not forecasts of cheetah locations, movement, range change, roads,
livestock, or future management.  The 23 historical cores, terrain, roads,
livestock, documented fence multiplier, and 2024 flare-masked lights remain
fixed.  Only built-up and VCF composition are projected from the 2012--2024
linear change signal.  The output is a bounded scenario ensemble for comparing
the same 45 core-pair links under alternative 2030 land-pressure futures.
"""
from datetime import datetime
from pathlib import Path
import csv
import json
import os

import arcpy
from arcpy.sa import Con, ExtractByMask, Raster

GDB = r"C:\cheetah\gdb\cheetah_working.gdb"
SOURCE_GDB = r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah_connectivity.gdb"
GEE_EXPORTS = r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah\rasters\gee_exports"
REPORTS = Path(r"C:\cheetah\reports")
BACKUPS = Path(r"C:\cheetah\backups")
CORES = os.path.join(GDB, "cheetah_core_primary_density051_min500_1km")
FENCE = os.path.join(GDB, "fence_multiplier_main_kruger_documented_1km")
FINAL_2024 = os.path.join(GDB, "resistance_final_balanced_fence_documented_2024")
SCENARIOS = {
    "low_growth": 0.0,
    "continuation": 0.5,
    "high_development": 1.0,
}


def locate(name, allow_tif=False):
    for candidate in (os.path.join(GDB, name), os.path.join(SOURCE_GDB, name)):
        if arcpy.Exists(candidate):
            return candidate
    if allow_tif:
        candidate = os.path.join(GEE_EXPORTS, name + ".tif")
        if arcpy.Exists(candidate):
            return candidate
    searched = f"{GDB}, {SOURCE_GDB}" + (f", and {GEE_EXPORTS}" if allow_tif else "")
    raise FileNotFoundError(f"Missing {name}: searched {searched}")


def signature(dataset):
    raster = arcpy.Raster(dataset)
    extent = raster.extent
    return (int(raster.width), int(raster.height), float(raster.meanCellWidth), float(raster.meanCellHeight),
            float(extent.XMin), float(extent.YMin), float(extent.XMax), float(extent.YMax),
            int(raster.spatialReference.factoryCode or 0))


def prop(dataset, property_name):
    try:
        return float(arcpy.management.GetRasterProperties(dataset, property_name).getOutput(0))
    except Exception:
        arcpy.management.CalculateStatistics(dataset, 1, 1, [], "OVERWRITE")
        return float(arcpy.management.GetRasterProperties(dataset, property_name).getOutput(0))


def clamp(raw, low, high):
    return Con(raw < low, low, Con(raw > high, high, raw))


def scale_1_10(raw, low, high):
    if high <= low:
        return Raster(raw) * 0 + 1
    bounded = clamp(Raster(raw), low, high)
    return ((bounded - low) / (high - low) * 9) + 1


def bounded_percent(raw):
    return clamp(raw, 0, 100)


def vegetation(tree, nontree, bare):
    return 1 + 0.045 * (Raster(bare) + 100 - Con((Raster(tree) + Raster(nontree)) > 100, 100, Raster(tree) + Raster(nontree)))


def delete_if_exists(dataset):
    if arcpy.Exists(dataset):
        arcpy.management.Delete(dataset)


def align_2012_built(source):
    """Create a one-time bilinear 2012 copy on the final 2024 lattice."""
    output = os.path.join(GDB, "built_2012_future2030_aligned_1km")
    if arcpy.Exists(output) and signature(output) == signature(FINAL_2024):
        return output
    temporary = os.path.join(GDB, "_built_2012_future2030_projected_tmp")
    delete_if_exists(temporary)
    delete_if_exists(output)
    arcpy.management.ProjectRaster(
        source, temporary, arcpy.Describe(FINAL_2024).spatialReference, "BILINEAR", "1000 1000"
    )
    ExtractByMask(temporary, FINAL_2024, "INSIDE").save(output)
    delete_if_exists(temporary)
    arcpy.management.CalculateStatistics(output, 1, 1, [], "OVERWRITE")
    if signature(output) != signature(FINAL_2024):
        raise RuntimeError("2012 built-up alignment failed to reproduce the final model grid")
    print("created aligned 2012 built-up source:", output)
    return output


def main():
    arcpy.CheckOutExtension("Spatial")
    arcpy.env.overwriteOutput = True
    required = {
        "built_2012_raw": locate("built_2012_1km", allow_tif=True), "built_2024": locate("built_2024_aligned_1km"),
        "lights_2024": locate("lights_2024_1km_flaremasked"),
        "tree_2012": locate("vcf_tree_2012_aligned_1km"), "tree_2024": locate("vcf_tree_2024_aligned_1km"),
        "nontree_2012": locate("vcf_nontree_2012_aligned_1km"), "nontree_2024": locate("vcf_nontree_2024_aligned_1km"),
        "bare_2012": locate("vcf_bare_2012_aligned_1km"), "bare_2024": locate("vcf_bare_2024_aligned_1km"),
        "roads": locate("pressure_roads_1_10"), "livestock": locate("pressure_livestock_index_1_10"),
        "terrain": locate("terrain_resistance_1_10"), "fence": FENCE, "final_2024": FINAL_2024,
    }
    for label, dataset in required.items():
        if not arcpy.Exists(dataset):
            raise FileNotFoundError(f"Missing required {label}: {dataset}")
    if not arcpy.Exists(CORES):
        raise FileNotFoundError(CORES)
    reference = signature(FINAL_2024)
    # The historical 2012 built GeoTIFF uses the original lattice. It is aligned
    # below with the same bilinear method used for the final 2024 predictor.
    mismatched = {label: signature(dataset) for label, dataset in required.items()
                  if label != "built_2012_raw" and signature(dataset) != reference}
    if mismatched:
        raise RuntimeError("All inputs must match the final 2024 grid:\n" + "\n".join(f"{k}: {v}" for k, v in mismatched.items()))

    arcpy.env.snapRaster = FINAL_2024
    arcpy.env.extent = arcpy.Describe(FINAL_2024).extent
    arcpy.env.cellSize = FINAL_2024
    arcpy.env.mask = FINAL_2024
    arcpy.env.outputCoordinateSystem = arcpy.Describe(FINAL_2024).spatialReference
    built_2012_aligned = align_2012_built(required["built_2012_raw"])
    BACKUPS.mkdir(parents=True, exist_ok=True); REPORTS.mkdir(parents=True, exist_ok=True)
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUPS / f"Resistance_before_2030_permeability_scenarios_{stamp}.aprx"
    aprx.saveACopy(str(backup))

    # Historical global scaling is retained and capped at 1--10.  This avoids
    # silently expanding the expert-assigned resistance scale outside its stated range.
    built_bounds = (min(prop(locate(f"built_{year}_1km", allow_tif=True), "MINIMUM") for year in (2012, 2016, 2020, 2024)),
                    max(prop(locate(f"built_{year}_1km", allow_tif=True), "MAXIMUM") for year in (2012, 2016, 2020, 2024)))
    lights_bounds = (min(prop(locate(f"lights_{year}_1km_flaremasked"), "MINIMUM") for year in (2012, 2016, 2020, 2024)),
                     max(prop(locate(f"lights_{year}_1km_flaremasked"), "MAXIMUM") for year in (2012, 2016, 2020, 2024)))
    tree12, tree24 = Raster(required["tree_2012"]), Raster(required["tree_2024"])
    nt12, nt24 = Raster(required["nontree_2012"]), Raster(required["nontree_2024"])
    bare12, bare24 = Raster(required["bare_2012"]), Raster(required["bare_2024"])
    built12, built24 = Raster(built_2012_aligned), Raster(required["built_2024"])
    final_support = Raster(FINAL_2024)
    built24_scaled = scale_1_10(built24, *built_bounds)
    vegetation24 = vegetation(tree24, nt24, bare24)
    core_values = [int(value) for (value,) in arcpy.da.SearchCursor(CORES, ["Value"])]
    core_ids = sorted(set(v for v in core_values if v > 0))
    if len(core_ids) != 23:
        raise RuntimeError(f"Expected 23 fixed cores; found {len(core_ids)}")

    records = []
    for name, fraction in SCENARIOS.items():
        # 0 = hold 2024; 0.5 = continue the 2012--2024 rate for six years;
        # 1.0 = twice that annual rate.  Lights deliberately remain at 2024:
        # they carry only 10% anthropogenic weight and are noisy even after flare masking.
        future_built = Con((built24 + fraction * (built24 - built12)) < 0, 0, built24 + fraction * (built24 - built12))
        future_tree = bounded_percent(tree24 + fraction * (tree24 - tree12))
        future_nt = bounded_percent(nt24 + fraction * (nt24 - nt12))
        future_bare = bounded_percent(bare24 + fraction * (bare24 - bare12))
        output = os.path.join(GDB, f"resistance_future2030_{name}_balanced_fence")
        delete_if_exists(output)
        if fraction == 0.0:
            # The low-growth scenario is an exact copy of the verified final
            # 2024 surface, avoiding reconstruction drift in any finalized term.
            final_support.save(output)
        else:
            # Apply only the projected dynamic-component deltas to the verified
            # final surface. Built-up contributes 0.30 within the 0.60
            # anthropogenic term; vegetation contributes 0.20. All other terms
            # therefore remain byte-for-byte conceptually anchored to 2024.
            delta_unfenced = (
                (scale_1_10(future_built, *built_bounds) - built24_scaled) * 0.30 * 0.60
                + (vegetation(future_tree, future_nt, future_bare) - vegetation24) * 0.20
            )
            (final_support + delta_unfenced * Raster(FENCE)).save(output)
        arcpy.management.CalculateStatistics(output, 1, 1, [], "OVERWRITE")
        values = arcpy.RasterToNumPyArray(output, nodata_to_value=-3.4e38)
        cores = arcpy.RasterToNumPyArray(CORES, nodata_to_value=-9999)
        missing = [core_id for core_id in core_ids if not ((cores == core_id) & (values > -3e38)).any()]
        del values, cores
        if missing:
            raise RuntimeError(f"{name} removes fixed cores: {missing}")
        records.append({
            "scenario": name, "projection_fraction_of_2012_2024_change": fraction,
            "output": output, "minimum": prop(output, "MINIMUM"), "maximum": prop(output, "MAXIMUM"),
            "built_scaling_bounds": list(built_bounds), "lights_scaling_bounds": list(lights_bounds),
            "fixed_cores_retained": len(core_ids),
        })
        print("created:", output)

    csv_path = REPORTS / f"future2030_permeability_scenario_register_{stamp}.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0])); writer.writeheader(); writer.writerows(records)
    json_path = REPORTS / f"future2030_permeability_scenario_register_{stamp}.json"
    json_path.write_text(json.dumps({
        "created": datetime.now().isoformat(timespec="seconds"), "horizon": 2030,
        "purpose": "Scenario-based prospective permeability stress test; not a calibrated forecast or prediction of cheetah movement, occurrence, range, roads, livestock, or management.",
        "fixed": "Verified final 2024 resistance baseline, 23 historical cores, 2024 flare-masked lights, roads, livestock, terrain, and documented finite fence multiplier.",
        "projected": "Only built-up and VCF tree/non-tree/bare deltas from the 2012--2024 linear trend are added to the verified 2024 final surface; VCF is bounded to physical limits and built-up retains historical 1--10 component scaling.",
        "scenario_definitions": {
            "low_growth": "Hold dynamic projected components at 2024 levels.",
            "continuation": "Extend one half of the net 2012--2024 change beyond 2024 (six years at the historical average annual rate).",
            "high_development": "Extend the full net 2012--2024 change beyond 2024 (twice the continuation annual rate).",
        }, "records": records,
    }, indent=2), encoding="utf-8")
    aprx.save()
    print("backup:", backup)
    print("register:", csv_path)
    print("method record:", json_path)
    print("Complete. Three 2030 scenario surfaces were created; historical surfaces and current-flow outputs were unchanged.")


if __name__ == "__main__":
    main()
