"""Interpret fence-path scenario results without changing ArcGIS datasets.

Main-fence interpretation: a cheetah can cross, so this scenario should usually
remain close to the unfenced reference path.  Near-barrier interpretation: it
tests whether the link depends on easy fence crossing.  The numeric cutoffs
below are transparent review triggers, not biological truth.
"""

from pathlib import Path
import csv


INPUT = Path(r"C:\cheetah\reports\fence_path_scenario_comparison.csv")
OUTPUT = Path(r"C:\cheetah\reports\fence_scenario_sensitivity_interpretation.csv")

# Review triggers selected for transparent, conservative interpretation.
MAIN_MIN_OVERLAP = 80.0       # % of scenario path within 5 km of primary
MAIN_MAX_COST = 10.0          # % cost increase before calling main effect material
NEAR_MIN_OVERLAP = 80.0       # same spatial-consistency standard
NEAR_MATERIAL_COST = 20.0     # larger cost increase for barrier-dependence flag
STRONG_MIN_OVERLAP = 50.0
STRONG_COST = 50.0


def number(value):
    return None if value in (None, "") else float(value)


def text_flag(condition, yes, no):
    return yes if condition else no


def main():
    if not INPUT.exists():
        raise FileNotFoundError(f"Run the four fence scenarios first. Missing: {INPUT}")

    by_pair = {}
    with INPUT.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if row["recalculated"] != "1":
                continue
            pair = (int(row["from_core"]), int(row["to_core"]))
            by_pair.setdefault(pair, {})[row["scenario"]] = {
                "overlap": number(row["scenario_path_within_5km_of_primary_percent"]),
                "length": number(row["path_length_change_km"]),
                "cost": number(row["cost_change_percent"]),
            }

    required = {"fence_main", "fence_nearbarrier", "kruger_documented", "kruger_conservative"}
    missing = [pair for pair, scenarios in by_pair.items() if not required.issubset(scenarios)]
    if missing:
        raise RuntimeError(f"Incomplete scenario rows for affected pairs: {missing}")

    rows = []
    for pair in sorted(by_pair):
        main_s = by_pair[pair]["fence_main"]
        near_s = by_pair[pair]["fence_nearbarrier"]
        kd_s = by_pair[pair]["kruger_documented"]
        kc_s = by_pair[pair]["kruger_conservative"]

        main_material = main_s["overlap"] < MAIN_MIN_OVERLAP or main_s["cost"] > MAIN_MAX_COST
        near_material = near_s["overlap"] < NEAR_MIN_OVERLAP or near_s["cost"] > NEAR_MATERIAL_COST
        # Low overlap alone is not a strong effect: it may simply reveal a
        # similarly efficient alternative route. Strong constraint requires a
        # large increase in modeled movement cost.
        near_strong = near_s["cost"] > STRONG_COST
        kruger_difference = (
            abs(kd_s["overlap"] - kc_s["overlap"]) > 0.01
            or abs(kd_s["cost"] - kc_s["cost"]) > 0.01
            or abs(kd_s["length"] - kc_s["length"]) > 0.01
        )

        # A spatial reroute and a loss of functional connectivity are not the
        # same thing.  A low-cost alternative route remains functionally
        # available, even when it shares little geometry with the primary path.
        # These are deliberately interpretation labels, not verified movement.
        if near_strong:
            conclusion = "Materially constrained: strong near-barrier cost effect"
        elif near_s["cost"] > NEAR_MATERIAL_COST:
            conclusion = "Materially constrained: near-barrier cost effect"
        elif near_s["overlap"] < NEAR_MIN_OVERLAP:
            conclusion = "Route-shifted but still low-cost"
        else:
            conclusion = "Stable under fence scenarios"

        if main_material and main_s["cost"] <= MAIN_MAX_COST:
            main_note = "route-shifted but low-cost under crossable fence"
        elif main_material:
            main_note = "review: crossable-fence scenario increased modeled cost"
        else:
            main_note = "consistent with a crossable fence"

        rows.append({
            "from_core": pair[0],
            "to_core": pair[1],
            "main_overlap_pct": main_s["overlap"],
            "main_length_change_km": main_s["length"],
            "main_cost_change_pct": main_s["cost"],
            "main_crossable_expectation": main_note,
            "nearbarrier_overlap_pct": near_s["overlap"],
            "nearbarrier_length_change_km": near_s["length"],
            "nearbarrier_cost_change_pct": near_s["cost"],
            "nearbarrier_dependency": text_flag(
                near_material,
                "yes: link depends on easy crossing under tested scenario",
                "no material dependence under tested scenario",
            ),
            "kruger_documented_cost_change_pct": kd_s["cost"],
            "kruger_conservative_cost_change_pct": kc_s["cost"],
            "kruger_assumption_changes_result": "yes" if kruger_difference else "no",
            "review_label": conclusion,
        })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0])
    with OUTPUT.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print("Fence-scenario interpretation (review triggers, not biological cutoffs):")
    print(f"  crossable main: overlap < {MAIN_MIN_OVERLAP:.0f}% OR cost increase > {MAIN_MAX_COST:.0f}%")
    print(f"  near-barrier: overlap < {NEAR_MIN_OVERLAP:.0f}% OR cost increase > {NEAR_MATERIAL_COST:.0f}%")
    print()
    for row in rows:
        print(
            f"{row['from_core']}–{row['to_core']}: {row['review_label']} | "
            f"main cost {row['main_cost_change_pct']:.1f}%, "
            f"near-barrier cost {row['nearbarrier_cost_change_pct']:.1f}%"
        )
    print()
    print(f"report: {OUTPUT}")
    print("No rasters, paths, or map layers were changed.")


if __name__ == "__main__":
    main()
