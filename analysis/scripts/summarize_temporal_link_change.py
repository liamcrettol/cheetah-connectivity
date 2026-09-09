"""Summarize 2012-2024 effective-cost change for fixed cheetah core links.

Reads the four primary least-cost-path reports, validates that the same links are
present in every year, joins the 32 robust conservation links, and writes:

* temporal_link_costs_all.csv            all 45 links, wide format
* temporal_link_change_summary.csv       interval-level descriptive statistics
* temporal_robust_links_ranked.csv        the 32 robust links, paper-table input
* fig_temporal_effective_cost_change.png  diagnostic figure

This script changes no rasters, paths, feature classes, or ArcGIS Pro layers.
"""

from __future__ import annotations

import csv
import math
import statistics
from pathlib import Path


REPORTS = Path(r"C:\cheetah\reports")
FIGURES = REPORTS / "figures"

PATH_REPORTS = {
    2012: REPORTS / "least_cost_paths_primary_combined_2012.csv",
    2016: REPORTS / "least_cost_paths_primary_combined_2016.csv",
    2020: REPORTS / "least_cost_paths_primary_combined_2020.csv",
    2024: REPORTS / "least_cost_paths_primary_combined_unfenced.csv",
}

PRIORITY = REPORTS / "conservation_priority_worksheet.csv"
OUT_ALL = REPORTS / "temporal_link_costs_all.csv"
OUT_SUMMARY = REPORTS / "temporal_link_change_summary.csv"
OUT_ROBUST = REPORTS / "temporal_robust_links_ranked.csv"
OUT_FIGURE = FIGURES / "fig_temporal_effective_cost_change.png"

YEARS = (2012, 2016, 2020, 2024)
INTERVALS = ((2012, 2016), (2016, 2020), (2020, 2024), (2012, 2024))


def link_key(row: dict[str, str]) -> tuple[int, int]:
    a, b = int(row["from_core"]), int(row["to_core"])
    return (a, b) if a <= b else (b, a)


def finite_float(value: str, label: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"Non-finite {label}: {value!r}")
    return number


