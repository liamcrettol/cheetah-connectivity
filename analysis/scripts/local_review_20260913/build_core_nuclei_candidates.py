"""Create four review-only candidate core groupings for local modeling."""
from pathlib import Path
import csv
import arcpy

ROOT = Path(r"C:\Users\liamc\Documents\Codex\2026-09-11\i-want-help")
SOURCE = ROOT / "work" / "resistances_package_audit" / "commondata" / "cheetah_working.gdb" / "cheetah_core_primary_density051_min500"
OUT_GDB = ROOT / "work" / "terrain_sensitivity_31_32.gdb"
OUT_FC = OUT_GDB / "core_nuclei_final_v2"
OUT_CSV = ROOT / "outputs" / "core_nuclei_candidates.csv"

GROUPS = {
    1: ("Northwest", [1, 9, 13, 17, 18, 24]),
    2: ("Central", [28, 30, 33, 36, 38, 40, 42, 43, 45, 41]),
    3: ("Southern", [49, 50, 53]),
    4: ("Eastern", [26, 27, 31, 32]),
}
ASSIGNMENTS = {core_id: (group_id, name) for group_id, (name, ids) in GROUPS.items() for core_id in ids}

if not arcpy.Exists(str(OUT_GDB)):
    arcpy.management.CreateFileGDB(str(OUT_GDB.parent), OUT_GDB.name)
if arcpy.Exists(str(OUT_FC)):
    arcpy.management.Delete(str(OUT_FC))
arcpy.management.CopyFeatures(str(SOURCE), str(OUT_FC))
arcpy.management.AddField(str(OUT_FC), "NUCLEUS_ID", "SHORT")
arcpy.management.AddField(str(OUT_FC), "NUCLEUS_NAME", "TEXT", field_length=30)
arcpy.management.AddField(str(OUT_FC), "GROUP_STATUS", "TEXT", field_length=20)

seen = set()
with arcpy.da.UpdateCursor(str(OUT_FC), ["CORE_ID", "NUCLEUS_ID", "NUCLEUS_NAME", "GROUP_STATUS"]) as rows:
    for row in rows:
        core_id = int(row[0])
        if core_id not in ASSIGNMENTS:
            raise RuntimeError(f"Core {core_id} was not assigned")
        group_id, name = ASSIGNMENTS[core_id]
        row[1], row[2], row[3] = group_id, name, "APPROVED_FOR_LOCAL"
        rows.updateRow(row)
        seen.add(core_id)
if seen != set(ASSIGNMENTS):
    raise RuntimeError("Candidate assignment did not cover the expected cores")

OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
with OUT_CSV.open("w", newline="", encoding="utf-8-sig") as handle:
    writer = csv.writer(handle)
    writer.writerow(["nucleus_id", "nucleus_name", "core_count", "core_ids", "status"])
    for group_id, (name, ids) in GROUPS.items():
        writer.writerow([group_id, name, len(ids), ",".join(map(str, ids)), "approved_for_local"])

print(f"Feature class: {OUT_FC}")
print(f"Table: {OUT_CSV}")
for group_id, (name, ids) in GROUPS.items():
    print(f"{group_id} {name}: {ids}")
