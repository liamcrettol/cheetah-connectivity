#!/usr/bin/env python3
"""Synchronize a GitHub repository and load its GIS data into ArcGIS Pro.

Run this with the Python environment installed with ArcGIS Pro. The script is
safe by default: it refuses to pull over uncommitted repository changes,
creates a timestamped .aprx backup, and does not delete local files or layers.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence


# Edit this once if you prefer to run without --repo-url.
REPO_URL = ""

DEFAULT_PROJECT_ROOT = Path(r"C:\cheetah")
DEFAULT_REPO_DIRNAME = "github_repo"
DEFAULT_GDB_NAME = "cheetah_working.gdb"

GIS_FILE_EXTENSIONS = {
    ".tif",
    ".tiff",
    ".img",
    ".crf",
    ".shp",
    ".geojson",
    ".kml",
    ".kmz",
    ".lyrx",
    ".sde",
}


class SetupError(RuntimeError):
    """A user-correctable setup problem."""


def log(message: str) -> None:
    print(message, flush=True)


def run(command: Sequence[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    log("  $ " + " ".join(command))
    return subprocess.run(
        list(command),
        cwd=str(cwd) if cwd else None,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def git_output(repo_dir: Path, *args: str) -> str:
    return run(["git", *args], cwd=repo_dir).stdout.strip()


def sync_repository(
    repo_url: str,
    repo_dir: Path,
    branch: str,
    allow_dirty: bool,
    skip_pull: bool,
) -> dict[str, object]:
    if shutil.which("git") is None:
        raise SetupError("Git is not installed or is not available on PATH.")

    if (repo_dir / ".git").is_dir():
        origin = git_output(repo_dir, "remote", "get-url", "origin")
        if repo_url and origin.rstrip("/") != repo_url.rstrip("/"):
            raise SetupError(
                f"Existing checkout uses origin {origin!r}, not {repo_url!r}. "
                "Use the correct --repo-dir or --repo-url."
            )
        if not allow_dirty:
            dirty = git_output(repo_dir, "status", "--porcelain")
            if dirty:
                raise SetupError(
                    f"Repository has uncommitted changes at {repo_dir}. Commit or stash "
                    "them, or rerun with --allow-dirty."
                )
        else:
            log("  skipping slow working-tree status scan (--allow-dirty)")
        if not skip_pull:
            git_output(repo_dir, "fetch", "origin", branch)
            git_output(repo_dir, "checkout", branch)
            git_output(repo_dir, "pull", "--ff-only", "origin", branch)
    else:
        if not repo_url:
            raise SetupError(
                "No repository exists at --repo-dir and no repository URL was supplied. "
                "Pass --repo-url or set REPO_URL at the top of this script."
            )
        if repo_dir.exists() and any(repo_dir.iterdir()):
            raise SetupError(f"Clone destination is not empty: {repo_dir}")
        repo_dir.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--branch", branch, "--single-branch", repo_url, str(repo_dir)])
        origin = repo_url

    lfs_used = False
    attributes = repo_dir / ".gitattributes"
    if attributes.exists() and "filter=lfs" in attributes.read_text(encoding="utf-8", errors="ignore"):
        if shutil.which("git") is None:
            raise SetupError("Git LFS files are declared, but Git is unavailable.")
        probe = subprocess.run(
            ["git", "lfs", "version"],
            cwd=str(repo_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        if probe.returncode != 0:
            raise SetupError("This repository uses Git LFS. Install Git LFS, then rerun.")
        git_output(repo_dir, "lfs", "pull")
        lfs_used = True

    return {
        "repo_dir": str(repo_dir),
        "origin": origin,
        "branch": branch,
        "commit": git_output(repo_dir, "rev-parse", "HEAD"),
        "git_lfs_used": lfs_used,
    }


def create_project_structure(project_root: Path, arcpy) -> dict[str, Path]:
    paths = {
        "root": project_root,
        "raw": project_root / "raw",
        "gdb": project_root / "gdb",
        "rasters": project_root / "rasters",
        "circuitscape": project_root / "circuitscape",
        "figures": project_root / "figures",
        "backups": project_root / "backups",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)

    working_gdb = paths["gdb"] / DEFAULT_GDB_NAME
    if not working_gdb.exists():
        arcpy.management.CreateFileGDB(str(working_gdb.parent), working_gdb.name)
    paths["working_gdb"] = working_gdb
    return paths


def locate_aprx(aprx_arg: str, project_root: Path, repo_dir: Path) -> str:
    if aprx_arg.upper() == "CURRENT":
        return "CURRENT"
    if aprx_arg.lower() != "auto":
        candidate = Path(aprx_arg).expanduser().resolve()
        if not candidate.exists():
            raise SetupError(f"ArcGIS Pro project does not exist: {candidate}")
        return str(candidate)

    candidates = sorted(
        {p.resolve() for base in (project_root, repo_dir) for p in base.glob("*.aprx")}
    )
    preferred = [p for p in candidates if p.name.lower() == "cheetah_connectivity.aprx"]
    if len(preferred) == 1:
        return str(preferred[0])
    if len(candidates) == 1:
        return str(candidates[0])
    if not candidates:
        raise SetupError(
            "No .aprx was found. Pass --aprx CURRENT from an ArcGIS Pro Notebook/"
            "Python window, or pass the full path to your .aprx file."
        )
    raise SetupError(
        "More than one .aprx was found; choose one with --aprx:\n  "
        + "\n  ".join(str(p) for p in candidates)
    )


def normalize(path: str | Path) -> str:
    return os.path.normcase(os.path.normpath(str(path)))


def existing_data_sources(target_map) -> set[str]:
    sources: set[str] = set()
    for item in [*target_map.listLayers(), *target_map.listTables()]:
        try:
            if item.supports("DATASOURCE"):
                sources.add(normalize(item.dataSource))
        except Exception:
            continue
    return sources


def walk_regular_gis_files(root: Path, include_csv: bool) -> Iterable[Path]:
    extensions = set(GIS_FILE_EXTENSIONS)
    if include_csv:
        extensions.add(".csv")
    if not root.exists():
        return

    for current, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames if d != ".git" and not d.lower().endswith(".gdb")
        ]
        for filename in filenames:
            path = Path(current) / filename
            if path.suffix.lower() in extensions:
                yield path.resolve()


def walk_geodatabases(root: Path, arcpy) -> Iterable[Path]:
    if not root.exists():
        return
    gdbs: list[Path] = []
    for current, dirnames, _ in os.walk(root):
        for dirname in list(dirnames):
            if dirname.lower().endswith(".gdb"):
                gdbs.append((Path(current) / dirname).resolve())
                dirnames.remove(dirname)
        if ".git" in dirnames:
            dirnames.remove(".git")

    for gdb in sorted(gdbs):
        for dirpath, _, filenames in arcpy.da.Walk(
            str(gdb), datatype=["FeatureClass", "RasterDataset", "Table"]
        ):
            for filename in filenames:
                yield Path(dirpath) / filename


def discover_datasets(scan_roots: Iterable[Path], arcpy, include_csv: bool) -> list[Path]:
    discovered: dict[str, Path] = {}
    for root in scan_roots:
        for path in walk_regular_gis_files(root, include_csv):
            discovered.setdefault(normalize(path), path)
        for path in walk_geodatabases(root, arcpy):
            discovered.setdefault(normalize(path), path)
    return sorted(discovered.values(), key=lambda p: normalize(p))


def choose_map(aprx, map_name: str):
    if map_name:
        matches = aprx.listMaps(map_name)
        if matches:
            return matches[0]
    if aprx.activeMap is not None:
        return aprx.activeMap
    maps = aprx.listMaps()
    return maps[0] if maps else aprx.createMap(map_name or "Cheetah Connectivity")


def add_datasets(target_map, datasets: Iterable[Path], arcpy) -> tuple[list[str], list[dict[str, str]], list[str]]:
    existing = existing_data_sources(target_map)
    added: list[str] = []
    failed: list[dict[str, str]] = []
    skipped: list[str] = []

    for path in datasets:
        key = normalize(path)
        if key in existing:
            skipped.append(str(path))
            continue
        try:
            if path.suffix.lower() == ".lyrx":
                target_map.addLayer(arcpy.mp.LayerFile(str(path)))
            else:
                target_map.addDataFromPath(str(path))
            existing.add(key)
            added.append(str(path))
            log(f"  added: {path}")
        except Exception as exc:
            failed.append({"path": str(path), "error": str(exc)})
            log(f"  WARNING: could not add {path}: {exc}")
    return added, failed, skipped


def configure_project_connections(aprx, paths: dict[str, Path], repo_dir: Path) -> None:
    project_root = paths["root"].resolve()
    wanted = [project_root, repo_dir.resolve(), paths["raw"], paths["rasters"], paths["circuitscape"], paths["figures"]]

    by_path: dict[str, dict[str, object]] = {}
    for item in aprx.folderConnections:
        connection = item.get("connectionString")
        if connection:
            by_path[normalize(connection)] = {
                "connectionString": connection,
                "alias": item.get("alias", ""),
                "isHomeFolder": False,
            }
    for folder in wanted:
        by_path[normalize(folder)] = {
            "connectionString": str(folder),
            "alias": "Cheetah project" if folder == project_root else "",
            "isHomeFolder": folder == project_root,
        }
    aprx.homeFolder = str(project_root)
    aprx.updateFolderConnections(list(by_path.values()), validate=True)

    working_gdb = paths["working_gdb"].resolve()
    databases: dict[str, dict[str, object]] = {}
    for item in aprx.databases:
        db_path = item.get("databasePath")
        if db_path:
            databases[normalize(db_path)] = {
                "databasePath": db_path,
                "isDefaultDatabase": False,
            }
    databases[normalize(working_gdb)] = {
        "databasePath": str(working_gdb),
        "isDefaultDatabase": True,
    }
    aprx.updateDatabases(list(databases.values()), validate=True)
    aprx.defaultGeodatabase = str(working_gdb)


def manifest_missing_paths(repo_dir: Path, project_root: Path) -> list[str]:
    manifests = sorted(repo_dir.rglob("manifest.csv"))
    if not manifests:
        return []
    common_columns = ("relative_path", "path", "file_path", "filepath", "file")
    missing: list[str] = []
    for manifest in manifests:
        try:
            with manifest.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                if not reader.fieldnames:
                    continue
                column = next((c for c in common_columns if c in reader.fieldnames), None)
                if not column:
                    continue
                for row in reader:
                    value = (row.get(column) or "").strip()
                    if not value:
                        continue
                    relative = Path(value)
                    candidates = [repo_dir / relative, project_root / relative]
                    if not any(candidate.exists() for candidate in candidates):
                        missing.append(value)
        except (OSError, csv.Error):
            continue
    return sorted(set(missing))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Clone/update a GitHub repository and load its GIS datasets into ArcGIS Pro."
    )
    parser.add_argument("--repo-url", default=REPO_URL, help="HTTPS or SSH GitHub repository URL.")
    parser.add_argument("--project-root", type=Path, default=DEFAULT_PROJECT_ROOT)
    parser.add_argument("--repo-dir", type=Path, help="Checkout directory; defaults to <project-root>\\github_repo.")
    parser.add_argument("--branch", default="main")
    parser.add_argument(
        "--aprx",
        default="auto",
        help="Full .aprx path, CURRENT when run inside ArcGIS Pro, or auto.",
    )
    parser.add_argument("--map-name", default="Map", help="Target map name; falls back to active/first map.")
    parser.add_argument("--allow-dirty", action="store_true", help="Allow a pull when the checkout has local changes.")
    parser.add_argument("--skip-pull", action="store_true", help="Use the existing checkout without fetching/pulling.")
    parser.add_argument("--include-csv", action="store_true", help="Also add CSV files as standalone tables.")
    parser.add_argument(
        "--repo-only",
        action="store_true",
        help="Scan only the GitHub checkout, not existing raw/rasters/gdb project folders.",
    )
    parser.add_argument("--no-backup", action="store_true", help="Do not save a timestamped .aprx backup.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = args.project_root.expanduser().resolve()
    repo_dir = (args.repo_dir or project_root / DEFAULT_REPO_DIRNAME).expanduser().resolve()

    try:
        import arcpy  # type: ignore
    except ImportError as exc:
        raise SetupError(
            "arcpy is unavailable. Run this with ArcGIS Pro's Python environment "
            "(propy.bat), an ArcGIS Pro Notebook, or a script tool."
        ) from exc

    log("1/5 Synchronizing GitHub repository")
    repo_info = sync_repository(
        args.repo_url, repo_dir, args.branch, args.allow_dirty, args.skip_pull
    )

    log("2/5 Creating/confirming project folders and working geodatabase")
    paths = create_project_structure(project_root, arcpy)

    log("3/5 Opening and backing up the ArcGIS Pro project")
    aprx_reference = locate_aprx(args.aprx, project_root, repo_dir)
    aprx = arcpy.mp.ArcGISProject(aprx_reference)
    if aprx.isReadOnly:
        raise SetupError(
            "The .aprx is read-only, usually because it is open in another ArcGIS Pro "
            "instance. Close it, or run inside that project with --aprx CURRENT."
        )
    backup_path = None
    if not args.no_backup:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = paths["backups"] / f"{Path(aprx.filePath).stem}_before_github_sync_{stamp}.aprx"
        aprx.saveACopy(str(backup_path))

    configure_project_connections(aprx, paths, repo_dir)
    target_map = choose_map(aprx, args.map_name)

    log("4/5 Discovering and adding GIS datasets")
    scan_roots = [repo_dir]
    if not args.repo_only:
        scan_roots.extend([paths["raw"], paths["rasters"], paths["gdb"]])
    datasets = discover_datasets(scan_roots, arcpy, args.include_csv)
    added, failed, skipped = add_datasets(target_map, datasets, arcpy)

    aprx.save()
    broken = [getattr(item, "name", str(item)) for item in aprx.listBrokenDataSources()]
    missing_manifest = manifest_missing_paths(repo_dir, project_root)

    report = {
        "completed_at": datetime.now().isoformat(timespec="seconds"),
        "repository": repo_info,
        "project_root": str(project_root),
        "aprx": aprx.filePath,
        "aprx_backup": str(backup_path) if backup_path else None,
        "map": target_map.name,
        "working_geodatabase": str(paths["working_gdb"]),
        "datasets_discovered": len(datasets),
        "datasets_added": added,
        "datasets_already_present": skipped,
        "datasets_failed": failed,
        "broken_project_sources": broken,
        "manifest_paths_not_found_locally": missing_manifest,
    }
    report_path = project_root / "github_arcgis_sync_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    log("5/5 Complete")
    log(f"  project: {aprx.filePath}")
    log(f"  map: {target_map.name}")
    log(f"  datasets added: {len(added)}")
    log(f"  datasets already present: {len(skipped)}")
    log(f"  datasets that failed: {len(failed)}")
    log(f"  broken project sources: {len(broken)}")
    log(f"  report: {report_path}")
    if not datasets:
        log(
            "  WARNING: no GIS datasets were found. The project workbook says rasters, "
            "geodatabases, shapefiles, and raw data are excluded from Git. You may need "
            "a separate data archive or download script."
        )
    return 0 if not failed and not broken else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SetupError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
