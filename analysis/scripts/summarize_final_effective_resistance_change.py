"""Summarize temporal change in final Circuitscape effective resistance.

The final model is vegetation-balanced with documented finite KAZA/Kruger
fence resistance.  This reads completed Circuitscape pairwise output only; it
does not re-run Circuitscape or alter any GIS data or map layer.
"""
import csv
import datetime as dt
import json
from pathlib import Path
import statistics


YEARS = (2012, 2016, 2020, 2024)
OUTPUTS = Path(r"C:\cheetah\circuitscape\outputs\final_balanced_fence_documented")
REPORTS = Path(r"C:\cheetah\reports")
SELECTED_LINKS = REPORTS / "cheetah_core_neighbor_links.csv"


def output_path(year):
    path = OUTPUTS / f"current_final_balanced_fence_documented_{year}_resistances_3columns.out"
    if not path.is_file():
        raise FileNotFoundError(f"Missing final Circuitscape effective-resistance output: {path}")
    return path


def read_pairs(year):
    result = {}
    with output_path(year).open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            values = line.split()
            if len(values) != 3:
                raise ValueError(f"{year}, line {number}: expected three columns, got {line!r}")
            first, second = sorted((int(float(values[0])), int(float(values[1]))))
            resistance = float(values[2])
            if resistance <= 0:
                raise ValueError(f"{year}, pair {first}-{second}: resistance must be positive")
            if (first, second) in result:
                raise ValueError(f"{year}, duplicate pair {first}-{second}")
            result[(first, second)] = resistance
    if len(result) != 253:
        raise RuntimeError(f"{year}: expected 253 fixed-core pairs, found {len(result)}")
    return result


