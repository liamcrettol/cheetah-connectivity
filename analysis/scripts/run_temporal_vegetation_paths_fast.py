"""Fast least-cost paths for the temporal vegetation sensitivity scenarios.

Accuracy is unchanged from the existing fast temporal method: one CostDistance
surface is calculated per source core, year, and scenario, then CostPathAsPolyline
extracts every selected destination path from that surface. This avoids rerunning
the identical source calculation for each link. No rasters or map layers are
changed; new path feature classes and CSV reports are created.
"""

from pathlib import Path
import csv
import os
import sys
import arcpy
from arcpy.sa import CostDistance, CostPathAsPolyline


OUTPUTS = r"C:\Users\lcrettol\Documents\Codex\2026-08-25\i-am-working-on-this-spreadsheet\outputs"
if OUTPUTS not in sys.path:
    sys.path.insert(0, OUTPUTS)
import create_reference_least_cost_paths as base


DEFAULT_YEARS = (2012, 2016, 2020, 2024)
DEFAULT_SCENARIOS = ("veg_low", "veg_balanced", "veg_high")
# Optional filters let you run an endpoint pilot before the full grid:
#   CHEETAH_YEARS=2012,2024
#   CHEETAH_SCENARIOS=veg_balanced
YEARS = tuple(int(value) for value in os.environ.get("CHEETAH_YEARS", "2012,2016,2020,2024").split(","))
SCENARIOS = tuple(value.strip() for value in os.environ.get("CHEETAH_SCENARIOS", "veg_low,veg_balanced,veg_high").split(",") if value.strip())
if not set(YEARS).issubset(DEFAULT_YEARS):
    raise ValueError(f"CHEETAH_YEARS must be drawn from {DEFAULT_YEARS}; got {YEARS}")
if not set(SCENARIOS).issubset(DEFAULT_SCENARIOS):
    raise ValueError(f"CHEETAH_SCENARIOS must be drawn from {DEFAULT_SCENARIOS}; got {SCENARIOS}")
REPORTS = Path(r"C:\cheetah\reports")
REPORT_FIELDS = (
    "from_core", "to_core", "path_length_km", "accumulated_cost_raw", "status"
)


def expected_pairs_for_source(pairs, source_id):
    return [pair for pair in pairs if pair[0] == source_id]


def output_rows(output):
    """Return valid output rows keyed by core pair; reject duplicates."""
    if not arcpy.Exists(output):
        return {}
    rows = {}
    fields = ["FROM_ID", "TO_ID", "PATH_KM", "COST_RAW", "STATUS"]
    with arcpy.da.SearchCursor(output, fields) as cursor:
        for from_id, to_id, path_km, cost_raw, status in cursor:
            if str(status).upper() != "OK":
                continue
            pair = tuple(sorted((int(from_id), int(to_id))))
            if pair in rows:
                raise RuntimeError(f"Duplicate completed pair {pair} in {output}")
            rows[pair] = [pair[0], pair[1], path_km, cost_raw, "OK"]
    return rows


