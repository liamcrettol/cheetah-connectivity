# Cheetah connectivity project

**Current handoff (4 September 2026):** [Resume at work or home](handoff/2026-09-04/README.md).
Includes verified diagnostic reports, map examples, scripts, spreadsheet context,
and pending decisions. Read this before starting another analysis run.

Analysis code, decision log, and GIS project for a study of temporal structural
connectivity, unprotected pinch points, and monitoring priorities for
free-ranging cheetahs in southern Africa.

**The manuscript, predeclared protocol, and bibliography live in a separate
repo:** [cheetah-connectivity-manuscript](https://github.com/liamcrettol/cheetah-connectivity-manuscript),
connected to Overleaf. This repo carries the ArcGIS project and Git LFS
binaries that Overleaf's GitHub sync can't handle, which is why the split
exists.

## Layout

    gis/          ArcGIS Pro project, geodatabase, raw archive, exports (LFS)
    raw/          arcpy/GEE processing scripts
    handoff/      dated session handoffs, diagnostic reports, QC evidence
    tools/        manifest.py inventories analysis outputs

## What must never be committed

Spatial inputs outside this repo's own conventions. Occurrence data is
sensitive and WDPA cannot be redistributed under its licence. See .gitignore.
