"""Create a transparent conservation-priority worksheet.

Literature-supported design: do not collapse network importance, temporal
threat, and intervention leverage into one opaque score.  This script ranks
only robust links by network position and leaves the other evidence dimensions
explicit for later analysis.
"""

from pathlib import Path
import csv

INPUT = Path(r"C:\cheetah\reports\conservation_link_importance_betweenness.csv")
OUTPUT = Path(r"C:\cheetah\reports\conservation_priority_worksheet.csv")


def main():
    with INPUT.open(newline="", encoding="utf-8-sig") as handle:
        rows = [r for r in csv.DictReader(handle) if r["primary_priority_eligible"] == "yes"]
    rows.sort(key=lambda r: float(r["edge_betweenness_normalized"]), reverse=True)

    out = []
    for rank, row in enumerate(rows, 1):
        out.append({
            "importance_rank": rank,
            "from_core": row["from_core"],
            "to_core": row["to_core"],
            "edge_betweenness_normalized": row["edge_betweenness_normalized"],
            "straight_line_distance_km": row["straight_line_distance_km"],
            "weight_robust": row["weight_robust"],
            "fence_robust": row["fence_robust"],
            "temporal_threat_score": "",
            "intervention_leverage_score": "",
            "action_type": "",
            "evidence_notes": "",
        })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fields = list(out[0]) if out else []
    with OUTPUT.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(out)

    print(f"robust links in worksheet: {len(out)}")
    print("importance is ranked by normalized edge betweenness only")
    print("threat and intervention leverage are intentionally separate, unfilled fields")
    print(f"report: {OUTPUT}")
    print("No rasters, paths, or map layers were changed.")


if __name__ == "__main__":
    main()
