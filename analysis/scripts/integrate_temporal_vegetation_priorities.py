"""Join temporal vegetation sensitivity to the existing link-priority evidence.

The script preserves the existing importance ranking and does not create a new
opaque composite score. A link remains primary-priority eligible only when it
was already weight- and fence-robust and its 2012-2024 direction is consistent
across the low, balanced, and high vegetation scenarios.
"""

from pathlib import Path
import csv


REPORTS = Path(r"C:\cheetah\reports")
IMPORTANCE = REPORTS / "conservation_link_importance_betweenness.csv"
PRIORITY = REPORTS / "conservation_priority_worksheet.csv"
VEGETATION = REPORTS / "temporal_vegetation_scenario_agreement.csv"

OUT_ALL = REPORTS / "conservation_link_evidence_integrated.csv"
OUT_PRIMARY = REPORTS / "conservation_priority_links_temporal.csv"
OUT_UNCERTAINTY = REPORTS / "conservation_uncertainty_links_temporal.csv"
OUT_PAPER_TOP20 = REPORTS / "paper_table_top20_connectivity_priorities.csv"
OUT_NOTE = REPORTS / "temporal_vegetation_priority_integration_note.md"


def key(row):
    a, b = int(row["from_core"]), int(row["to_core"])
    return (a, b) if a <= b else (b, a)


def read_rows(path):
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def index_unique(rows, label):
    result = {}
    for row in rows:
        pair = key(row)
        if pair in result:
            raise RuntimeError(f"Duplicate pair {pair} in {label}")
        result[pair] = row
    return result


def write_csv(path, rows, fields):
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def direction_label(vegetation):
    directions = {
        vegetation["direction_veg_low"],
        vegetation["direction_veg_balanced"],
        vegetation["direction_veg_high"],
    }
    if len(directions) != 1:
        return "vegetation-sensitive direction"
    direction = next(iter(directions))
    return {
        "increase": "increasing modeled resistance",
        "decrease": "decreasing modeled resistance",
        "no_change": "no directional change",
    }[direction]


def main():
    importance_rows = read_rows(IMPORTANCE)
    priority_rows = read_rows(PRIORITY)
    vegetation_rows = read_rows(VEGETATION)
    importance = index_unique(importance_rows, IMPORTANCE)
    priority = index_unique(priority_rows, PRIORITY)
    vegetation = index_unique(vegetation_rows, VEGETATION)

    if len(importance) != 45 or len(vegetation) != 45:
        raise RuntimeError(
            f"Expected 45 links; importance={len(importance)}, vegetation={len(vegetation)}"
        )
    if set(importance) != set(vegetation):
        raise RuntimeError("Importance and vegetation tables do not contain identical links")

    integrated = []
    for pair in sorted(importance):
        imp = importance[pair]
        veg = vegetation[pair]
        prior = priority.get(pair, {})
        existing_eligible = imp["primary_priority_eligible"].strip().lower() == "yes"
        vegetation_robust = (
            veg["direction_consistent_across_scenarios"].strip().lower() == "yes"
        )
        final_eligible = existing_eligible and vegetation_robust

        reasons = []
        if imp["weight_robust"].strip().lower() != "yes":
            reasons.append("weight-sensitive")
        if imp["fence_robust"].strip().lower() != "yes":
            reasons.append("fence-sensitive")
        if not vegetation_robust:
            reasons.append("vegetation-direction-sensitive")
        if final_eligible:
            final_use = "primary conservation-priority evidence"
        else:
            final_use = "uncertainty/data-collection evidence: " + ", ".join(reasons)

        integrated.append({
            "from_core": pair[0],
            "to_core": pair[1],
            "importance_rank": prior.get("importance_rank", ""),
            "edge_betweenness_normalized": imp["edge_betweenness_normalized"],
            "link_type": imp["link_type"],
            "straight_line_distance_km": imp["straight_line_distance_km"],
            "weight_robust": imp["weight_robust"],
            "fence_robust": imp["fence_robust"],
            "vegetation_direction_robust": "yes" if vegetation_robust else "no",
            "veg_low_change_percent_2012_2024": veg["veg_low_change_percent_2012_2024"],
            "veg_balanced_change_percent_2012_2024": veg["veg_balanced_change_percent_2012_2024"],
            "veg_high_change_percent_2012_2024": veg["veg_high_change_percent_2012_2024"],
            "median_change_percent_2012_2024": veg["median_change_percent"],
            "temporal_direction_interpretation": direction_label(veg),
            "primary_priority_eligible_before_vegetation_test": "yes" if existing_eligible else "no",
            "primary_priority_eligible_final": "yes" if final_eligible else "no",
            "priority_use_final": final_use,
        })

    fields = list(integrated[0])
    write_csv(OUT_ALL, integrated, fields)

    primary = [row for row in integrated if row["primary_priority_eligible_final"] == "yes"]
    primary.sort(key=lambda row: int(row["importance_rank"]))
    uncertainty = [row for row in integrated if row["primary_priority_eligible_final"] == "no"]
    uncertainty.sort(key=lambda row: float(row["edge_betweenness_normalized"]), reverse=True)
    write_csv(OUT_PRIMARY, primary, fields)
    write_csv(OUT_UNCERTAINTY, uncertainty, fields)
    write_csv(OUT_PAPER_TOP20, primary[:20], fields)

    vegetation_sensitive = [
        row for row in integrated if row["vegetation_direction_robust"] == "no"
    ]
    newly_excluded = [
        row for row in vegetation_sensitive
        if row["primary_priority_eligible_before_vegetation_test"] == "yes"
    ]
    with OUT_NOTE.open("w", encoding="utf-8") as handle:
        handle.write("# Temporal vegetation sensitivity integration\n\n")
        handle.write(
            "The existing normalized edge-betweenness ranking was retained. "
            "No new composite score or biological cutoff was introduced. A link "
            "remained primary-priority eligible only if it was already weight- and "
            "fence-robust and its 2012–2024 effective-cost direction was consistent "
            "across vegetation-low, vegetation-balanced, and vegetation-high scenarios.\n\n"
        )
        handle.write(f"- Links evaluated: {len(integrated)}\n")
        handle.write(f"- Final primary-priority links: {len(primary)}\n")
        handle.write(f"- Uncertainty/data-collection links: {len(uncertainty)}\n")
        handle.write(f"- Vegetation-direction-sensitive links: {len(vegetation_sensitive)}\n")
        handle.write(f"- Previously eligible links newly excluded: {len(newly_excluded)}\n")
        if vegetation_sensitive:
            handle.write(
                "- Sensitive pairs: "
                + ", ".join(
                    f"{row['from_core']}–{row['to_core']}" for row in vegetation_sensitive
                )
                + "\n"
            )

    print(f"links integrated: {len(integrated)}")
    print(f"final primary-priority links: {len(primary)}")
    print(f"uncertainty/data-collection links: {len(uncertainty)}")
    print(f"vegetation-sensitive links: {len(vegetation_sensitive)}")
    print(f"previously eligible links newly excluded: {len(newly_excluded)}")
    print(f"all-link evidence: {OUT_ALL}")
    print(f"primary priorities: {OUT_PRIMARY}")
    print(f"uncertainty links: {OUT_UNCERTAINTY}")
    print(f"paper top 20: {OUT_PAPER_TOP20}")
    print(f"method note: {OUT_NOTE}")


if __name__ == "__main__":
    main()
