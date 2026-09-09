"""Create mapped priority and uncertainty link layers with temporal evidence.

Geometry is taken from the balanced 2024 least-cost paths as a representative
display line. Eligibility and interpretation come from the integrated evidence
table and therefore include weight, fence, and vegetation-direction tests. The
display line is not an ensemble corridor or an observed movement route.
"""

from datetime import datetime
from pathlib import Path
import csv
import os

import arcpy


GDB = r"C:\cheetah\gdb\cheetah_working.gdb"
SOURCE = os.path.join(GDB, "least_cost_paths_temporal_veg_balanced_2024")
PRIMARY = os.path.join(GDB, "conservation_priority_paths_temporal")
UNCERTAINTY = os.path.join(GDB, "conservation_uncertainty_paths_temporal")
EVIDENCE = Path(r"C:\cheetah\reports\conservation_link_evidence_integrated.csv")
REPORT = Path(r"C:\cheetah\reports\conservation_priority_spatial_layers.csv")
BACKUPS = Path(r"C:\cheetah\backups")
PARENT = "Cheetah project"
GROUP = "16 Conservation priorities · temporal"

FIELDS = (
    ("IMP_RANK", "LONG", None),
    ("EDGE_BTW", "DOUBLE", None),
    ("MED_CHG", "DOUBLE", None),
    ("CHG_LOW", "DOUBLE", None),
    ("CHG_BAL", "DOUBLE", None),
    ("CHG_HIGH", "DOUBLE", None),
    ("TEMP_DIR", "TEXT", 40),
    ("WT_ROB", "TEXT", 3),
    ("FNC_ROB", "TEXT", 3),
    ("VEG_ROB", "TEXT", 3),
    ("PRIOR_USE", "TEXT", 180),
    ("GEOM_BAS", "TEXT", 80),
)


def pair_key(a, b):
    a, b = int(a), int(b)
    return (a, b) if a <= b else (b, a)


