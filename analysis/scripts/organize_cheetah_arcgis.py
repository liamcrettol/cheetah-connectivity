#!/usr/bin/env python3
"""Organize existing Cheetah layers into meaningful ArcGIS Pro group layers."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path


DEFAULT_BACKUP_DIR = Path(r"C:\cheetah\backups")
GROUP_NAMES = [
    "01 Project framework",
    "02 Baseline evidence",
    "03 Built-up · GHSL",
    "04 Nighttime lights · VIIRS",
    "05 Land cover · MCD12Q1",
    "06 Vegetation · tree cover",
    "07 Vegetation · non-tree",
    "08 Vegetation · bare",
    "99 Other",
]


def classify(name: str, source: str = "") -> str:
    text = f"{name} {source}".lower()
    stem = Path(name).stem.lower()
    if any(token in text for token in ("extent_buffered", "range_envelope", "snapgrid")):
        return "01 Project framework"
    if "cheetahsouthernafrica" in text or "weise2017" in text or "observations" in text:
        return "02 Baseline evidence"
    if stem.startswith("built_"):
        return "03 Built-up · GHSL"
    if stem.startswith("lights_"):
        return "04 Nighttime lights · VIIRS"
    if stem.startswith("lc_"):
        return "05 Land cover · MCD12Q1"
    if stem.startswith("vcf_tree_"):
        return "06 Vegetation · tree cover"
    if stem.startswith("vcf_nontree_"):
        return "07 Vegetation · non-tree"
    if stem.startswith("vcf_bare_"):
        return "08 Vegetation · bare"
    return "99 Other"


def source_of(item) -> str:
    try:
        if item.supports("DATASOURCE"):
            return item.dataSource
    except Exception:
        pass
    try:
        return item.dataSource
    except Exception:
        return ""


def find_direct_child_group(target_map, parent, name: str):
    prefix = parent.longName + "\\"
    for layer in target_map.listLayers():
        if layer.isGroupLayer and layer.name == name and layer.longName == prefix + name:
            return layer
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aprx", default="CURRENT")
    parser.add_argument("--map-name", default="Map")
    parser.add_argument("--parent-group", default="Cheetah project")
    parser.add_argument("--backup-dir", type=Path, default=DEFAULT_BACKUP_DIR)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    import arcpy  # type: ignore

    aprx = arcpy.mp.ArcGISProject(args.aprx)
    if aprx.isReadOnly:
        raise RuntimeError("Project is read-only. Run inside the open project with --aprx CURRENT.")
    maps = aprx.listMaps(args.map_name) if args.map_name else []
    target_map = maps[0] if maps else (aprx.activeMap or aprx.listMaps()[0])

    root_layers = [
        layer
        for layer in target_map.listLayers()
        if "\\" not in layer.longName and not layer.isGroupLayer
    ]
    plan = [
        {
            "layer": layer.name,
            "source": source_of(layer),
            "destination": classify(layer.name, source_of(layer)),
        }
        for layer in root_layers
    ]

    print(f"Project: {aprx.filePath}")
    print(f"Map: {target_map.name}")
    print(f"Root layers to organize: {len(plan)}")
    for item in plan:
        print(f"  {item['layer']} -> {item['destination']}")
    if args.dry_run:
        print("Dry run complete; nothing changed.")
        return 0

    backup_dir = args.backup_dir.expanduser().resolve()
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = backup_dir / f"{Path(aprx.filePath).stem}_before_layer_organization_{stamp}.aprx"
    aprx.saveACopy(str(backup))

    parent_matches = [
        layer
        for layer in target_map.listLayers(args.parent_group)
        if layer.isGroupLayer and "\\" not in layer.longName
    ]
    parent = parent_matches[0] if parent_matches else target_map.createGroupLayer(args.parent_group)
    groups = {}
    # ArcGIS inserts new groups at the top, so create them in reverse to leave
    # the numbered groups in ascending reading order.
    for name in reversed(GROUP_NAMES):
        groups[name] = find_direct_child_group(target_map, parent, name) or target_map.createGroupLayer(name, parent)

    moved: list[dict[str, str]] = []
    failed: list[dict[str, str]] = []
    for layer in root_layers:
        # Removing a layer invalidates its ArcPy object immediately, so retain
        # all values needed for logging before removeLayer is called.
        layer_name = layer.name
        layer_source = source_of(layer)
        destination = classify(layer_name, layer_source)
        try:
            # ArcPy cannot move a layer directly into an empty group. Adding the
            # existing layer to the group preserves its authored properties;
            # removing the root reference then avoids a duplicate.
            target_map.addLayerToGroup(groups[destination], layer, "BOTTOM")
            target_map.removeLayer(layer)
            moved.append({"layer": layer_name, "source": layer_source, "destination": destination})
        except Exception as exc:
            failed.append(
                {
                    "layer": layer_name,
                    "source": layer_source,
                    "destination": destination,
                    "error": str(exc),
                }
            )
            print(f"WARNING: {layer_name}: {exc}")

    aprx.save()
    report = {
        "completed_at": datetime.now().isoformat(timespec="seconds"),
        "project": aprx.filePath,
        "map": target_map.name,
        "backup": str(backup),
        "moved": moved,
        "failed": failed,
    }
    report_path = Path(r"C:\cheetah\layer_organization_report.json")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Organized {len(moved)} layers; {len(failed)} failed.")
    print(f"Backup: {backup}")
    print(f"Report: {report_path}")
    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
