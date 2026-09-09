"""Compile the final report-ready conservation-link evidence table.

This preserves the established literature-consistent priority rule: rank the
preselected core links by their network importance and retain links robust to
the completed weighting, vegetation, and fence checks.  Final Circuitscape
effective-resistance change is appended as quantitative temporal context; it
does not silently re-rank or redefine conservation priorities.
"""
import csv
import datetime as dt
import json
from pathlib import Path


REPORTS = Path(r"C:\cheetah\reports")
PRIORITY = REPORTS / "conservation_priority_links_temporal.csv"
CENTRALITY_CORRECTION = 21.0 / 23.0  # 231 directed-edge denominator -> 253 undirected edges


def newest_effective_resistance_table():
    candidates = sorted(REPORTS.glob("final_effective_resistance_change_2012_2024_*.csv"))
    if not candidates:
        raise FileNotFoundError("Run summarize_final_effective_resistance_change.py first")
    return candidates[-1]


def pair(row, first="from_core", second="to_core"):
    return tuple(sorted((int(row[first]), int(row[second]))))


def as_number(row, name):
    value = row.get(name, "")
    return None if value in (None, "") else float(value)


def main():
    if not PRIORITY.is_file():
        raise FileNotFoundError(PRIORITY)
    resistance_table = newest_effective_resistance_table()
    with resistance_table.open(newline="", encoding="utf-8-sig") as handle:
        resistance = {pair(row): row for row in csv.DictReader(handle)}
    with PRIORITY.open(newline="", encoding="utf-8-sig") as handle:
        original = list(csv.DictReader(handle))
    if len(original) != 32:
        raise RuntimeError(f"Expected 32 robust primary-priority links, found {len(original)}")

    rows = []
    for source in original:
        key = pair(source)
        final = resistance.get(key)
        if final is None:
            raise RuntimeError(f"Selected link {key[0]}-{key[1]} is absent from final Circuitscape output")
        rank = int(source["importance_rank"])
        old_centrality = as_number(source, "edge_betweenness_normalized")
        # This source table is the already-filtered 32-link primary set. Keep
        # its explicit field when present, but never downgrade a row merely
        # because an older export omitted that redundant column value.
        priority = source.get("primary_priority_eligible_final", "yes").strip().lower() != "no"
        rows.append({
            "from_core": key[0],
            "to_core": key[1],
            "importance_rank": rank,
            "edge_betweenness_normalized_corrected": None if old_centrality is None else old_centrality * CENTRALITY_CORRECTION,
            "link_type": source.get("link_type", ""),
            "straight_line_distance_km": as_number(source, "straight_line_distance_km"),
            "priority_evidence_status": "primary conservation-priority evidence" if priority else "supporting / uncertainty context",
            "weight_robust": source.get("weight_robust", ""),
            "fence_robust": source.get("fence_robust", ""),
            "vegetation_direction_robust": source.get("vegetation_direction_robust", ""),
            "prior_temporal_interpretation": source.get("temporal_direction_interpretation", ""),
            "effective_resistance_2012": float(final["effective_resistance_2012"]),
            "effective_resistance_2016": float(final["effective_resistance_2016"]),
            "effective_resistance_2020": float(final["effective_resistance_2020"]),
            "effective_resistance_2024": float(final["effective_resistance_2024"]),
            "final_effective_resistance_change_percent_2012_2024": float(final["percent_change_2012_2024"]),
        })
    rows.sort(key=lambda row: row["importance_rank"])
    primary = [row for row in rows if row["priority_evidence_status"] == "primary conservation-priority evidence"]
    if len(primary) != 32:
        raise RuntimeError(f"Expected all 32 rows to be robust primary links, found {len(primary)}")

    primary_changes = [row["final_effective_resistance_change_percent_2012_2024"] for row in primary]
    summary = {
        "created": dt.datetime.now().isoformat(timespec="seconds"),
        "source_priority_table": str(PRIORITY),
        "source_final_effective_resistance_table": str(resistance_table),
        "selected_link_count": len(rows),
        "primary_priority_link_count": len(primary),
        "priority_rule": "Existing 32-link robust-priority designation retained; final effective resistance appended as temporal context, not a new ranking criterion.",
        "centrality_note": "Normalized edge-betweenness values were corrected by 21/23 because the graph has 253 undirected pairs; ranks are unchanged.",
        "primary_link_final_effective_resistance_change": {
            "median_percent": sorted(primary_changes)[len(primary_changes) // 2] if len(primary_changes) % 2 else (sorted(primary_changes)[15] + sorted(primary_changes)[16]) / 2,
            "increased": sum(value > 0 for value in primary_changes),
            "decreased": sum(value < 0 for value in primary_changes),
        },
        "interpretation_limits": [
            "Priority status reflects modelled structural-connectivity evidence, not observed cheetah use or a legal conservation designation.",
            "Effective-resistance change is reported continuously; no arbitrary biological change threshold was imposed.",
            "Final current and endpoint high-current maps provide complementary screening context and do not replace the link evidence table.",
        ],
    }
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = REPORTS / f"final_conservation_link_evidence_{stamp}.csv"
    with out.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    record = REPORTS / f"final_conservation_link_evidence_{stamp}.json"
    record.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    brief = REPORTS / f"final_conservation_link_evidence_{stamp}.md"
    brief.write_text(
        "# Final conservation-link evidence\n\n"
        f"- Selected links assessed: {len(rows)}\n"
        f"- Robust primary-priority links: {len(primary)}\n"
        f"- Primary-link median final effective-resistance change, 2012–2024: {summary['primary_link_final_effective_resistance_change']['median_percent']:.3f}%\n"
        f"- Primary links with increase / decrease: {summary['primary_link_final_effective_resistance_change']['increased']} / {summary['primary_link_final_effective_resistance_change']['decreased']}\n\n"
        "Priority labels retain the prior robustness-based rule. Effective resistance is added as continuous temporal context rather than a new biological cutoff.\n",
        encoding="utf-8",
    )
    print("selected links compiled:", len(rows))
    print("robust primary-priority links retained:", len(primary))
    print("primary-link median final effective-resistance change:", f"{summary['primary_link_final_effective_resistance_change']['median_percent']:.3f}%")
    print("table:", out)
    print("method record:", record)
    print("brief:", brief)
    print("Complete. Existing GIS data, maps, priority designations, and Circuitscape outputs were unchanged.")


if __name__ == "__main__":
    main()