def write_checkpoint(output, report):
    """Write the currently completed output rows after every source core."""
    rows = output_rows(output)
    report.parent.mkdir(parents=True, exist_ok=True)
    temporary = report.with_suffix(report.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(REPORT_FIELDS)
        for pair in sorted(rows):
            writer.writerow(rows[pair])
    os.replace(temporary, report)
    return rows


def report_is_complete(report, pairs):
    if not report.exists():
        return False
    completed = set()
    try:
        with report.open("r", newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                if row.get("status", "").upper() != "OK":
                    continue
                if not row.get("path_length_km") or not row.get("accumulated_cost_raw"):
                    return False
                completed.add(tuple(sorted((int(row["from_core"]), int(row["to_core"])))))
    except (OSError, ValueError, KeyError):
        return False
    return completed == set(pairs)


def create_output(output):
    arcpy.management.CreateFeatureclass(
        base.GDB,
        Path(output).name,
        "POLYLINE",
        spatial_reference=arcpy.Describe(base.CORES).spatialReference,
    )
    for name, field_type, length in (
        ("FROM_ID", "LONG", None),
        ("TO_ID", "LONG", None),
        ("SCENARIO", "TEXT", 40),
        ("PATH_KM", "DOUBLE", None),
        ("COST_RAW", "DOUBLE", None),
        ("STATUS", "TEXT", 20),
    ):
        kwargs = {"field_length": length} if length else {}
        arcpy.management.AddField(output, name, field_type, **kwargs)


def delete_source_rows(output, source_id):
    with arcpy.da.UpdateCursor(output, ["FROM_ID"], f"FROM_ID = {int(source_id)}") as rows:
        for _ in rows:
            rows.deleteRow()


def main():
    arcpy.CheckOutExtension("Spatial")
    arcpy.env.overwriteOutput = True
    arcpy.env.snapRaster = base.SNAP
    arcpy.env.cellSize = base.SNAP
    arcpy.env.extent = base.SNAP
    arcpy.env.mask = base.MASK
    arcpy.env.outputCoordinateSystem = arcpy.Describe(base.SNAP).spatialReference
    arcpy.env.parallelProcessingFactor = "75%"

    for required in (base.CORES, base.LINKS, base.SNAP, base.MASK):
        base.require(required)

    pairs = sorted({
        tuple(sorted((int(a), int(b))))
        for a, b in arcpy.da.SearchCursor(base.LINKS, ["FROM_ID", "TO_ID"])
    })
    source_ids = sorted({pair[0] for pair in pairs})
    print(f"selected links: {len(pairs)}")
    print(f"source cores per run: {len(source_ids)}")
    print(f"planned cost-distance runs: {len(SCENARIOS) * len(YEARS) * len(source_ids)}")

    src = "fast_veg_temporal_source"
    dst = "fast_veg_temporal_destination"
    arcpy.management.MakeFeatureLayer(base.CORES, src)
    arcpy.management.MakeFeatureLayer(base.CORES, dst)

    for scenario in SCENARIOS:
        for year in YEARS:
            resistance = os.path.join(base.GDB, f"resistance_temporal_{scenario}_{year}")
            output = os.path.join(base.GDB, f"least_cost_paths_temporal_{scenario}_{year}")
            report = REPORTS / f"least_cost_paths_temporal_{scenario}_{year}.csv"
            base.require(resistance)
            if report_is_complete(report, pairs) and arcpy.Exists(output):
                if set(output_rows(output)) == set(pairs):
                    print(f"{scenario} {year}: already complete; skipping")
                    continue

            if not arcpy.Exists(output):
                create_output(output)
            required_fields = {"FROM_ID", "TO_ID", "SCENARIO", "PATH_KM", "COST_RAW", "STATUS"}
            actual_fields = {field.name for field in arcpy.ListFields(output)}
            if not required_fields.issubset(actual_fields):
                raise RuntimeError(f"Existing output has the wrong schema: {output}")

            completed_rows = output_rows(output)
            for source_id in source_ids:
                expected = expected_pairs_for_source(pairs, source_id)
                if all(pair in completed_rows for pair in expected):
                    print(f"{scenario} {year}: source core {source_id} already complete; skipping")
                    continue

                # A source is the checkpoint unit. Remove any partial rows from it
                # before recomputing so a restart cannot create duplicates.
                delete_source_rows(output, source_id)
                print(f"{scenario} {year}: source core {source_id}")
                arcpy.management.SelectLayerByAttribute(
                    src, "NEW_SELECTION", f"CORE_ID = {source_id}"
                )
                token = f"fast_{scenario}_{year}_{source_id}"
                cd = os.path.join(base.GDB, token + "_cd")
                bl = os.path.join(base.GDB, token + "_bl")
                base.delete_if_exists(cd)
                base.delete_if_exists(bl)
                try:
                    CostDistance(
                        src, resistance, maximum_distance=None, out_backlink_raster=bl
                    ).save(cd)
                    with arcpy.da.InsertCursor(
                        output,
                        ["SHAPE@", "FROM_ID", "TO_ID", "SCENARIO", "PATH_KM", "COST_RAW", "STATUS"],
                    ) as insert:
                        for from_id, to_id in expected:
                            arcpy.management.SelectLayerByAttribute(
                                dst, "NEW_SELECTION", f"CORE_ID = {to_id}"
                            )
                            path_fc = os.path.join(base.GDB, f"{token}_{to_id}_path")
                            base.delete_if_exists(path_fc)
                            try:
                                CostPathAsPolyline(
                                    dst, cd, bl, path_fc, "BEST_SINGLE", "CORE_ID"
                                )
                                geometry, path_cost = base.first_path_geometry(path_fc)
                                path_km = float(geometry.length / 1000.0)
                                insert.insertRow([
                                    geometry, from_id, to_id, f"{scenario}_{year}",
                                    path_km, path_cost, "OK",
                                ])
                            except Exception as exc:
                                message = str(exc).replace("\n", " | ")
                                print(f"WARNING: {scenario} {year} {from_id}-{to_id}: {message}")
                            finally:
                                base.delete_if_exists(path_fc)
                finally:
                    base.delete_if_exists(cd)
                    base.delete_if_exists(bl)

                completed_rows = write_checkpoint(output, report)
                completed_for_source = sum(pair in completed_rows for pair in expected)
                print(
                    f"{scenario} {year}: checkpoint source {source_id} "
                    f"({completed_for_source}/{len(expected)} paths)"
                )

            completed_rows = write_checkpoint(output, report)
            successful = len(completed_rows)
            print(f"{scenario} {year}: successful paths {successful} / {len(pairs)}")
            print(f"report: {report}")
            if successful != len(pairs):
                missing = sorted(set(pairs) - set(completed_rows))
                raise RuntimeError(f"{scenario} {year} is incomplete; missing pairs: {missing}")

    print("Complete. Fast vegetation-sensitivity path reports are ready.")
    print("No rasters or existing path reports were changed.")
    arcpy.CheckInExtension("Spatial")


if __name__ == "__main__":
    main()
