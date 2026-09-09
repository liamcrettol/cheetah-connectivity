"""Prepare separate temporal-threat fields for robust conservation links.

Threat is the change in modeled effective cost, not the link's current
importance. The script uses the available 2024 primary paths and leaves the
2012 fields pending until the historical resistance/path run is complete.
"""

from pathlib import Path
import csv

WORKSHEET = Path(r"C:\cheetah\reports\conservation_priority_worksheet.csv")
PATH_2012 = Path(r"C:\cheetah\reports\least_cost_paths_primary_combined_2012.csv")
PATH_2024 = Path(r"C:\cheetah\reports\least_cost_paths_primary_combined_unfenced.csv")
OUTPUT = Path(r"C:\cheetah\reports\temporal_threat_2012_2024.csv")


def key(row):
    return tuple(sorted((int(row["from_core"]), int(row["to_core"]))))


def load_cost(path):
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return {key(r): float(r["accumulated_cost_raw"]) for r in csv.DictReader(handle) if r.get("status", "OK") == "OK"}


def main():
    costs_2012 = load_cost(PATH_2012)
    costs_2024 = load_cost(PATH_2024)
    with WORKSHEET.open(newline="", encoding="utf-8-sig") as handle:
        links = list(csv.DictReader(handle))

    rows = []
    for link in links:
        p = key(link)
        c12 = costs_2012.get(p)
        c24 = costs_2024.get(p)
        change = None if c12 in (None, 0) or c24 is None else 100.0 * (c24 - c12) / c12
        rows.append({
            "from_core": p[0],
            "to_core": p[1],
            "importance_rank": link["importance_rank"],
            "edge_betweenness_normalized": link["edge_betweenness_normalized"],
            "effective_cost_2012": "" if c12 is None else c12,
            "effective_cost_2024": "" if c24 is None else c24,
            "effective_cost_change_percent": "" if change is None else change,
            "temporal_threat_status": (
                "ready for interpretation" if change is not None else "pending historical 2012 path run"
            ),
            "interpretation_note": (
                "Positive change means modeled cost increased; do not interpret as observed movement change."
                if change is not None else
                "Run the 2012 primary combined unfenced paths, then rerun this script."
            ),
        })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0])
    with OUTPUT.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    ready = sum(r["temporal_threat_status"] == "ready for interpretation" for r in rows)
    print(f"robust links prepared: {len(rows)}")
    print(f"links with both 2012 and 2024 costs: {ready}")
    print(f"links pending 2012 paths: {len(rows) - ready}")
    print(f"report: {OUTPUT}")
    print("No rasters, paths, or map layers were changed.")


if __name__ == "__main__":
    main()
