"""Export verified pairwise Circuitscape inputs for the four temporal snapshots.

This preparation step does not run Circuitscape or alter ArcGIS datasets. It
exports the fixed historical core raster and the four primary, unfenced
resistance surfaces to ASCII grids after verifying identical alignment.
"""

from datetime import datetime
from pathlib import Path
import json
import math
import os

import arcpy


GDB = r"C:\cheetah\gdb\cheetah_working.gdb"
OUT = Path(r"C:\cheetah\circuitscape\inputs")
YEARS = (2012, 2016, 2020, 2024)
CORES = os.path.join(GDB, "cheetah_core_primary_density051_min500_1km")
RESISTANCE = {
    year: os.path.join(GDB, f"resistance_primary_unfenced_combined_{year}")
    for year in YEARS
}


def raster_grid(dataset):
    desc = arcpy.Describe(dataset)
    extent = desc.extent
    return {
        "columns": int(desc.width),
        "rows": int(desc.height),
        "cell_width": float(desc.meanCellWidth),
        "cell_height": float(desc.meanCellHeight),
        "xmin": float(extent.XMin),
        "ymin": float(extent.YMin),
        "xmax": float(extent.XMax),
        "ymax": float(extent.YMax),
        "spatial_reference": desc.spatialReference.name,
        "wkid": int(desc.spatialReference.factoryCode or 0),
    }


def same_grid(left, right, tolerance=0.001):
    if left["columns"] != right["columns"] or left["rows"] != right["rows"]:
        return False
    numeric = ("cell_width", "cell_height", "xmin", "ymin", "xmax", "ymax")
    return all(math.isclose(left[key], right[key], abs_tol=tolerance) for key in numeric)


def property_value(dataset, property_name):
    try:
        value = arcpy.management.GetRasterProperties(dataset, property_name).getOutput(0)
    except Exception:
        arcpy.management.CalculateStatistics(dataset, 1, 1, [], "OVERWRITE")
        value = arcpy.management.GetRasterProperties(dataset, property_name).getOutput(0)
    return float(value)


def export_ascii(source, destination):
    if destination.exists():
        destination.unlink()
    arcpy.conversion.RasterToASCII(source, str(destination))
    if not destination.exists() or destination.stat().st_size == 0:
        raise RuntimeError(f"ASCII export failed: {destination}")


def main():
    required = [CORES] + list(RESISTANCE.values())
    missing = [dataset for dataset in required if not arcpy.Exists(dataset)]
    if missing:
        raise FileNotFoundError("Missing required dataset(s):\n  " + "\n  ".join(missing))

    OUT.mkdir(parents=True, exist_ok=True)
    reference_grid = raster_grid(RESISTANCE[2012])
    grids = {"cores": raster_grid(CORES)}
    grids.update({str(year): raster_grid(dataset) for year, dataset in RESISTANCE.items()})
    mismatches = [name for name, grid in grids.items() if not same_grid(reference_grid, grid)]
    if mismatches:
        details = "\n".join(f"{name}: {grids[name]}" for name in mismatches)
        raise RuntimeError("Circuitscape inputs are not on the same grid:\n" + details)

    print(
        "verified grid: "
        f"{reference_grid['columns']} columns x {reference_grid['rows']} rows; "
        f"{reference_grid['cell_width']:.0f} m cells"
    )

    core_ascii = OUT / "cheetah_cores_fixed_23.asc"
    print(f"exporting fixed cores: {core_ascii}")
    export_ascii(CORES, core_ascii)

    resistance_records = []
    for year in YEARS:
        source = RESISTANCE[year]
        destination = OUT / f"resistance_primary_unfenced_{year}.asc"
        print(f"exporting {year}: {destination}")
        export_ascii(source, destination)
        resistance_records.append({
            "year": year,
            "source": source,
            "ascii": str(destination),
            "minimum": property_value(source, "MINIMUM"),
            "maximum": property_value(source, "MAXIMUM"),
        })

    core_ids = sorted({int(row[0]) for row in arcpy.da.SearchCursor(CORES, ["Value"])})
    if len(core_ids) != 23:
        raise RuntimeError(f"Expected 23 fixed core IDs; found {len(core_ids)}: {core_ids}")

    manifest = {
        "created": datetime.now().isoformat(timespec="seconds"),
        "analysis": "Circuitscape pairwise current flow",
        "scenario": "pairwise",
        "habitat_maps_are_resistances": True,
        "core_definition": "fixed 2010-2016 historical density baseline",
        "core_count": len(core_ids),
        "core_ids": core_ids,
        "core_source": CORES,
        "core_ascii": str(core_ascii),
        "grid": reference_grid,
        "resistance_surfaces": resistance_records,
        "method_note": (
            "Use the same fixed focal cores for every year. Run pairwise current flow "
            "for each resistance surface and normalize cumulative current by the same "
            "number of contributing core pairs before temporal comparison."
        ),
    }
    manifest_path = OUT / "circuitscape_input_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"verified fixed cores: {len(core_ids)}")
    print(f"ASCII inputs: {OUT}")
    print(f"manifest: {manifest_path}")
    print("Complete. Circuitscape was not run and no ArcGIS datasets were changed.")


if __name__ == "__main__":
    main()