def percentile(values, pct):
    ordered = sorted(values)
    position = (len(ordered) - 1) * pct / 100.0
    low, high = int(position), min(int(position) + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def selected_links():
    """Read the a-priori 45 neighboring links used for corridor reporting."""
    if not SELECTED_LINKS.is_file():
        raise FileNotFoundError(f"Missing selected-link definition: {SELECTED_LINKS}")
    result = set()
    with SELECTED_LINKS.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            result.add(tuple(sorted((int(row["from_core"]), int(row["to_core"])))) )
    if len(result) != 45:
        raise RuntimeError(f"Expected 45 selected neighboring links, found {len(result)}")
    return result


def main():
    by_year = {year: read_pairs(year) for year in YEARS}
    reference_pairs = set(by_year[2012])
    selected = selected_links()
    if not selected.issubset(reference_pairs):
        raise RuntimeError("A selected corridor link is missing from the final Circuitscape pair set")
    for year, pairs in by_year.items():
        if set(pairs) != reference_pairs:
            raise RuntimeError(f"{year}: pair identifiers differ from 2012; do not compare them")

    rows = []
    for first, second in sorted(reference_pairs):
        initial = by_year[2012][(first, second)]
        final = by_year[2024][(first, second)]
        absolute = final - initial
        percent = 100.0 * absolute / initial
        rows.append({
            "from_core": first,
            "to_core": second,
            **{f"effective_resistance_{year}": by_year[year][(first, second)] for year in YEARS},
            "absolute_change_2012_2024": absolute,
            "percent_change_2012_2024": percent,
            "direction": "increase" if absolute > 0 else "decrease" if absolute < 0 else "no change",
            "selected_neighbor_link": "yes" if (first, second) in selected else "no",
        })

    changes = [row["percent_change_2012_2024"] for row in rows]
    abs_changes = [abs(value) for value in changes]
    increases = sorted(rows, key=lambda row: row["percent_change_2012_2024"], reverse=True)
    decreases = sorted(rows, key=lambda row: row["percent_change_2012_2024"])
    annual = {}
    for year in YEARS:
        values = list(by_year[year].values())
        annual[str(year)] = {
            "pair_count": len(values),
            "median_effective_resistance": statistics.median(values),
            "mean_effective_resistance": statistics.mean(values),
            "minimum_effective_resistance": min(values),
            "maximum_effective_resistance": max(values),
        }
    selected_changes = [row["percent_change_2012_2024"] for row in rows if row["selected_neighbor_link"] == "yes"]
    selected_abs = [abs(value) for value in selected_changes]
    summary = {
        "created": dt.datetime.now().isoformat(timespec="seconds"),
        "scenario": "Final vegetation-balanced resistance with documented finite KAZA/Kruger fence multiplier",
        "core_count": 23,
        "pair_count": len(rows),
        "selected_neighbor_link_count": len(selected_changes),
        "years": list(YEARS),
        "annual_effective_resistance": annual,
        "change_2012_2024_percent": {
            "median": statistics.median(changes),
            "mean": statistics.mean(changes),
            "minimum": min(changes),
            "maximum": max(changes),
            "median_absolute": statistics.median(abs_changes),
            "p90_absolute": percentile(abs_changes, 90),
            "increased_pairs": sum(value > 0 for value in changes),
            "decreased_pairs": sum(value < 0 for value in changes),
        },
        "largest_increases": increases[:10],
        "largest_decreases": decreases[:10],
        "selected_neighbor_link_change_2012_2024_percent": {
            "median": statistics.median(selected_changes),
            "mean": statistics.mean(selected_changes),
            "median_absolute": statistics.median(selected_abs),
            "p90_absolute": percentile(selected_abs, 90),
            "increased_links": sum(value > 0 for value in selected_changes),
            "decreased_links": sum(value < 0 for value in selected_changes),
        },
        "interpretation_limits": [
            "Effective resistance is a modelled pairwise connectivity metric, not observed cheetah movement probability.",
            "Changes compare the same 23 fixed cores and all 253 core pairs under the same final model structure.",
            "Results should be interpreted alongside link robustness, fence-scenario review, and VCF missing-data context.",
        ],
    }

    REPORTS.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    table = REPORTS / f"final_effective_resistance_change_2012_2024_{stamp}.csv"
    with table.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    record = REPORTS / f"final_effective_resistance_change_2012_2024_{stamp}.json"
    record.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    brief = REPORTS / f"final_effective_resistance_change_2012_2024_{stamp}.md"
    brief.write_text(
        "# Final effective-resistance change, 2012–2024\n\n"
        f"- Pairwise comparisons: {len(rows)} (all pairs among 23 fixed cores)\n"
        f"- Median percent change: {summary['change_2012_2024_percent']['median']:.3f}%\n"
        f"- Median absolute percent change: {summary['change_2012_2024_percent']['median_absolute']:.3f}%\n"
        f"- 90th-percentile absolute percent change: {summary['change_2012_2024_percent']['p90_absolute']:.3f}%\n"
        f"- Increased / decreased: {summary['change_2012_2024_percent']['increased_pairs']} / {summary['change_2012_2024_percent']['decreased_pairs']}\n\n"
        f"- Selected neighbouring links: {len(selected_changes)}; median percent change: {summary['selected_neighbor_link_change_2012_2024_percent']['median']:.3f}%\n\n"
        "These are modelled effective-resistance changes, not observed movement changes.\n",
        encoding="utf-8",
    )
    print("fixed core pairs compared:", len(rows))
    print("median percent change (2012–2024):", f"{summary['change_2012_2024_percent']['median']:.3f}%")
    print("median absolute percent change:", f"{summary['change_2012_2024_percent']['median_absolute']:.3f}%")
    print("selected neighboring-link median percent change:",
          f"{summary['selected_neighbor_link_change_2012_2024_percent']['median']:.3f}%")
    print("largest increase:", f"{increases[0]['from_core']}-{increases[0]['to_core']}",
          f"{increases[0]['percent_change_2012_2024']:.3f}%")
    print("largest decrease:", f"{decreases[0]['from_core']}-{decreases[0]['to_core']}",
          f"{decreases[0]['percent_change_2012_2024']:.3f}%")
    print("table:", table)
    print("method record:", record)
    print("brief:", brief)
    print("Complete. Existing Circuitscape outputs, rasters, and map layers were unchanged.")


if __name__ == "__main__":
    main()
