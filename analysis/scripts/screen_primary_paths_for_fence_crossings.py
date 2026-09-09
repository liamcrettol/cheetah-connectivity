"""Identify primary paths that intersect rasterized fence cells; no data are changed."""

from pathlib import Path
import csv
import os

import arcpy

GDB = r"C:\cheetah\gdb\cheetah_working.gdb"
PATHS = os.path.join(GDB, "least_cost_paths_primary_combined_unfenced")
KAZA = os.path.join(GDB, "vet_fence_kaza_wwf_reference")
KRUGER = os.path.join(GDB, "kruger_boundary_fence_status_reference")
REPORT = Path(r"C:\cheetah\reports\primary_path_fence_crossing_screen.csv")
HALF_DIAGONAL_1KM = 710.0


def merged_buffer(path, where_clause=None):
    geometries = []
    fields = ["SHAPE@"]
    with arcpy.da.SearchCursor(path, fields, where_clause=where_clause) as rows:
        for (shape,) in rows:
            if shape:
                geometries.append(shape.buffer(HALF_DIAGONAL_1KM))
    if not geometries:
        return None
    result = geometries[0]
    for geometry in geometries[1:]:
        result = result.union(geometry)
    return result


def main():
    for dataset in (PATHS, KAZA, KRUGER):
        if not arcpy.Exists(dataset):
            raise FileNotFoundError(dataset)
    kaza_cells = merged_buffer(KAZA)
    kruger_documented = merged_buffer(KRUGER, "STATUS = 'DOCUMENTED_FENCED'")
    kruger_conservative = merged_buffer(KRUGER, "STATUS IN ('DOCUMENTED_FENCED', 'UNCERTAIN')")

    output = []
    with arcpy.da.SearchCursor(PATHS, ["FROM_ID", "TO_ID", "SHAPE@"]) as rows:
        for from_id, to_id, path in rows:
            crosses_kaza = not path.disjoint(kaza_cells)
            crosses_documented = not path.disjoint(kruger_documented)
            crosses_conservative = not path.disjoint(kruger_conservative)
            output.append([
                int(from_id), int(to_id), int(crosses_kaza), int(crosses_documented),
                int(crosses_conservative), int(crosses_kaza or crosses_documented),
                int(crosses_kaza or crosses_conservative),
            ])

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    with REPORT.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "from_core", "to_core", "kaza_main_or_nearbarrier",
            "kruger_documented_only", "kruger_documented_or_uncertain",
            "combined_kruger_documented_scenario", "combined_kruger_conservative_scenario",
        ])
        writer.writerows(sorted(output))

    columns = [
        ("KAZA main/near-barrier", 2), ("Kruger documented boundary only", 3),
        ("Kruger documented or uncertain", 4), ("combined documented scenario", 5),
        ("combined conservative scenario", 6),
    ]
    print(f"primary paths screened: {len(output)}")
    for label, index in columns:
        pairs = [(row[0], row[1]) for row in output if row[index]]
        print(f"{label}: {len(pairs)} affected pairs")
        if pairs:
            print("  " + ", ".join(f"{a}-{b}" for a, b in pairs))
    print(f"report: {REPORT}")
    print("No rasters, feature classes, or map layers were changed.")


if __name__ == "__main__":
    main()
