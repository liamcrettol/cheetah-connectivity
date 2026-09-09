"""Combine weight and fence sensitivity into a conservative priority screen.

Primary conservation eligibility requires a link to be ROBUST under both tested
weight alternatives and STABLE under the fence scenarios.  Route-shifted,
low-cost links remain in the output as uncertainty/data-collection priorities,
but are not promoted to the primary priority set.
"""

from pathlib import Path
import csv

WEIGHT = Path(r"C:\cheetah\reports\full_weight_sensitivity_summary.csv")
FENCE = Path(r"C:\cheetah\reports\fence_scenario_sensitivity_interpretation.csv")
OUTPUT = Path(r"C:\cheetah\reports\robust_conservation_link_screen.csv")


def pair(row):
    return (int(row["from_core"]), int(row["to_core"]))


def main():
    weights = {}
    with WEIGHT.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            weights.setdefault(pair(row), []).append(row)

    fences = {}
    with FENCE.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            fences[pair(row)] = row

    rows = []
    for p in sorted(weights):
        wrows = weights[p]
        weight_robust = all(r["classification"].upper() == "ROBUST" for r in wrows)
        frow = fences.get(p)
        fence_label = "Not affected by tested fence cells" if frow is None else frow["review_label"]
        fence_robust = frow is None or fence_label == "Stable under fence scenarios"
        eligible = weight_robust and fence_robust

        if eligible:
            uncertainty = "Primary priority eligible"
            rationale = "Robust under both tested weight alternatives and fence scenarios."
        elif not weight_robust and not fence_robust:
            uncertainty = "Sensitive to both weights and fences"
            rationale = "Retain for discussion/data collection; exclude from primary priorities."
        elif not weight_robust:
            uncertainty = "Weight-sensitive"
            rationale = "Retain for discussion/data collection; exclude from primary priorities."
        else:
            uncertainty = "Fence-sensitive or route-geometry-sensitive"
            rationale = "Retain for discussion/data collection; exclude from primary priorities."

        rows.append({
            "from_core": p[0],
            "to_core": p[1],
            "weight_robust": "yes" if weight_robust else "no",
            "fence_robust": "yes" if fence_robust else "no",
            "fence_result": fence_label,
            "primary_priority_eligible": "yes" if eligible else "no",
            "uncertainty_class": uncertainty,
            "rationale": rationale,
        })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0])
    with OUTPUT.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print(f"candidate links screened: {len(rows)}")
    print(f"primary-priority eligible: {sum(r['primary_priority_eligible'] == 'yes' for r in rows)}")
    print(f"uncertainty/data-collection links: {sum(r['primary_priority_eligible'] == 'no' for r in rows)}")
    print(f"report: {OUTPUT}")
    print("No rasters, paths, or map layers were changed.")


if __name__ == "__main__":
    main()
