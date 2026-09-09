"""Create unfenced-reference least-cost paths for the 45 selected core pairs.

Run inside the ArcGIS Pro Python window. The selected straight-line network is
used only to identify pairs. Paths are calculated on the unfenced resistance
surface and existing datasets are preserved.
"""

from datetime import datetime
from pathlib import Path
import csv
import os

import arcpy
from arcpy.sa import CostDistance, CostPathAsPolyline

GDB = r"C:\cheetah\gdb\cheetah_working.gdb"
SNAP = r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah_connectivity.gdb\snapgrid_1km"
MASK = r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah_connectivity.gdb\extent_buffered"
CORES = os.path.join(GDB, "cheetah_core_primary_density051_min500")
LINKS = os.path.join(GDB, "cheetah_core_neighbor_links")
RESISTANCE = os.path.join(GDB, "resistance_base_unfenced_1_10")
OUTPUT = os.path.join(GDB, "least_cost_paths_reference_unfenced")
REPORT = Path(r"C:\cheetah\reports\least_cost_paths_reference_unfenced.csv")
BACKUPS = Path(r"C:\cheetah\backups")
PARENT = "Cheetah project"
GROUP = "15 Connectivity links · modeled"
SCENARIO_LABEL = "reference_unfenced"
PAIRS_OVERRIDE = None


def require(path):
    if not arcpy.Exists(path):
        raise FileNotFoundError(path)


def remove_map_references(map_object, dataset):
    target = os.path.normcase(os.path.normpath(dataset))
    for layer in list(map_object.listLayers()):
        try:
            if layer.supports("DATASOURCE") and os.path.normcase(os.path.normpath(layer.dataSource)) == target:
                map_object.removeLayer(layer)
        except Exception:
            pass


def get_group(map_object):
    parents = [x for x in map_object.listLayers() if x.isGroupLayer and x.longName == PARENT]
    if len(parents) != 1:
        raise RuntimeError(f"Expected one {PARENT!r} group; found {len(parents)}")
    wanted = PARENT + "\\" + GROUP
    groups = [x for x in map_object.listLayers() if x.isGroupLayer and x.longName == wanted]
    return groups[0] if groups else map_object.createGroupLayer(GROUP, parents[0])


def delete_if_exists(path):
    if arcpy.Exists(path):
        arcpy.management.Delete(path)


def first_path_geometry(path_fc):
    fields = [f.name for f in arcpy.ListFields(path_fc)]
    cost_field = next((f for f in fields if f.upper() in ("PATHCOST", "PATH_COST")), None)
    cursor_fields = ["SHAPE@"] + ([cost_field] if cost_field else [])
    best = None
    with arcpy.da.SearchCursor(path_fc, cursor_fields) as rows:
        for row in rows:
            geometry = row[0]
            cost = float(row[1]) if cost_field and row[1] is not None else None
            candidate = (geometry, cost)
            if best is None or geometry.length < best[0].length:
                best = candidate
    if best is None:
        raise RuntimeError("CostPathAsPolyline returned no path feature")
    return best


