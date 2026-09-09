"""Compile final completed outputs into manuscript tables and an evidence checklist.

This script does not write manuscript prose or modify model outputs.  It copies
the exact completed-analysis values into a dated results package so the author
can write the Results section directly from traceable tables.
"""
import csv
import datetime as dt
import json
from pathlib import Path

REPORTS = Path(r"C:\cheetah\reports")
OUT_DIR = REPORTS / "manuscript_results_package"


def latest(pattern):
    files = sorted(REPORTS.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise FileNotFoundError(f"No report matches {pattern}")
    return files[0]


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    effective_source = latest("final_effective_resistance_change_2012_2024_*.csv")
    current_source = latest("final_current_temporal_evidence_*.csv")
    priority_source = latest("final_conservation_link_evidence_*.csv")
    protection_source = latest("protected_area_high_current_coverage_*.csv")

    effective = read_csv(effective_source)
    priority = read_csv(priority_source)
    protection = read_csv(protection_source)
    current_lines = current_source.read_text(encoding="utf-8-sig").strip().splitlines()
    split = current_lines.index("")
    current = list(csv.DictReader(current_lines[:split]))
    current_classes = list(csv.DictReader(current_lines[split + 1:]))

    selected = [r for r in effective if r["selected_neighbor_link"].lower() == "yes"]
    robust = [r for r in priority if r["priority_evidence_status"] == "primary conservation-priority evidence"]
    percent_changes = [float(r["percent_change_2012_2024"]) for r in effective]
    selected_changes = [float(r["percent_change_2012_2024"]) for r in selected]
    robust_changes = [float(r["final_effective_resistance_change_percent_2012_2024"]) for r in robust]
    med = lambda values: sorted(values)[len(values) // 2] if len(values) % 2 else (sorted(values)[len(values)//2-1] + sorted(values)[len(values)//2]) / 2
    largest_increase = max(effective, key=lambda r: float(r["percent_change_2012_2024"]))
    largest_decrease = min(effective, key=lambda r: float(r["percent_change_2012_2024"]))

    overview = [
        {"metric": "Final current-flow snapshots", "value": "4 (2012, 2016, 2020, 2024)", "unit_or_note": "253/253 pairwise focal-region pairs connected each year"},
        {"metric": "Fixed density cores", "value": "23", "unit_or_note": "historical baseline; fixed across snapshots"},
        {"metric": "Selected neighboring core links", "value": str(len(selected)), "unit_or_note": "fixed core-pair comparison set"},
        {"metric": "Primary-priority links", "value": str(len(robust)), "unit_or_note": "robust under stated weight/fence screens; not literal routes"},
        {"metric": "All-pair median modeled effective-resistance change, 2012–2024", "value": f"{med(percent_changes):.3f}", "unit_or_note": "percent"},
        {"metric": "Selected-link median modeled effective-resistance change, 2012–2024", "value": f"{med(selected_changes):.3f}", "unit_or_note": "percent"},
        {"metric": "Primary-priority median modeled effective-resistance change, 2012–2024", "value": f"{med(robust_changes):.3f}", "unit_or_note": "percent"},
        {"metric": "Largest all-pair increase", "value": f"{largest_increase['from_core']}–{largest_increase['to_core']}: {float(largest_increase['percent_change_2012_2024']):+.3f}", "unit_or_note": "percent"},
        {"metric": "Largest all-pair decrease", "value": f"{largest_decrease['from_core']}–{largest_decrease['to_core']}: {float(largest_decrease['percent_change_2012_2024']):+.3f}", "unit_or_note": "percent"},
    ]
    write_csv(OUT_DIR / f"table_results_overview_{stamp}.csv", ["metric", "value", "unit_or_note"], overview)
    write_csv(OUT_DIR / f"table_protected_area_coverage_{stamp}.csv", list(protection[0]), protection)
    write_csv(OUT_DIR / f"table_primary_priority_links_{stamp}.csv", list(priority[0]), robust)
    write_csv(OUT_DIR / f"table_current_temporal_evidence_{stamp}.csv", list(current[0]), current)
    write_csv(OUT_DIR / f"table_current_endpoint_classes_{stamp}.csv", list(current_classes[0]), current_classes)

    evidence = {
        "generated": dt.datetime.now().isoformat(timespec="seconds"),
        "source_reports": {
            "effective_resistance": str(effective_source), "current_temporal": str(current_source),
            "priority_links": str(priority_source), "protected_area": str(protection_source),
        },
        "overview": overview,
        "writing_guardrails": [
            "Call outputs modeled structural connectivity, modeled current concentration, or modeled effective resistance—not observed cheetah occurrence, movement, or validated corridors.",
            "Treat protected-area overlay as descriptive legal-protection context; it does not measure management effectiveness or conservation outcomes.",
            "Core-pair links identify network relationships and priority evidence; they are not literal animal routes.",
            "Use the final vegetation-balanced, finite-fence model for primary results; reference/alternative scenarios remain sensitivity context.",
        ],
        "figure_set": [
            "Figure 1: High-current concentration areas under final 2024 model.",
            "Figure 2: Persistence and endpoint change in high modeled current, 2012–2024.",
            "Figure 3: Robust conservation-priority core-pair links.",
            "Figure 4: Protected-area context of high-current concentration, 2024.",
        ],
    }
    json_path = OUT_DIR / f"manuscript_results_evidence_{stamp}.json"
    json_path.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    md_path = OUT_DIR / f"READ_ME_FIRST_{stamp}.md"
    md_path.write_text(
        "# Completed results package\n\n"
        "Use the companion CSVs as the source of numerical values. This package intentionally does not draft Results prose.\n\n"
        "## Recommended reporting order\n\n"
        "1. State the four final modeled-current snapshots and all-pair completion.\n"
        "2. Describe temporal persistence/endpoint change in high modeled current.\n"
        "3. Report effective-resistance change across all pairs, selected links, and primary-priority links.\n"
        "4. Present the robust priority-link evidence.\n"
        "5. Report the protected-area overlay as descriptive coverage context.\n\n"
        "## Guardrails\n\n- " + "\n- ".join(evidence["writing_guardrails"]) + "\n",
        encoding="utf-8",
    )
    print("created results package:", OUT_DIR)
    print("overview table:", OUT_DIR / f"table_results_overview_{stamp}.csv")
    print("read first:", md_path)


if __name__ == "__main__":
    main()
