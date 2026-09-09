#!/usr/bin/env python3
"""Read-only inventory of the Cheetah GitHub checkout and current ArcGIS map."""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter
from datetime import datetime
from pathlib import Path


DEFAULT_REPO = Path(r"C:\cheetah\github_repo")
DEFAULT_OUTPUT = Path(r"C:\cheetah\inventory")
FILE_TYPES = {".tif", ".tiff", ".img", ".crf", ".shp", ".geojson", ".kml", ".kmz", ".csv", ".lyrx", ".sde"}


def classify(name: str, source: str = "") -> str:
    text = f"{name} {source}".lower()
    if any(token in text for token in ("extent_buffered", "range_envelope", "snapgrid")):
        return "01 Project framework"
    if "cheetahsouthernafrica" in text or "weise2017" in text or "observations" in text:
        return "02 Baseline evidence"
    if Path(name).stem.lower().startswith("built_"):
        return "03 Built-up · GHSL"
    if Path(name).stem.lower().startswith("lights_"):
        return "04 Nighttime lights · VIIRS"
    if Path(name).stem.lower().startswith("lc_"):
        return "05 Land cover · MCD12Q1"
    if Path(name).stem.lower().startswith("vcf_tree_"):
        return "06 Vegetation · tree cover"
    if Path(name).stem.lower().startswith("vcf_nontree_"):
        return "07 Vegetation · non-tree"
    if Path(name).stem.lower().startswith("vcf_bare_"):
        return "08 Vegetation · bare"
    return "99 Other"


def regular_files(repo: Path):
    for current, dirnames, filenames in os.walk(repo):
        dirnames[:] = [d for d in dirnames if d != ".git" and not d.lower().endswith(".gdb")]
        for filename in filenames:
            path = Path(current) / filename
            if path.suffix.lower() in FILE_TYPES:
                yield path.resolve()


def geodatabase_datasets(repo: Path, arcpy):
    for current, dirnames, _ in os.walk(repo):
        for dirname in list(dirnames):
            if dirname.lower().endswith(".gdb"):
                gdb = (Path(current) / dirname).resolve()
                dirnames.remove(dirname)
                for dirpath, _, names in arcpy.da.Walk(
                    str(gdb), datatype=["FeatureClass", "RasterDataset", "Table"]
                ):
                    for name in names:
                        yield Path(dirpath) / name
        if ".git" in dirnames:
            dirnames.remove(".git")


def describe_dataset(path: Path, repo: Path, arcpy) -> dict[str, object]:
    row: dict[str, object] = {
        "group": classify(path.name, str(path)),
        "name": path.name,
        "source": str(path),
        "relative_path": os.path.relpath(str(path), str(repo)),
        "extension": path.suffix.lower(),
        "data_type": "",
        "spatial_reference": "",
        "wkid": "",
        "row_count": "",
        "band_count": "",
        "cell_width": "",
        "cell_height": "",
        "extent": "",
        "size_mb": "",
        "modified": "",
        "describe_error": "",
    }
    if path.is_file():
        stat = path.stat()
        row["size_mb"] = round(stat.st_size / (1024 * 1024), 3)
        row["modified"] = datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds")
    try:
        desc = arcpy.Describe(str(path))
        row["data_type"] = getattr(desc, "dataType", "")
        sr = getattr(desc, "spatialReference", None)
        if sr:
            row["spatial_reference"] = getattr(sr, "name", "")
            row["wkid"] = getattr(sr, "factoryCode", "")
        extent = getattr(desc, "extent", None)
        if extent:
            row["extent"] = f"{extent.XMin},{extent.YMin},{extent.XMax},{extent.YMax}"
        row["band_count"] = getattr(desc, "bandCount", "")
        row["cell_width"] = getattr(desc, "meanCellWidth", "")
        row["cell_height"] = getattr(desc, "meanCellHeight", "")
        try:
            row["row_count"] = int(arcpy.management.GetCount(str(path))[0])
        except Exception:
            pass
    except Exception as exc:
        row["describe_error"] = str(exc)
    return row


def map_inventory(aprx, map_name: str) -> tuple[object, list[dict[str, object]]]:
    maps = aprx.listMaps(map_name) if map_name else []
    target = maps[0] if maps else (aprx.activeMap or aprx.listMaps()[0])
    rows: list[dict[str, object]] = []
    for layer in target.listLayers():
        source = ""
        broken = False
        try:
            broken = bool(layer.isBroken)
        except Exception:
            pass
        try:
            if layer.supports("DATASOURCE"):
                source = layer.dataSource
        except Exception:
            pass
        rows.append(
            {
                "kind": "group" if layer.isGroupLayer else "layer",
                "long_name": layer.longName,
                "name": layer.name,
                "suggested_group": classify(layer.name, source),
                "visible": getattr(layer, "visible", ""),
                "broken": broken,
                "source": source,
            }
        )
    for table in target.listTables():
        source = ""
        try:
            source = table.dataSource
        except Exception:
            pass
        rows.append(
            {
                "kind": "table",
                "long_name": table.name,
                "name": table.name,
                "suggested_group": classify(table.name, source),
                "visible": "",
                "broken": getattr(table, "isBroken", False),
                "source": source,
            }
        )
    return target, rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=DEFAULT_REPO)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--aprx", default="CURRENT")
    parser.add_argument("--map-name", default="Map")
    args = parser.parse_args()

    import arcpy  # type: ignore

    repo = args.repo.expanduser().resolve()
    if not repo.exists():
        raise FileNotFoundError(f"Repository not found: {repo}")
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)

    aprx = arcpy.mp.ArcGISProject(args.aprx)
    target_map, map_rows = map_inventory(aprx, args.map_name)
    paths = sorted(
        {str(p): p for p in [*regular_files(repo), *geodatabase_datasets(repo, arcpy)]}.values(),
        key=lambda p: str(p).lower(),
    )
    dataset_rows = [describe_dataset(path, repo, arcpy) for path in paths]

    write_csv(output / "github_datasets.csv", dataset_rows)
    write_csv(output / "current_map_contents.csv", map_rows)
    summary = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "repository": str(repo),
        "project": aprx.filePath,
        "map": target_map.name,
        "dataset_count": len(dataset_rows),
        "map_item_count": len(map_rows),
        "datasets_by_group": dict(Counter(row["group"] for row in dataset_rows)),
        "map_items_by_group": dict(Counter(row["suggested_group"] for row in map_rows)),
        "broken_map_items": [row["long_name"] for row in map_rows if row["broken"]],
    }
    (output / "inventory_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Inventory complete: {len(dataset_rows)} repository datasets")
    print(f"Current map items: {len(map_rows)}")
    for group, count in sorted(summary["datasets_by_group"].items()):
        print(f"  {group}: {count}")
    print(f"Reports: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

