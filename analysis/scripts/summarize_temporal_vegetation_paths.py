"""Validate and summarize the temporal vegetation-sensitivity path grid.

This is a read-only reporting step. It expects 45 successful core pairs for
each of three vegetation scenarios and four temporal snapshots. It writes
long-form results, per-link temporal changes, interval summaries, and a
scenario-agreement table. It does not assign new biological cutoffs or alter
the existing conservation-priority classification.
"""

from pathlib import Path
import csv
import math
import statistics


REPORTS = Path(r"C:\cheetah\reports")
SCENARIOS = ("veg_low", "veg_balanced", "veg_high")
YEARS = (2012, 2016, 2020, 2024)
INTERVALS = ((2012, 2016), (2016, 2020), (2020, 2024), (2012, 2024))
EXPECTED_LINKS = 45

OUT_LONG = REPORTS / "temporal_vegetation_paths_long.csv"
OUT_CHANGE = REPORTS / "temporal_vegetation_change_by_link.csv"
OUT_SUMMARY = REPORTS / "temporal_vegetation_interval_summary.csv"
OUT_AGREEMENT = REPORTS / "temporal_vegetation_scenario_agreement.csv"
OUT_QC = REPORTS / "temporal_vegetation_qc.txt"


def pair_key(row):
    a, b = int(row["from_core"]), int(row["to_core"])
    return (a, b) if a <= b else (b, a)


def read_report(scenario, year):
    path = REPORTS / f"least_cost_paths_temporal_{scenario}_{year}.csv"
    if not path.exists():
        raise FileNotFoundError(path)
    records = {}
    failures = []
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            key = pair_key(row)
            if row.get("status", "").upper() != "OK":
                failures.append((key, row.get("status", "")))
                continue
            if key in records:
                raise RuntimeError(f"Duplicate pair {key} in {path}")
            length = float(row["path_length_km"])
            cost = float(row["accumulated_cost_raw"])
            if not math.isfinite(length) or not math.isfinite(cost):
                raise RuntimeError(f"Non-finite path result for {key} in {path}")
            records[key] = {"path_length_km": length, "cost_raw": cost}
    if failures:
        raise RuntimeError(f"Failed paths remain in {path}: {failures}")
    if len(records) != EXPECTED_LINKS:
        raise RuntimeError(f"Expected {EXPECTED_LINKS} successful links in {path}; found {len(records)}")
    return path, records


def percent_change(start, end):
    return ((end - start) / start) * 100.0 if start != 0 else math.nan


def quantile(values, probability):
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def direction(value, tolerance=1e-12):
    if value > tolerance:
        return "increase"
    if value < -tolerance:
        return "decrease"
    return "no_change"


