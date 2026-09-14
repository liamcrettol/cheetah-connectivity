r"""Add the candidate core-nuclei layer to the open ArcGIS Pro project.

Run in the ArcGIS Pro Python window:
exec(open(r"C:\Users\liamc\Documents\Codex\2026-09-11\i-want-help\outputs\add_core_nuclei_candidates_to_current_project.py").read())
"""
from datetime import datetime
from pathlib import Path
import arcpy

ROOT = Path(r"C:\Users\liamc\Documents\Codex\2026-09-11\i-want-help")
DATASET = ROOT / "work" / "terrain_sensitivity_31_32.gdb" / "core_nuclei_final_v2"
WINDOWS = ROOT / "work" / "terrain_sensitivity_31_32.gdb" / "local_nuclei_windows_25km"

if not arcpy.Exists(str(DATASET)):
    raise FileNotFoundError(DATASET)
if not arcpy.Exists(str(WINDOWS)):
    raise FileNotFoundError(WINDOWS)
aprx = arcpy.mp.ArcGISProject("CURRENT")
map_object = aprx.activeMap or aprx.listMaps()[0]
backup_folder = Path(aprx.filePath).parent / "backups"
backup_folder.mkdir(parents=True, exist_ok=True)
stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup = backup_folder / f"{Path(aprx.filePath).stem}_before_core_nuclei_candidates_{stamp}.aprx"
aprx.saveACopy(str(backup))

def safe_long_name(layer):
    try:
        return layer.longName
    except AttributeError:
        return ""

for layer in list(map_object.listLayers()):
    label = safe_long_name(layer)
    if label == "Candidate core nuclei · review":
        map_object.removeLayer(layer)
    if label == "Local nuclei windows · 25 km":
        map_object.removeLayer(layer)
layer = map_object.addDataFromPath(str(DATASET))
layer.name = "Candidate core nuclei · review"
layer.visible = True
window_layer = map_object.addDataFromPath(str(WINDOWS))
window_layer.name = "Local nuclei windows · 25 km"
window_layer.visible = True
aprx.save()
print(f"Project backup: {backup}")
print(f"Added Candidate core nuclei · review and Local nuclei windows · 25 km to map {map_object.name}")
print("Symbolize by NUCLEUS_NAME; these groups are candidates for review, not final assignments.")
print(f"ID table: {ROOT / 'outputs' / 'core_nuclei_candidates.csv'}")
