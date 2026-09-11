import arcpy
from pathlib import Path
project=Path(r"C:\cheetah\resistances\resistances.aprx")
out=Path(r"C:\cheetah\github_repo\arcgis_project\resistances_portable_20260911.ppkx")
if out.exists(): out.unlink()
res=arcpy.management.PackageProject(str(project), str(out), "EXTERNAL", "PROJECT_PACKAGE", "MAXOF", "ALL", None, "Portable Cheetah connectivity resistance ArcGIS Pro project; consolidated data included", "cheetah, connectivity, resistance, ArcGIS Pro", "CURRENT", "TOOLBOXES", "NO_HISTORY_ITEMS", "READ_WRITE", "KEEP_ALL_RELATED_ROWS", "CONVERT_SQLITE")
print(res)
print(out)
