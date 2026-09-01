# GitHub → ArcGIS Pro setup

The script `sync_github_to_arcgis_pro.py` safely updates a GitHub checkout, creates the workbook's expected `C:\cheetah` folder structure, creates a working file geodatabase, connects those folders to the ArcGIS Pro project, and adds supported GIS datasets without duplicating layers already in the map.

## Before running

1. Install Git. If the repository uses Git LFS, install Git LFS too.
2. Open **ArcGIS Pro → Python Command Prompt**, so the script runs with `arcpy`.
3. Know your GitHub repository URL. For a private repository, authenticate through Git Credential Manager or SSH; do not paste a token into the script.

## Recommended command

```powershell
python "C:\Users\lcrettol\Documents\Codex\2026-08-25\i-am-working-on-this-spreadsheet\outputs\sync_github_to_arcgis_pro.py" `
  --repo-url "https://github.com/YOUR-ACCOUNT/YOUR-REPOSITORY.git" `
  --project-root "C:\cheetah" `
  --aprx "C:\cheetah\cheetah_connectivity.aprx" `
  --map-name "Map"
```

If running from an ArcGIS Pro Notebook or script tool against the open project, use `--aprx CURRENT`.

The script refuses to pull over uncommitted repository changes, makes a timestamped `.aprx` backup, uses `git pull --ff-only`, and writes `C:\cheetah\github_arcgis_sync_report.json` with added, skipped, failed, broken, and missing-manifest items.

## Important project constraint

The spreadsheet's **Conventions** tab says rasters, geodatabases, shapefiles, and `raw/` are excluded from GitHub. If that is still true, the script will pull the code/protocol/manifest but will correctly report that the GIS data itself is missing. Those files need a separate archive, Git LFS, release assets, or a reproducible download/export script.
