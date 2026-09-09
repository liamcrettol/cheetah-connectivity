"""Export the four final paper layouts as 300-dpi PNG and PDF files.

The script selects the latest dated draft of each layout when one exists. It
does not alter layouts, maps, analysis outputs, or manuscript files.
"""
from pathlib import Path
import re
import arcpy

OUT_DIR = Path(r"C:\cheetah\exports\paper_figures")
FIGURES = (
    ("Figure_1_high_current_concentration_2024", "LAYOUT · Figure 1 · High-current concentration · draft"),
    ("Figure_2_temporal_current_evidence", "LAYOUT · Figure 2 · Temporal current evidence · draft"),
    ("Figure_3_robust_priority_links", "LAYOUT · Figure 3 · Robust priority links · draft"),
    ("Figure_4_protected_area_context", "LAYOUT · Figure 4 · Protected-area context · draft"),
)


def latest_layout(aprx, prefix):
    matches = aprx.listLayouts(prefix + "*")
    if not matches:
        raise RuntimeError(f"Missing layout beginning with {prefix!r}")
    # Dated versions end in YYYYMMDD_HHMMSS; lexical order chooses the newest.
    return sorted(matches, key=lambda item: item.name)[-1]


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    for stem, prefix in FIGURES:
        layout = latest_layout(aprx, prefix)
        png = OUT_DIR / f"{stem}.png"
        pdf = OUT_DIR / f"{stem}.pdf"
        layout.exportToPNG(str(png), resolution=300, color_mode="32-BIT_WITH_ALPHA")
        layout.exportToPDF(str(pdf), resolution=300, image_quality="BEST", embed_fonts=True)
        print("exported:", png)
        print("exported:", pdf)
        print("layout used:", layout.name)
    print("Complete. Review the PNGs at 100% zoom before placing them in the manuscript.")


if __name__ == "__main__":
    main()
