"""Descriptive audit of the two conditions in manuscript hypothesis H1.

Joins the final 2012--2024 effective-resistance changes to baseline edge
betweenness for the 45 selected neighboring links. This is an audit summary,
not a new inferential test.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
CHANGE = REPORTS / "final_effective_resistance_change_2012_2024_20260909_073544.csv"
IMPORTANCE = REPORTS / "conservation_link_importance_betweenness.csv"
OUTPUT = REPORTS / "h1_betweenness_change_audit.json"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def average_ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    result = [0.0] * len(values)
    start = 0
    while start < len(order):
        stop = start + 1
        while stop < len(order) and values[order[stop]] == values[order[start]]:
            stop += 1
        rank = (start + stop - 1) / 2.0 + 1.0
        for index in order[start:stop]:
            result[index] = rank
        start = stop
    return result


def pearson(left: list[float], right: list[float]) -> float:
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right))
    denominator = math.sqrt(
        sum((a - left_mean) ** 2 for a in left)
        * sum((b - right_mean) ** 2 for b in right)
    )
    return numerator / denominator


def main() -> None:
    changes = read_rows(CHANGE)
    importance = {
        (int(row["from_core"]), int(row["to_core"])): row
        for row in read_rows(IMPORTANCE)
    }

    joined: list[dict[str, float | int]] = []
    for row in changes:
        if row["selected_neighbor_link"].lower() != "yes":
            continue
        key = (int(row["from_core"]), int(row["to_core"]))
        if key not in importance:
            raise KeyError(f"Selected link {key} is absent from the importance table")
        joined.append(
            {
                "from_core": key[0],
                "to_core": key[1],
                "percent_change_2012_2024": float(row["percent_change_2012_2024"]),
                "edge_betweenness_normalized": float(
                    importance[key]["edge_betweenness_normalized"]
                ),
            }
        )

    if len(joined) != 45:
        raise RuntimeError(f"Expected 45 selected links; found {len(joined)}")

    change_values = [float(row["percent_change_2012_2024"]) for row in joined]
    betweenness_values = [float(row["edge_betweenness_normalized"]) for row in joined]
    result = {
        "purpose": "Descriptive audit of manuscript H1; not a predeclared inferential test.",
        "selected_links": len(joined),
        "links_with_increased_effective_resistance": sum(value > 0 for value in change_values),
        "links_with_decreased_effective_resistance": sum(value < 0 for value in change_values),
        "spearman_rho_percent_change_vs_baseline_betweenness": pearson(
            average_ranks(change_values), average_ranks(betweenness_values)
        ),
        "interpretation": (
            "The minority-loss condition matched, but the expected positive relationship "
            "between loss and baseline betweenness did not. H1 is mixed, not supported."
        ),
        "input_change_report": str(CHANGE),
        "input_importance_report": str(IMPORTANCE),
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"report: {OUTPUT}")


if __name__ == "__main__":
    main()