def main():
    data = {}
    files = []
    reference_pairs = None
    for scenario in SCENARIOS:
        for year in YEARS:
            path, records = read_report(scenario, year)
            files.append(path)
            data[(scenario, year)] = records
            pairs = set(records)
            if reference_pairs is None:
                reference_pairs = pairs
            elif pairs != reference_pairs:
                missing = sorted(reference_pairs - pairs)
                extra = sorted(pairs - reference_pairs)
                raise RuntimeError(
                    f"Core-pair mismatch in {path}; missing={missing}, extra={extra}"
                )

    long_rows = []
    for scenario in SCENARIOS:
        for year in YEARS:
            for a, b in sorted(reference_pairs):
                record = data[(scenario, year)][(a, b)]
                long_rows.append({
                    "scenario": scenario,
                    "year": year,
                    "from_core": a,
                    "to_core": b,
                    **record,
                })
    write_csv(
        OUT_LONG,
        long_rows,
        ["scenario", "year", "from_core", "to_core", "path_length_km", "cost_raw"],
    )

    change_rows = []
    for scenario in SCENARIOS:
        for a, b in sorted(reference_pairs):
            row = {"scenario": scenario, "from_core": a, "to_core": b}
            for year in YEARS:
                record = data[(scenario, year)][(a, b)]
                row[f"cost_{year}"] = record["cost_raw"]
                row[f"path_length_km_{year}"] = record["path_length_km"]
            for start, end in INTERVALS:
                start_record = data[(scenario, start)][(a, b)]
                end_record = data[(scenario, end)][(a, b)]
                row[f"cost_change_{start}_{end}"] = end_record["cost_raw"] - start_record["cost_raw"]
                row[f"cost_change_percent_{start}_{end}"] = percent_change(
                    start_record["cost_raw"], end_record["cost_raw"]
                )
                row[f"path_length_change_km_{start}_{end}"] = (
                    end_record["path_length_km"] - start_record["path_length_km"]
                )
            change_rows.append(row)

    change_fields = ["scenario", "from_core", "to_core"]
    for year in YEARS:
        change_fields.extend([f"cost_{year}", f"path_length_km_{year}"])
    for start, end in INTERVALS:
        change_fields.extend([
            f"cost_change_{start}_{end}",
            f"cost_change_percent_{start}_{end}",
            f"path_length_change_km_{start}_{end}",
        ])
    write_csv(OUT_CHANGE, change_rows, change_fields)

    summary_rows = []
    for scenario in SCENARIOS:
        selected = [row for row in change_rows if row["scenario"] == scenario]
        for start, end in INTERVALS:
            field = f"cost_change_percent_{start}_{end}"
            values = [float(row[field]) for row in selected]
            summary_rows.append({
                "scenario": scenario,
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
            })
    write_csv(OUT_SUMMARY, summary_rows, list(summary_rows[0]))

    by_scenario_pair = {
        (row["scenario"], int(row["from_core"]), int(row["to_core"])): row
        for row in change_rows
    }
    agreement_rows = []
    for a, b in sorted(reference_pairs):
        changes = {
            scenario: float(
                by_scenario_pair[(scenario, a, b)]["cost_change_percent_2012_2024"]
            )
            for scenario in SCENARIOS
        }
        directions = {scenario: direction(value) for scenario, value in changes.items()}
        unique_directions = set(directions.values())
        agreement_rows.append({
            "from_core": a,
            "to_core": b,
            "veg_low_change_percent_2012_2024": changes["veg_low"],
            "veg_balanced_change_percent_2012_2024": changes["veg_balanced"],
            "veg_high_change_percent_2012_2024": changes["veg_high"],
            "minimum_change_percent": min(changes.values()),
            "maximum_change_percent": max(changes.values()),
            "median_change_percent": statistics.median(changes.values()),
            "direction_veg_low": directions["veg_low"],
            "direction_veg_balanced": directions["veg_balanced"],
            "direction_veg_high": directions["veg_high"],
            "direction_consistent_across_scenarios": "yes" if len(unique_directions) == 1 else "no",
            "interpretation": (
                "directionally stable across vegetation assumptions"
                if len(unique_directions) == 1
                else "sensitive to vegetation assumption; retain as uncertainty"
            ),
        })
    write_csv(OUT_AGREEMENT, agreement_rows, list(agreement_rows[0]))

    stable = sum(row["direction_consistent_across_scenarios"] == "yes" for row in agreement_rows)
    with OUT_QC.open("w", encoding="utf-8") as handle:
        handle.write("Temporal vegetation least-cost path QC\n")
        handle.write(f"Reports checked: {len(files)}\n")
        handle.write(f"Successful paths checked: {len(long_rows)}\n")
        handle.write(f"Unique core pairs: {len(reference_pairs)}\n")
        handle.write(f"Directionally consistent pairs, 2012-2024: {stable}/{len(reference_pairs)}\n")
        handle.write("No biological cutoff was assigned by this reporting script.\n")

    print(f"validated reports: {len(files)}")
    print(f"validated paths: {len(long_rows)}")
    print(f"directionally consistent links, 2012-2024: {stable}/{len(reference_pairs)}")
    print(f"long results: {OUT_LONG}")
    print(f"change table: {OUT_CHANGE}")
    print(f"interval summary: {OUT_SUMMARY}")
    print(f"scenario agreement: {OUT_AGREEMENT}")
    print(f"QC report: {OUT_QC}")


if __name__ == "__main__":
    main()
