"""Run inside ArcGIS Pro: create a SEPARATE diagnostic map, no solver.
Backs up and saves the project; does not alter existing maps or GIS datasets.
"""
import datetime as task_datetime
from pathlib import Path
import arcpy

GDB = Path(r'C:\cheetah\diagnostics\vcf_v2_pair17_24_2016_20260903_155703_741091\test.gdb')


def main():
    names=['source_core17','destination_core24','saved_old_route','candidate_route17_24']
    for name in names:
        if not arcpy.Exists(str(GDB/name)):
            raise FileNotFoundError(str(GDB/name))
    aprx=arcpy.mp.ArcGISProject('CURRENT')
    stamp=task_datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    backups=Path(r'C:\cheetah\backups');backups.mkdir(parents=True,exist_ok=True)
    backup=backups/f'{Path(aprx.filePath).stem}_before_pilot_comparison_{stamp}.aprx'
    aprx.saveACopy(str(backup))
    m=aprx.createMap('DIAGNOSTIC - VCF 17-24 2016 - '+stamp,'MAP')
    m.spatialReference=arcpy.Describe(str(GDB/'saved_old_route')).spatialReference
    for name,label in [('source_core17','Core 17 - fixed source'),('destination_core24','Core 24 - fixed destination')]:
        layer=m.addDataFromPath(str(GDB/name));layer.name=label
        sym=layer.symbology
        sym.updateRenderer('SimpleRenderer')
        sym.renderer.symbol.color={'RGB':[210,214,218,25]}
        sym.renderer.symbol.outlineColor={'RGB':[80,85,90,100]}
        sym.renderer.symbol.outlineWidth=1.2
        layer.symbology=sym
    for name,label,color in [('saved_old_route','OLD route - orange',[213,94,0,100]),
                             ('candidate_route17_24','CANDIDATE route - blue',[0,114,178,100])]:
        layer=m.addDataFromPath(str(GDB/name));layer.name=label
        sym=layer.symbology;sym.updateRenderer('SimpleRenderer')
        sym.renderer.symbol.color={'RGB':color};sym.renderer.symbol.width=3
        layer.symbology=sym
    extents=[arcpy.Describe(str(GDB/name)).extent for name in ('saved_old_route','candidate_route17_24')]
    extent=arcpy.Extent(min(e.XMin for e in extents)-5000,min(e.YMin for e in extents)-5000,
                        max(e.XMax for e in extents)+5000,max(e.YMax for e in extents)+5000)
    m.defaultCamera.setExtent(extent)
    aprx.save()
    m.openView()
    print('Backup:',backup)
    print('Opened:',m.name)
    print('Orange = old, blue = candidate. Existing maps and source data unchanged. No solver run.')


if __name__=='__main__':
    main()
