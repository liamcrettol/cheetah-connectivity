"""Read-only count and length summary of GRIP4 road types in the study extent."""

import csv
from collections import defaultdict
from pathlib import Path

import arcpy


ROADS = r"C:\cheetah\gdb\cheetah_working.gdb\roads_grip4"
REPORT = Path(r"C:\cheetah\reports\roads_grip4_type_summary.csv")
LABELS = {
    1: "Highways",
    2: "Primary roads",
    3: "Secondary roads",
    4: "Tertiary roads",
    5: "Local roads",
}


def main():
    if not arcpy.Exists(ROADS):
        raise RuntimeError(f"Missing clipped GRIP4 roads: {ROADS}")
    summary = defaultdict(lambda: {"feature_count": 0, "length_m": 0.0})
    with arcpy.da.SearchCursor(ROADS, ["GP_RTP", "SHAPE@LENGTH"]) as cursor:
        for road_type, length_m in cursor:
            summary[road_type]["feature_count"] += 1
            summary[road_type]["length_m"] += length_m or 0.0

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for road_type in sorted(summary, key=lambda value: (value is None, value)):
        item = summary[road_type]
        rows.append({
            "gp_rtp": road_type,
            "road_type": LABELS.get(road_type, "Unknown / unclassified"),
            "feature_count": item["feature_count"],
            "length_km": round(item["length_m"] / 1000, 2),
            "recommended_group": "major" if road_type in (1, 2) else "minor" if road_type in (3, 4, 5) else "review",
        })
    with REPORT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    for row in rows:
        print(f"{row['gp_rtp']}: {row['road_type']}: {row['feature_count']:,} features; {row['length_km']:,.2f} km; {row['recommended_group']}")
    print(f"report: {REPORT}")
    print("Nothing was changed.")


if __name__ == "__main__":
    main()