def main():
    for dataset in (SNAP, MASK, CORES, LINKS, RESISTANCE):
        require(dataset)
    arcpy.CheckOutExtension("Spatial")
    arcpy.env.overwriteOutput = True
    arcpy.env.snapRaster = SNAP
    arcpy.env.cellSize = SNAP
    arcpy.env.extent = SNAP
    arcpy.env.mask = MASK
    arcpy.env.outputCoordinateSystem = arcpy.Describe(SNAP).spatialReference
    arcpy.env.parallelProcessingFactor = "75%"

    aprx = arcpy.mp.ArcGISProject("CURRENT")
    maps = aprx.listMaps("Map")
    map_object = maps[0] if maps else aprx.activeMap
    if map_object is None:
        raise RuntimeError("No active map was found")
    target_group = get_group(map_object)

    BACKUPS.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUPS / f"{Path(aprx.filePath).stem}_before_reference_lcp_{stamp}.aprx"
    aprx.saveACopy(str(backup))
    print(f"backup: {backup}")

    pairs = []
    with arcpy.da.SearchCursor(LINKS, ["FROM_ID", "TO_ID"]) as rows:
        for from_id, to_id in rows:
            pairs.append((int(from_id), int(to_id)))
    pairs = sorted(set(pairs))
    if PAIRS_OVERRIDE is not None:
        wanted_pairs = {tuple(sorted((int(a), int(b)))) for a, b in PAIRS_OVERRIDE}
        pairs = [pair for pair in pairs if tuple(sorted(pair)) in wanted_pairs]
        missing = wanted_pairs - {tuple(sorted(pair)) for pair in pairs}
        if missing:
            raise RuntimeError(f"Requested pairs were not found in selected links: {sorted(missing)}")
    if not pairs:
        raise RuntimeError("No selected core pairs were found")
    print(f"selected pairs: {len(pairs)}")

    remove_map_references(map_object, OUTPUT)
    delete_if_exists(OUTPUT)
    spatial_reference = arcpy.Describe(CORES).spatialReference
    arcpy.management.CreateFeatureclass(GDB, Path(OUTPUT).name, "POLYLINE", spatial_reference=spatial_reference)
    for name, field_type, length in (
        ("FROM_ID", "LONG", None), ("TO_ID", "LONG", None),
        ("SCENARIO", "TEXT", 40), ("PATH_KM", "DOUBLE", None),
        ("COST_RAW", "DOUBLE", None), ("STATUS", "TEXT", 20),
    ):
        kwargs = {"field_length": length} if length else {}
        arcpy.management.AddField(OUTPUT, name, field_type, **kwargs)

    source_layer = "reference_lcp_source_core"
    destination_layer = "reference_lcp_destination_core"
    arcpy.management.MakeFeatureLayer(CORES, source_layer)
    arcpy.management.MakeFeatureLayer(CORES, destination_layer)
    report_rows = []

    with arcpy.da.InsertCursor(OUTPUT, ["SHAPE@", "FROM_ID", "TO_ID", "SCENARIO", "PATH_KM", "COST_RAW", "STATUS"]) as insert:
        for number, (from_id, to_id) in enumerate(pairs, 1):
            print(f"{number}/{len(pairs)}: core {from_id} -> core {to_id}")
            arcpy.management.SelectLayerByAttribute(source_layer, "NEW_SELECTION", f"CORE_ID = {from_id}")
            arcpy.management.SelectLayerByAttribute(destination_layer, "NEW_SELECTION", f"CORE_ID = {to_id}")
            if int(arcpy.management.GetCount(source_layer)[0]) != 1 or int(arcpy.management.GetCount(destination_layer)[0]) != 1:
                raise RuntimeError(f"Could not select exactly one feature for pair {from_id}-{to_id}")

            token = f"lcp_{from_id}_{to_id}"
            cost_distance = os.path.join(GDB, token + "_cd")
            backlink = os.path.join(GDB, token + "_bl")
            path_fc = os.path.join(GDB, token + "_path")
            for temp in (cost_distance, backlink, path_fc):
                delete_if_exists(temp)
            try:
                CostDistance(
                    source_layer,
                    RESISTANCE,
                    maximum_distance=None,
                    out_backlink_raster=backlink,
                ).save(cost_distance)
                CostPathAsPolyline(
                    destination_layer,
                    cost_distance,
                    backlink,
                    path_fc,
                    "BEST_SINGLE",
                    "CORE_ID",
                )
                geometry, path_cost = first_path_geometry(path_fc)
                path_km = float(geometry.length / 1000.0)
                insert.insertRow([geometry, from_id, to_id, SCENARIO_LABEL, path_km, path_cost, "OK"])
                report_rows.append([from_id, to_id, path_km, "" if path_cost is None else path_cost, "OK"])
            except Exception as exc:
                message = str(exc).replace("\n", " | ")
                report_rows.append([from_id, to_id, "", "", "FAILED: " + message])
                print(f"WARNING: pair {from_id}-{to_id} failed: {message}")
            finally:
                for temp in (path_fc, cost_distance, backlink):
                    try:
                        delete_if_exists(temp)
                    except Exception:
                        pass

    with REPORT.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["from_core", "to_core", "path_length_km", "accumulated_cost_raw", "status"])
        writer.writerows(report_rows)

    successful = int(arcpy.management.GetCount(OUTPUT)[0])
    if successful:
        loose = map_object.addDataFromPath(OUTPUT)
        grouped = map_object.addLayerToGroup(target_group, loose, "BOTTOM")
        map_object.removeLayer(loose)
        if grouped:
            grouped[0].visible = True
            target_group.visible = True
    aprx.save()
    arcpy.CheckInExtension("Spatial")
    print(f"successful paths: {successful}")
    print(f"failed paths: {len(pairs) - successful}")
    print(f"paths: {OUTPUT}")
    print(f"report: {REPORT}")
    print("Complete. These are unfenced-reference least-cost paths; no existing datasets were changed.")


if __name__ == "__main__":
    main()
