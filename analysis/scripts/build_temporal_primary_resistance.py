"""Build comparable primary resistance surfaces for 2012, 2016, 2020, 2024.

All time-varying layers are scaled with global bounds calculated across all
four snapshots. This preserves temporal comparability; per-year min/max
scaling would erase real change. Static roads, livestock and terrain are
reused across years. Source rasters are never modified.
"""

from pathlib import Path
import arcpy
from arcpy.sa import Raster

GDB = r"C:\cheetah\gdb\cheetah_working.gdb"
SOURCE_GDB = r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah_connectivity.gdb"
GEE = Path(r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah\rasters\gee_exports")
YEARS = (2012, 2016, 2020, 2024)
STATIC = {
    # The selected 5-km GRIP4 density was standardized and stored under this
    # documented component name by the resistance workflow.
    "roads": "pressure_roads_1_10",
    "livestock": "pressure_livestock_index_1_10",
    "terrain": "terrain_resistance_1_10",
}
def path(name):
    return f"{GDB}\\{name}"


def locate(name, allow_tif=True):
    """Find a project dataset without assuming every source was copied to GDB."""
    candidates = [path(name), f"{SOURCE_GDB}\\{name}"]
    if allow_tif:
        candidates.append(str(GEE / f"{name}.tif"))
    for candidate in candidates:
        if arcpy.Exists(candidate):
            return candidate
    raise FileNotFoundError(
        f"Missing required dataset {name}. Searched:\n  " + "\n  ".join(candidates)
    )


def locate_snap():
    candidates = [
        path("snapgrid_1km"),
        f"{SOURCE_GDB}\\snapgrid_1km",
        str(GEE / "built_2012_1km.tif"),
    ]
    for candidate in candidates:
        if arcpy.Exists(candidate):
            return candidate
    raise FileNotFoundError("No verified snap raster found. Searched:\n  " + "\n  ".join(candidates))


def prop(raster, name):
    try:
        return float(arcpy.management.GetRasterProperties(raster, name).getOutput(0))
    except Exception:
        # Some GeoTIFFs arrive without statistics; calculate them once, then retry.
        arcpy.management.CalculateStatistics(raster, 1, 1, [], "OVERWRITE")
        return float(arcpy.management.GetRasterProperties(raster, name).getOutput(0))


def scale(raster, low, high):
    if high <= low:
        return Raster(raster) * 0 + 1
    return ((Raster(raster) - low) / (high - low) * 9) + 1


def delete_if_exists(out):
    if arcpy.Exists(out):
        arcpy.management.Delete(out)


def main():
    arcpy.CheckOutExtension("Spatial")
    arcpy.env.workspace = GDB
    snap = locate_snap()
    print(f"snap raster: {snap}")
    arcpy.env.snapRaster = snap
    arcpy.env.cellSize = 1000
    arcpy.env.extent = arcpy.Describe(snap).extent
    arcpy.env.overwriteOutput = True

    built = {year: locate(f"built_{year}_1km") for year in YEARS}
    lights = {}
    for year in YEARS:
        try:
            lights[year] = locate(f"lights_{year}_1km_flaremasked", allow_tif=False)
        except FileNotFoundError:
            lights[year] = locate(f"lights_{year}_1km")
    roads_path = locate(STATIC["roads"], allow_tif=False)
    livestock_path = locate(STATIC["livestock"], allow_tif=False)
    terrain_path = locate(STATIC["terrain"], allow_tif=False)

    # Fixed bounds across all snapshots make values comparable through time.
    bounds = {}
    for label, rasters in {
        "built": list(built.values()),
        "lights": list(lights.values()),
    }.items():
        lows = [prop(r, "MINIMUM") for r in rasters]
        highs = [prop(r, "MAXIMUM") for r in rasters]
        bounds[label] = (min(lows), max(highs))
    print(f"global scaling bounds: built={bounds['built']}, lights={bounds['lights']}")

    roads = Raster(roads_path)
    livestock = Raster(livestock_path)
    terrain = Raster(terrain_path)
    roads_1_10 = scale(roads, prop(roads, "MINIMUM"), prop(roads, "MAXIMUM"))
    livestock_1_10 = scale(livestock, prop(livestock, "MINIMUM"), prop(livestock, "MAXIMUM"))

    for year in YEARS:
        built_1_10 = scale(built[year], *bounds["built"])
        lights_1_10 = scale(lights[year], *bounds["lights"])
        # Primary formulation: anthropogenic 80%, terrain 20%; equal weight
        # within anthropogenic pressure except lights receive 10%.
        anthropogenic = (
            built_1_10 * 0.30 + roads_1_10 * 0.30 + livestock_1_10 * 0.30 + lights_1_10 * 0.10
        )
        output = path(f"resistance_primary_unfenced_combined_{year}")
        delete_if_exists(output)
        (anthropogenic * 0.80 + terrain * 0.20).save(output)
        arcpy.management.CalculateStatistics(output, 1, 1, [], "OVERWRITE")
        print(f"created: resistance_primary_unfenced_combined_{year}")

    print("Complete. Historical primary resistance surfaces are ready for least-cost paths.")
    print("No source rasters were changed.")


if __name__ == "__main__":
    main()
