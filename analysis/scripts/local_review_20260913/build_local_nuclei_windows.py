"""Build four buffered local-analysis windows from the approved nuclei."""
from pathlib import Path
import arcpy

ROOT = Path(r"C:\Users\liamc\Documents\Codex\2026-09-11\i-want-help")
GDB = ROOT / "work" / "terrain_sensitivity_31_32.gdb"
SOURCE = GDB / "core_nuclei_final_v2"
DISSOLVED = GDB / "local_nuclei_dissolved"
WINDOWS = GDB / "local_nuclei_windows_25km"

if not arcpy.Exists(str(SOURCE)):
    raise FileNotFoundError(SOURCE)
for dataset in (DISSOLVED, WINDOWS):
    if arcpy.Exists(str(dataset)):
        arcpy.management.Delete(str(dataset))

arcpy.management.Dissolve(
    str(SOURCE), str(DISSOLVED), ["NUCLEUS_ID", "NUCLEUS_NAME"],
    multi_part="MULTI_PART", unsplit_lines="DISSOLVE_LINES"
)
arcpy.analysis.Buffer(
    str(DISSOLVED), str(WINDOWS), "25 Kilometers",
    line_side="FULL", line_end_type="ROUND", dissolve_option="LIST",
    dissolve_field=["NUCLEUS_ID", "NUCLEUS_NAME"], method="PLANAR"
)
arcpy.management.AddField(str(WINDOWS), "WINDOW_KM", "DOUBLE")
arcpy.management.CalculateField(str(WINDOWS), "WINDOW_KM", "25", "PYTHON3")
print(f"Created: {WINDOWS}")
print("Four local windows are ready for review; no resistance analysis was run.")