def read_path_report(path: Path) -> dict[tuple[int, int], dict[str, float]]:
    if not path.exists():
        raise FileNotFoundError(path)

    result: dict[tuple[int, int], dict[str, float]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("status", "").strip().upper() != "OK":
                continue
            key = link_key(row)
            if key in result:
                raise ValueError(f"Duplicate link {key} in {path}")
            result[key] = {
                "cost": finite_float(row["accumulated_cost_raw"], "cost"),
                "length_km": finite_float(row["path_length_km"], "path length"),
            }
    return result


def percent_change(start: float, end: float) -> float:
    return ((end - start) / start) * 100.0 if start != 0 else math.nan


def read_priority() -> dict[tuple[int, int], dict[str, str]]:
    if not PRIORITY.exists():
        raise FileNotFoundError(PRIORITY)
    with PRIORITY.open("r", encoding="utf-8-sig", newline="") as handle:
        return {link_key(row): row for row in csv.DictReader(handle)}


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return math.nan
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def main() -> None:
    reports = {year: read_path_report(path) for year, path in PATH_REPORTS.items()}
    key_sets = {year: set(values) for year, values in reports.items()}
    reference = key_sets[2012]
    mismatches = {
        year: sorted(reference.symmetric_difference(keys))
        for year, keys in key_sets.items()
        if keys != reference
    }
    if mismatches:
        details = "\n".join(f"{year}: {links}" for year, links in mismatches.items())
        raise RuntimeError("Path reports do not contain identical fixed links:\n" + details)

    priority = read_priority()
    all_rows: list[dict] = []
    for a, b in sorted(reference):
        row: dict[str, object] = {"from_core": a, "to_core": b}
        for year in YEARS:
            row[f"effective_cost_{year}"] = reports[year][(a, b)]["cost"]
            row[f"path_length_km_{year}"] = reports[year][(a, b)]["length_km"]
        for start, end in INTERVALS:
            row[f"cost_change_{start}_{end}"] = (
                reports[end][(a, b)]["cost"] - reports[start][(a, b)]["cost"]
            )
            row[f"cost_change_percent_{start}_{end}"] = percent_change(
                reports[start][(a, b)]["cost"], reports[end][(a, b)]["cost"]
            )
            row[f"path_length_change_km_{start}_{end}"] = (
                reports[end][(a, b)]["length_km"] - reports[start][(a, b)]["length_km"]
            )
        row["robust_priority_link"] = "yes" if (a, b) in priority else "no"
        if (a, b) in priority:
            row["importance_rank"] = int(priority[(a, b)]["importance_rank"])
            row["edge_betweenness_normalized"] = float(
                priority[(a, b)]["edge_betweenness_normalized"]
            )
        else:
            row["importance_rank"] = ""
            row["edge_betweenness_normalized"] = ""
        all_rows.append(row)

    all_fields = ["from_core", "to_core", "robust_priority_link", "importance_rank",
                  "edge_betweenness_normalized"]
    for year in YEARS:
        all_fields.extend([f"effective_cost_{year}", f"path_length_km_{year}"])
    for start, end in INTERVALS:
        all_fields.extend([
            f"cost_change_{start}_{end}",
            f"cost_change_percent_{start}_{end}",
            f"path_length_change_km_{start}_{end}",
        ])
    write_csv(OUT_ALL, all_rows, all_fields)

    summary_rows: list[dict] = []
    for population, selected in (
        ("all_45_links", all_rows),
        ("robust_32_links", [r for r in all_rows if r["robust_priority_link"] == "yes"]),
    ):
        for start, end in INTERVALS:
            field = f"cost_change_percent_{start}_{end}"
            values = [float(row[field]) for row in selected]
            summary_rows.append({
                "population": population,
                "period": f"{start}-{end}",
                "n_links": len(values),
                "mean_percent_change": statistics.fmean(values),
                "median_percent_change": statistics.median(values),
                "q25_percent_change": quantile(values, 0.25),
                "q75_percent_change": quantile(values, 0.75),
                "minimum_percent_change": min(values),
                "maximum_percent_change": max(values),
                "links_increased": sum(value > 0 for value in values),
                "links_decreased": sum(value < 0 for value in values),
                "links_abs_change_ge_0_1pct": sum(abs(value) >= 0.1 for value in values),
                "links_abs_change_ge_1pct": sum(abs(value) >= 1.0 for value in values),
            })

    summary_fields = list(summary_rows[0])
    write_csv(OUT_SUMMARY, summary_rows, summary_fields)

    robust_rows = [row for row in all_rows if row["robust_priority_link"] == "yes"]
    robust_rows.sort(key=lambda row: int(row["importance_rank"]))
    write_csv(OUT_ROBUST, robust_rows, all_fields)

    figure_status = "not created"
    try:
        import matplotlib.pyplot as plt

        FIGURES.mkdir(parents=True, exist_ok=True)
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), constrained_layout=True)

        labels = [f"{start}–{end}" for start, end in INTERVALS]
        distributions = [
            [float(row[f"cost_change_percent_{start}_{end}"]) for row in robust_rows]
            for start, end in INTERVALS
        ]
        axes[0].boxplot(distributions, tick_labels=labels, showfliers=True)
        axes[0].axhline(0, color="0.35", linewidth=0.8)
        axes[0].set_ylabel("Effective-cost change (%)")
        axes[0].set_title("A. Robust links through time")

        x = [float(row["edge_betweenness_normalized"]) for row in robust_rows]
        y = [float(row["cost_change_percent_2012_2024"]) for row in robust_rows]
        axes[1].scatter(x, y, color="#0072B2", alpha=0.8, edgecolor="white", linewidth=0.4)
        axes[1].axhline(0, color="0.35", linewidth=0.8)
        axes[1].set_xlabel("Normalized edge betweenness")
        axes[1].set_ylabel("2012–2024 effective-cost change (%)")
        axes[1].set_title("B. Network importance versus temporal change")
        for row, x_value, y_value in zip(robust_rows, x, y):
            if int(row["importance_rank"]) <= 5 or abs(y_value) >= 0.1:
                axes[1].annotate(
                    f'{row["from_core"]}–{row["to_core"]}',
                    (x_value, y_value), xytext=(3, 3), textcoords="offset points",
                    fontsize=7,
                )

        fig.suptitle("Modelled effective-cost change for robust candidate links")
        fig.savefig(OUT_FIGURE, dpi=300, bbox_inches="tight")
        plt.close(fig)
        figure_status = str(OUT_FIGURE)
    except Exception as exc:
        print(f"WARNING: CSV outputs succeeded, but the diagnostic figure was not created: {exc}")

    total_values = [float(row["cost_change_percent_2012_2024"]) for row in robust_rows]
    print(f"fixed links verified across all years: {len(all_rows)}")
    print(f"robust links summarized: {len(robust_rows)}")
    print(f"2012-2024 robust-link median change: {statistics.median(total_values):.6f}%")
    print(f"2012-2024 robust-link range: {min(total_values):.6f}% to {max(total_values):.6f}%")
    print(f"robust links with absolute 2012-2024 change >= 1%: {sum(abs(v) >= 1 for v in total_values)}")
    if max(abs(v) for v in total_values) < 1.0:
        print("METHOD NOTE: temporal effective-cost change is weak (<1% for every robust link).")
        print("Treat this as a result to investigate, not evidence of no landscape change.")
        print("Check resistance weighting/scaling and whether least-cost paths are insensitive to localized change.")
    print(f"all-link table: {OUT_ALL}")
    print(f"summary: {OUT_SUMMARY}")
    print(f"robust paper-table input: {OUT_ROBUST}")
    print(f"diagnostic figure: {figure_status}")
    print("No rasters, paths, feature classes, or map layers were changed.")


if __name__ == "__main__":
    main()
