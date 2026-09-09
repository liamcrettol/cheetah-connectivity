"""Fast historical primary paths: one CostDistance run per source core/year."""

from datetime import datetime
from pathlib import Path
import csv
import importlib
import os
import sys
import arcpy
from arcpy.sa import CostDistance, CostPathAsPolyline

OUTPUTS = r"C:\Users\lcrettol\Documents\Codex\2026-08-25\i-am-working-on-this-spreadsheet\outputs"
if OUTPUTS not in sys.path:
    sys.path.insert(0, OUTPUTS)
import create_reference_least_cost_paths as base

YEARS = (2012, 2016, 2020)


def main():
    arcpy.CheckOutExtension("Spatial")
    arcpy.env.overwriteOutput = True
    arcpy.env.snapRaster = base.SNAP
    arcpy.env.cellSize = base.SNAP
    arcpy.env.extent = base.SNAP
    arcpy.env.mask = base.MASK
    arcpy.env.outputCoordinateSystem = arcpy.Describe(base.SNAP).spatialReference
    arcpy.env.parallelProcessingFactor = "75%"
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    maps = aprx.listMaps("Map")
    m = maps[0] if maps else aprx.activeMap
    if m is None:
        raise RuntimeError("No active map found")
    group = base.get_group(m)
    pairs = sorted({tuple(sorted((int(a), int(b)))) for a, b in arcpy.da.SearchCursor(base.LINKS, ["FROM_ID", "TO_ID"])})
    print(f"selected links: {len(pairs)}")

    for year in YEARS:
        resistance = os.path.join(base.GDB, f"resistance_primary_unfenced_combined_{year}")
        output = os.path.join(base.GDB, f"least_cost_paths_primary_combined_{year}")
        report = Path(r"C:\cheetah\reports") / f"least_cost_paths_primary_combined_{year}.csv"
        for required in (resistance, base.CORES, base.LINKS, base.SNAP, base.MASK):
            base.require(required)
        base.remove_map_references(m, output)
        base.delete_if_exists(output)
        arcpy.management.CreateFeatureclass(base.GDB, Path(output).name, "POLYLINE", spatial_reference=arcpy.Describe(base.CORES).spatialReference)
        for name, field_type, length in (("FROM_ID", "LONG", None), ("TO_ID", "LONG", None), ("SCENARIO", "TEXT", 40), ("PATH_KM", "DOUBLE", None), ("COST_RAW", "DOUBLE", None), ("STATUS", "TEXT", 20)):
            arcpy.management.AddField(output, name, field_type, **({"field_length": length} if length else {}))
        src = "fast_temporal_source"
        dst = "fast_temporal_destination"
        arcpy.management.MakeFeatureLayer(base.CORES, src)
        arcpy.management.MakeFeatureLayer(base.CORES, dst)
        report_rows = []
        with arcpy.da.InsertCursor(output, ["SHAPE@", "FROM_ID", "TO_ID", "SCENARIO", "PATH_KM", "COST_RAW", "STATUS"]) as insert:
            for source_id in sorted({p[0] for p in pairs}):
                print(f"{year}: source core {source_id}")
                arcpy.management.SelectLayerByAttribute(src, "NEW_SELECTION", f"CORE_ID = {source_id}")
                token = f"fast_{year}_{source_id}"
                cd = os.path.join(base.GDB, token + "_cd")
                bl = os.path.join(base.GDB, token + "_bl")
                base.delete_if_exists(cd); base.delete_if_exists(bl)
                try:
                    CostDistance(src, resistance, maximum_distance=None, out_backlink_raster=bl).save(cd)
                    for from_id, to_id in [p for p in pairs if p[0] == source_id]:
                        arcpy.management.SelectLayerByAttribute(dst, "NEW_SELECTION", f"CORE_ID = {to_id}")
                        path_fc = os.path.join(base.GDB, f"{token}_{to_id}_path")
                        base.delete_if_exists(path_fc)
                        try:
                            CostPathAsPolyline(dst, cd, bl, path_fc, "BEST_SINGLE", "CORE_ID")
                            geometry, path_cost = base.first_path_geometry(path_fc)
                            path_km = float(geometry.length / 1000.0)
                            insert.insertRow([geometry, from_id, to_id, f"primary_unfenced_{year}", path_km, path_cost, "OK"])
                            report_rows.append([from_id, to_id, path_km, "" if path_cost is None else path_cost, "OK"])
                        except Exception as exc:
                            message = str(exc).replace("\n", " | ")
                            report_rows.append([from_id, to_id, "", "", "FAILED: " + message])
                            print(f"WARNING: {from_id}-{to_id}: {message}")
                        finally:
                            base.delete_if_exists(path_fc)
                finally:
                    base.delete_if_exists(cd); base.delete_if_exists(bl)
        report.parent.mkdir(parents=True, exist_ok=True)
        with report.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle)
            writer.writerow(["from_core", "to_core", "path_length_km", "accumulated_cost_raw", "status"])
            writer.writerows(report_rows)
        loose = m.addDataFromPath(output)
        grouped = m.addLayerToGroup(group, loose, "BOTTOM")
        m.removeLayer(loose)
        if grouped:
            grouped[0].visible = False
        print(f"{year}: successful paths {sum(r[-1] == 'OK' for r in report_rows)} / {len(pairs)}")
        print(f"report: {report}")
    aprx.save()
    arcpy.CheckInExtension("Spatial")
    print("Complete. Historical primary path reports are ready for temporal threat calculation.")


if __name__ == "__main__":
    main()
