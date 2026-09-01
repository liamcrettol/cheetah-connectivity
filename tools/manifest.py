"""
Regenerates manifest.csv, an inventory of analysis outputs.

Run:  python tools/manifest.py

Walks each path in OUTPUT_ROOTS, records every file under /rasters,
/circuitscape and /figures (the derived-output folders per the Conventions
tab; /raw and /gdb are not inventoried here), and parses filenames against
the project naming convention:

    <what>_<scenario>_<year>_<resolution>[_<core>]

e.g. res04_2024_1km.tif · current_res02_2016_1km_c2.tif · cores_c1.tif

Anything that does not match is still listed, with off_convention set to
True, so it shows up for cleanup rather than silently vanishing.

Paths in OUTPUT_ROOTS are checked in order; missing roots are skipped, so you
can list a home path and a work/Codespace path together without editing this
file every time you switch machines.
"""

import csv
import re
from pathlib import Path

# Edit this to match where ArcGIS Pro / Circuitscape write outputs on your
# machine(s). List as many as you like -- missing ones are skipped.
OUTPUT_ROOTS = [
    Path.home() / "cheetah",
    Path("C:/cheetah"),
]

# Only these subfolders hold derived outputs worth inventorying.
OUTPUT_SUBFOLDERS = ["rasters", "circuitscape", "figures"]

NAME_PATTERN = re.compile(
    r"^(?P<what>[a-zA-Z]+\d*)_"
    r"(?P<scenario>res\d{2})_"
    r"(?P<year>\d{4})_"
    r"(?P<resolution>\d+km)"
    r"(?:_(?P<core>c\d))?"
    r"\.(?P<ext>\w+)$"
)

# A handful of outputs don't carry a scenario/year (e.g. cores_c1.tif),
# so also try this shorter pattern before flagging off_convention.
SHORT_PATTERN = re.compile(
    r"^(?P<what>[a-zA-Z]+\d*)"
    r"(?:_(?P<core>c\d))?"
    r"\.(?P<ext>\w+)$"
)


def parse_filename(name: str) -> dict:
    m = NAME_PATTERN.match(name)
    if m:
        d = m.groupdict()
        d["off_convention"] = False
        return d

    m = SHORT_PATTERN.match(name)
    if m:
        d = {"what": m.group("what"), "scenario": "", "year": "", "resolution": "",
             "core": m.group("core") or "", "ext": m.group("ext"), "off_convention": False}
        return d

    return {"what": "", "scenario": "", "year": "", "resolution": "", "core": "",
            "ext": Path(name).suffix.lstrip("."), "off_convention": True}


def collect_rows() -> list[dict]:
    rows = []
    for root in OUTPUT_ROOTS:
        if not root.exists():
            continue
        for sub in OUTPUT_SUBFOLDERS:
            subdir = root / sub
            if not subdir.exists():
                continue
            for path in subdir.rglob("*"):
                if not path.is_file():
                    continue
                parsed = parse_filename(path.name)
                rows.append({
                    "root": str(root),
                    "subfolder": sub,
                    "relative_path": str(path.relative_to(root)),
                    "filename": path.name,
                    "size_bytes": path.stat().st_size,
                    "modified": path.stat().st_mtime,
                    **parsed,
                })
    return rows


def main():
    rows = collect_rows()
    out_path = Path(__file__).resolve().parent.parent / "manifest.csv"
    fieldnames = [
        "root", "subfolder", "relative_path", "filename", "size_bytes",
        "modified", "what", "scenario", "year", "resolution", "core", "ext",
        "off_convention",
    ]
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    off = sum(1 for r in rows if r["off_convention"])
    print(f"{len(rows)} files inventoried, {off} off-convention, written to {out_path}")


if __name__ == "__main__":
    main()
