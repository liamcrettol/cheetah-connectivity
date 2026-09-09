"""Export only the final documented-fence resistance inputs for Circuitscape.

Run this in ArcGIS Pro before run_final_pairwise_current_flow.ps1.  It exports
the fixed 23-core raster plus four final vegetation-balanced, finite-fence
resistance rasters.  Existing reference inputs and outputs are untouched.
"""

from datetime import datetime
from pathlib import Path
import json
import math
import os

import arcpy


GDB = r"C:\cheetah\gdb\cheetah_working.gdb"
OUT = Path(r"C:\cheetah\circuitscape\inputs\final_balanced_fence_documented")
YEARS = (2012, 2016, 2020, 2024)
CORES = os.path.join(GDB, "cheetah_core_primary_density051_min500_1km")
RESISTANCE = {
    year: os.path.join(GDB, f"resistance_final_balanced_fence_documented_{year}")
    for year in YEARS
}


def grid(dataset):
    r = arcpy.Raster(dataset)
    e = r.extent
    return {
        "columns": int(r.width), "rows": int(r.height),
        "cell_width": float(r.meanCellWidth), "cell_height": float(r.meanCellHeight),
        "xmin": float(e.XMin), "ymin": float(e.YMin),
        "xmax": float(e.XMax), "ymax": float(e.YMax),
        "spatial_reference": r.spatialReference.name,
        "wkid": int(r.spatialReference.factoryCode or 0),
    }


def same_grid(left, right, tolerance=0.001):
    if left["columns"] != right["columns"] or left["rows"] != right["rows"]:
        return False
    for key in ("cell_width", "cell_height", "xmin", "ymin", "xmax", "ymax"):
        if not math.isclose(left[key], right[key], rel_tol=0, abs_tol=tolerance):
            return False
    return left["wkid"] == right["wkid"]


def value(dataset, property_name):
    try:
        return float(arcpy.management.GetRasterProperties(dataset, property_name).getOutput(0))
    except Exception:
        arcpy.management.CalculateStatistics(dataset, 1, 1, [], "OVERWRITE")
        return float(arcpy.management.GetRasterProperties(dataset, property_name).getOutput(0))


def export_ascii(source, destination):
    if destination.exists():
        destination.unlink()
    arcpy.conversion.RasterToASCII(source, str(destination))
    if not destination.exists() or destination.stat().st_size == 0:
        raise RuntimeError(f"ASCII export failed: {destination}")


def main():
    required = [CORES, *RESISTANCE.values()]
    missing = [p for p in required if not arcpy.Exists(p)]
    if missing:
        raise FileNotFoundError("Missing required final input(s):\n  " + "\n  ".join(missing))
    reference = grid(RESISTANCE[2012])
    inputs = {"cores": grid(CORES), **{str(y): grid(p) for y, p in RESISTANCE.items()}}
    bad = [label for label, candidate in inputs.items() if not same_grid(reference, candidate)]
    if bad:
        raise RuntimeError("Final inputs do not share an identical grid:\n" +
                           "\n".join(f"  {label}: {inputs[label]}" for label in bad))
    core_ids = sorted({int(v) for (v,) in arcpy.da.SearchCursor(CORES, ["Value"])})
    if len(core_ids) != 23:
        raise RuntimeError(f"Expected 23 fixed cores, found {len(core_ids)}: {core_ids}")

    OUT.mkdir(parents=True, exist_ok=True)
    core_ascii = OUT / "cheetah_cores_fixed_23.asc"
    print(f"verified grid: {reference['columns']} columns x {reference['rows']} rows; {reference['cell_width']:.0f} m cells")
    print(f"exporting fixed cores: {core_ascii}")
    export_ascii(CORES, core_ascii)
    records = []
    for year, source in RESISTANCE.items():
        destination = OUT / f"resistance_final_balanced_fence_documented_{year}.asc"
        print(f"exporting final {year}: {destination}")
        export_ascii(source, destination)
        records.append({"year": year, "source": source, "ascii": str(destination),
                        "minimum": value(source, "MINIMUM"), "maximum": value(source, "MAXIMUM")})

    manifest = {
        "created": datetime.now().isoformat(timespec="seconds"),
        "analysis": "Circuitscape pairwise current flow",
        "scenario": "final vegetation-balanced + documented finite KAZA/Kruger fence",
        "habitat_maps_are_resistances": True,
        "core_definition": "fixed historical density baseline",
        "core_count": 23, "core_ids": core_ids, "core_source": CORES,
        "core_ascii": str(core_ascii), "grid": reference, "resistance_surfaces": records,
        "water_context_policy": "All-zero VCF triplets remain finite baseline values; no permanent water barrier was inferred from annual land-cover context.",
        "fence_policy": "Documented KAZA+Kruger finite/crossable multiplier; maximum used where fence datasets overlap.",
        "normalization_note": "Use the same 253 contributing core pairs each year before temporal current comparison.",
    }
    manifest_path = OUT / "final_circuitscape_input_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"manifest: {manifest_path}")
    print("Complete. Final inputs exported; Circuitscape was not run and no GIS datasets were changed.")


if __name__ == "__main__":
    main()
