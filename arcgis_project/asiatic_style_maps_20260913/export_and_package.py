import arcpy, re
from pathlib import Path
project = Path(r"C:\Users\lcrettol\OneDrive - Pineview Water System\Documents\ArcGIS\Packages\asiatic_style_maps_20260913_9fee94\p30\asiatic_style_maps.aprx")
outdir = Path(r"C:\cheetah\github_repo\arcgis_project\asiatic_style_maps_20260913")
outdir.mkdir(parents=True, exist_ok=True)
p = arcpy.mp.ArcGISProject(str(project))
seen=[]
for layout in p.listLayouts():
    name = re.sub(r'[^A-Za-z0-9]+','_',layout.name).strip('_').lower()
    pdf = outdir / f"{name}.pdf"
    png = outdir / f"{name}.png"
    if pdf.exists(): pdf.unlink()
    if png.exists(): png.unlink()
    layout.exportToPDF(str(pdf), resolution=300)
    layout.exportToPNG(str(png), resolution=300)
    seen.append((layout.name, pdf.name, png.name))
print(f"exported {len(seen)} layouts")
for x in seen: print(x)
ppkx = outdir / "asiatic_style_maps_portable_20260915.ppkx"
if ppkx.exists(): ppkx.unlink()
arcpy.management.PackageProject(str(project), str(ppkx), "EXTERNAL", "PROJECT_PACKAGE", "MAXOF", "ALL", None, "Portable Asiatic style maps ArcGIS Pro project; consolidated project data included", "Asiatic cheetah, connectivity, maps, ArcGIS Pro", "CURRENT", "TOOLBOXES", "NO_HISTORY_ITEMS", "READ_WRITE", "KEEP_ALL_RELATED_ROWS", "CONVERT_SQLITE")
print(f"packaged {ppkx}")
