"""Repair the diagnostic renderer's mismatched field and class values."""
from pathlib import Path
from datetime import datetime
import arcpy

def main():
    aprx = arcpy.mp.ArcGISProject('CURRENT')
    matches = [l for m in aprx.listMaps('Map') for l in m.listLayers()
               if l.name == 'vcf_missing_water_context_v1']
    if len(matches) != 1:
        raise RuntimeError(f'Expected one diagnostic layer, found {len(matches)}')
    layer = matches[0]
    backup = Path(r'C:\cheetah\backups') / ('Resistance_before_renderer_repair_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.aprx')
    aprx.saveACopy(str(backup))
    sym = layer.symbology
    expected = {'Persistent water context', 'Persistent land context', 'Unresolved / mixed context'}
    values = {str(v) for group in sym.colorizer.groups for item in group.items for v in item.values}
    if values != expected:
        raise RuntimeError(f'Unexpected renderer values: {values}; nothing changed')
    # Change only the field: the existing text values match CLASS_NAME exactly.
    cim = layer.getDefinition('V3')
    cim.colorizer.fieldName = 'CLASS_NAME'
    layer.setDefinition(cim)
    after = layer.symbology
    if after.colorizer.field != 'CLASS_NAME':
        raise RuntimeError('Renderer field repair did not persist')
    layer.visible = True
    aprx.save()
    print('Fixed: text class values now match CLASS_NAME.')
    print('backup:', backup)
    print('Raster data and map extent unchanged.')

if __name__ == '__main__':
    main()