def read_evidence():
    if not EVIDENCE.exists():
        raise FileNotFoundError(EVIDENCE)
    result = {}
    with EVIDENCE.open("r", newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            key = pair_key(row["from_core"], row["to_core"])
            if key in result:
                raise RuntimeError(f"Duplicate evidence pair: {key}")
            result[key] = row
    if len(result) != 45:
        raise RuntimeError(f"Expected 45 evidence rows; found {len(result)}")
    return result


def remove_map_references(map_object, dataset):
    target = os.path.normcase(os.path.normpath(dataset))
    for layer in list(map_object.listLayers()):
        try:
            if layer.supports("DATASOURCE"):
                source = os.path.normcase(os.path.normpath(layer.dataSource))
                if source == target:
                    map_object.removeLayer(layer)
        except Exception:
            pass


def prepare_output(map_object, output, wanted_pairs, evidence):
    remove_map_references(map_object, output)
    if arcpy.Exists(output):
        arcpy.management.Delete(output)
    arcpy.management.CopyFeatures(SOURCE, output)
    with arcpy.da.UpdateCursor(output, ["FROM_ID", "TO_ID"]) as rows:
        for from_id, to_id in rows:
            if pair_key(from_id, to_id) not in wanted_pairs:
                rows.deleteRow()

    existing = {field.name.upper() for field in arcpy.ListFields(output)}
    for name, field_type, length in FIELDS:
        if name in existing:
            continue
        kwargs = {"field_length": length} if length else {}
        arcpy.management.AddField(output, name, field_type, **kwargs)

    cursor_fields = ["FROM_ID", "TO_ID"] + [field[0] for field in FIELDS]
    with arcpy.da.UpdateCursor(output, cursor_fields) as rows:
        for row in rows:
            record = evidence[pair_key(row[0], row[1])]
            values = [
                int(record["importance_rank"]) if record["importance_rank"] else None,
                float(record["edge_betweenness_normalized"]),
                float(record["median_change_percent_2012_2024"]),
                float(record["veg_low_change_percent_2012_2024"]),
                float(record["veg_balanced_change_percent_2012_2024"]),
                float(record["veg_high_change_percent_2012_2024"]),
                record["temporal_direction_interpretation"],
                record["weight_robust"],
                record["fence_robust"],
                record["vegetation_direction_robust"],
                record["priority_use_final"],
                "balanced 2024 representative least-cost path",
            ]
            rows.updateRow(list(row[:2]) + values)

    actual = int(arcpy.management.GetCount(output)[0])
    if actual != len(wanted_pairs):
        raise RuntimeError(f"Expected {len(wanted_pairs)} rows in {output}; found {actual}")
    return actual


def get_group(map_object):
    parents = [
        layer for layer in map_object.listLayers()
        if layer.isGroupLayer and layer.longName == PARENT
    ]
    if len(parents) != 1:
        raise RuntimeError(f"Expected one {PARENT!r} group; found {len(parents)}")
    wanted = PARENT + "\\" + GROUP
    groups = [
        layer for layer in map_object.listLayers()
        if layer.isGroupLayer and layer.longName == wanted
    ]
    return groups[0] if groups else map_object.createGroupLayer(GROUP, parents[0])


def add_to_group(map_object, group, dataset, visible):
    loose = map_object.addDataFromPath(dataset)
    grouped = map_object.addLayerToGroup(group, loose, "BOTTOM")
    map_object.removeLayer(loose)
    if not grouped:
        raise RuntimeError(f"Could not add {dataset} to {GROUP}")
    grouped[0].visible = visible
    return grouped[0]


def main():
    if not arcpy.Exists(SOURCE):
        raise FileNotFoundError(SOURCE)
    evidence = read_evidence()
    primary_pairs = {
        pair for pair, row in evidence.items()
        if row["primary_priority_eligible_final"].strip().lower() == "yes"
    }
    uncertainty_pairs = set(evidence) - primary_pairs
    if len(primary_pairs) != 32 or len(uncertainty_pairs) != 13:
        raise RuntimeError(
            f"Expected 32 primary and 13 uncertainty links; found "
            f"{len(primary_pairs)} and {len(uncertainty_pairs)}"
        )

    aprx = arcpy.mp.ArcGISProject("CURRENT")
    maps = aprx.listMaps("Map")
    map_object = maps[0] if maps else aprx.activeMap
    if map_object is None:
        raise RuntimeError("No active map was found")
    group = get_group(map_object)

    BACKUPS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUPS / f"{Path(aprx.filePath).stem}_before_temporal_priority_layers_{stamp}.aprx"
    aprx.saveACopy(str(backup))
    print(f"backup: {backup}")

    primary_count = prepare_output(map_object, PRIMARY, primary_pairs, evidence)
    uncertainty_count = prepare_output(map_object, UNCERTAINTY, uncertainty_pairs, evidence)
    add_to_group(map_object, group, PRIMARY, True)
    add_to_group(map_object, group, UNCERTAINTY, False)
    group.visible = True
    aprx.save()

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    with REPORT.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["layer", "feature_count", "geometry_basis", "interpretation"])
        writer.writerow([
            PRIMARY, primary_count, "balanced 2024 representative least-cost path",
            "weight-, fence-, and vegetation-direction-robust primary links",
        ])
        writer.writerow([
            UNCERTAINTY, uncertainty_count, "balanced 2024 representative least-cost path",
            "retain for uncertainty and data collection; exclude from primary priorities",
        ])

    print(f"primary priority paths: {primary_count}")
    print(f"uncertainty paths: {uncertainty_count}")
    print(f"primary layer: {PRIMARY}")
    print(f"uncertainty layer: {UNCERTAINTY}")
    print(f"report: {REPORT}")
    print("The mapped geometry is representative, not an ensemble corridor or observed route.")


if __name__ == "__main__":
    main()
