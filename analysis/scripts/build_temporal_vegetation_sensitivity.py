"""Build protocol-consistent vegetation sensitivity surfaces for 2012-2024.

The existing anthropogenic-only temporal surfaces are preserved. This script
creates low/base/high vegetation-weight scenarios using half/base/double
vegetation influence (10/20/40 percent), following the sensitivity logic used
by Moqanaki & Cushman (2017; online 2016). Source rasters are never modified.
"""

from pathlib import Path
import csv
import arcpy
from arcpy.sa import Con, ExtractByMask, Raster


GDB = r"C:\cheetah\gdb\cheetah_working.gdb"
SOURCE_GDB = r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah_connectivity.gdb"
GEE = Path(r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah\rasters\gee_exports")
REPORT = Path(r"C:\cheetah\reports\temporal_vegetation_sensitivity_register.csv")
YEARS = (2012, 2016, 2020, 2024)

SCENARIOS = {
    "veg_low": {"anthropogenic": 0.70, "vegetation": 0.10, "terrain": 0.20},
    "veg_balanced": {"anthropogenic": 0.60, "vegetation": 0.20, "terrain": 0.20},
    "veg_high": {"anthropogenic": 0.40, "vegetation": 0.40, "terrain": 0.20},
}


def gdb(name):
    return f"{GDB}\\{name}"


def locate(name, tif=True):
    candidates = [gdb(name), f"{SOURCE_GDB}\\{name}"]
    if tif:
        candidates.append(str(GEE / f"{name}.tif"))
    for candidate in candidates:
        if arcpy.Exists(candidate):
            return candidate
    raise FileNotFoundError(f"Missing {name}. Searched:\n  " + "\n  ".join(candidates))


def locate_snap():
    for candidate in (
        gdb("snapgrid_1km"),
        f"{SOURCE_GDB}\\snapgrid_1km",
        str(GEE / "built_2012_1km.tif"),
    ):
        if arcpy.Exists(candidate):
            return candidate
    raise FileNotFoundError("No snap raster found")


def prop(dataset, property_name):
    try:
        return float(arcpy.management.GetRasterProperties(dataset, property_name).getOutput(0))
    except Exception:
        arcpy.management.CalculateStatistics(dataset, 1, 1, [], "OVERWRITE")
        return float(arcpy.management.GetRasterProperties(dataset, property_name).getOutput(0))


def clamp(raster, low=0.0, high=100.0):
    value = Raster(raster)
    return Con(value < low, low, Con(value > high, high, value))


def scale_1_10(raster, low, high):
    if high <= low:
        return Raster(raster) * 0 + 1
    return ((Raster(raster) - low) / (high - low) * 9) + 1


def replace(output, expression):
    if arcpy.Exists(output):
        arcpy.management.Delete(output)
    expression.save(output)
    arcpy.management.CalculateStatistics(output, 1, 1, [], "OVERWRITE")


def align_vcf(variable, year, snap):
    output = gdb(f"{variable}_{year}_aligned_1km")
    source = locate(f"{variable}_{year}_1km")
    # ExtractByMask uses the analysis snap/cell-size settings and clips to the
    # verified study grid. Existing aligned copies are deliberately rebuilt so
    # every year uses the same operation.
    replace(output, ExtractByMask(Raster(source), Raster(snap)))
    return output


def main():
    arcpy.CheckOutExtension("Spatial")
    arcpy.env.workspace = GDB
    arcpy.env.overwriteOutput = True
    snap = locate_snap()
    arcpy.env.snapRaster = snap
    arcpy.env.cellSize = snap
    arcpy.env.extent = arcpy.Describe(snap).extent
    arcpy.env.mask = snap

    roads_path = locate("pressure_roads_1_10", tif=False)
    livestock_path = locate("pressure_livestock_index_1_10", tif=False)
    terrain_path = locate("terrain_resistance_1_10", tif=False)

    built = {year: locate(f"built_{year}_1km") for year in YEARS}
    lights = {}
    for year in YEARS:
        try:
            lights[year] = locate(f"lights_{year}_1km_flaremasked", tif=False)
        except FileNotFoundError:
            lights[year] = locate(f"lights_{year}_1km")

    # Preserve fixed cross-year scaling used by the existing temporal model.
    built_bounds = (
        min(prop(value, "MINIMUM") for value in built.values()),
        max(prop(value, "MAXIMUM") for value in built.values()),
    )
    lights_bounds = (
        min(prop(value, "MINIMUM") for value in lights.values()),
        max(prop(value, "MAXIMUM") for value in lights.values()),
    )

    roads = scale_1_10(roads_path, prop(roads_path, "MINIMUM"), prop(roads_path, "MAXIMUM"))
    livestock = scale_1_10(
        livestock_path, prop(livestock_path, "MINIMUM"), prop(livestock_path, "MAXIMUM")
    )
    terrain = Raster(terrain_path)

    register = []
    for year in YEARS:
        print(f"{year}: aligning VCF fields")
        tree = clamp(align_vcf("vcf_tree", year, snap))
        nontree = clamp(align_vcf("vcf_nontree", year, snap))
        bare = clamp(align_vcf("vcf_bare", year, snap))

        # MOD44B fractions should be complementary but do not always sum to
        # exactly 100 after export/resampling. Average the explicit bare band
        # with the residual deficit so no single noisy band controls the result.
        vegetated = Con(tree + nontree > 100, 100, tree + nontree)
        cover_deficit = 100 - vegetated
        sparse_bare_proxy = (bare + cover_deficit) / 2.0
        vegetation_resistance = 1 + 9 * (sparse_bare_proxy / 100.0)
        vegetation_output = gdb(f"vegetation_resistance_{year}_1_10")
        replace(vegetation_output, vegetation_resistance)

        built_1_10 = scale_1_10(built[year], *built_bounds)
        lights_1_10 = scale_1_10(lights[year], *lights_bounds)
        anthropogenic = (
            built_1_10 * 0.30
            + roads * 0.30
            + livestock * 0.30
            + lights_1_10 * 0.10
        )

        for label, weights in SCENARIOS.items():
            output_name = f"resistance_temporal_{label}_{year}"
            output = gdb(output_name)
            expression = (
                anthropogenic * weights["anthropogenic"]
                + Raster(vegetation_output) * weights["vegetation"]
                + terrain * weights["terrain"]
            )
            replace(output, expression)
            register.append({
                "scenario": label,
                "year": year,
                "output": output,
                "anthropogenic_weight": weights["anthropogenic"],
                "vegetation_weight": weights["vegetation"],
                "terrain_weight": weights["terrain"],
                "vegetation_transform": "1 + 9 * mean(VCF bare, 100 - min(100, tree + nontree)) / 100",
                "interpretation": "sensitivity scenario; relative structural resistance, not empirical movement coefficient",
            })
            print(f"created: {output_name}")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    with REPORT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(register[0]))
        writer.writeheader()
        writer.writerows(register)

    print(f"scenario surfaces created: {len(register)}")
    print(f"register: {REPORT}")
    print("Existing anthropogenic-only temporal surfaces were preserved.")
    print("No source rasters were changed.")


if __name__ == "__main__":
    main()
