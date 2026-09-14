r"""Add the bounded 500 m 31--32 pilot to the current ArcGIS Pro map."""
from datetime import datetime
from pathlib import Path
import arcpy

ROOT=Path(r"C:\Users\liamc\Documents\Codex\2026-09-11\i-want-help")
GDB=ROOT/"work"/"terrain_sensitivity_31_32.gdb"
PATH=GDB/"path_31_32_pilot_500m"
RES=GDB/"resistance_2024_pilot_500m_31_32"
for p in (PATH,RES):
    if not arcpy.Exists(str(p)): raise FileNotFoundError(p)
aprx=arcpy.mp.ArcGISProject("CURRENT"); m=aprx.activeMap or aprx.listMaps()[0]
backup=Path(aprx.filePath).parent/"backups"/f"{Path(aprx.filePath).stem}_before_500m_pilot_{datetime.now():%Y%m%d_%H%M%S}.aprx"; backup.parent.mkdir(parents=True,exist_ok=True); aprx.saveACopy(str(backup))
for lyr in list(m.listLayers()):
    try: label=lyr.longName
    except AttributeError: label=""
    if label in ("31–32 · 500 m p90 terrain pilot","Resistance · 500 m p90 terrain pilot"):
        m.removeLayer(lyr)
line=m.addDataFromPath(str(PATH)); line.name="31–32 · 500 m p90 terrain pilot"; line.visible=True
raster=m.addDataFromPath(str(RES)); raster.name="Resistance · 500 m p90 terrain pilot"; raster.visible=False
aprx.save(); print(f"Project backup: {backup}"); print("Added 500 m pilot path and hidden resistance raster.")
