"""Create a publication-ready temporal vegetation sensitivity figure.

Panel A shows median link-level effective-cost change with interquartile ranges
for each interval. Panel B shows the full 2012-2024 link-level distribution.
Negative values mean lower modeled resistance; positive values mean higher
modeled resistance. The source CSVs remain unchanged.
"""

from pathlib import Path
import csv

import matplotlib.pyplot as plt
import numpy as np


REPORTS = Path(r"C:\cheetah\reports")
FIGURES = REPORTS / "figures"
SUMMARY = REPORTS / "temporal_vegetation_interval_summary.csv"
CHANGES = REPORTS / "temporal_vegetation_change_by_link.csv"
OUT_PNG = FIGURES / "fig_temporal_vegetation_sensitivity.png"
OUT_PDF = FIGURES / "fig_temporal_vegetation_sensitivity.pdf"
OUT_ALT = FIGURES / "fig_temporal_vegetation_sensitivity_alt_text.md"

SCENARIOS = ("veg_low", "veg_balanced", "veg_high")
LABELS = {
    "veg_low": "Vegetation low",
    "veg_balanced": "Vegetation balanced",
    "veg_high": "Vegetation high",
}
COLORS = {
    "veg_low": "#0072B2",
    "veg_balanced": "#E69F00",
    "veg_high": "#6A3D9A",
}
MARKERS = {"veg_low": "o", "veg_balanced": "s", "veg_high": "^"}
LINESTYLES = {"veg_low": "-", "veg_balanced": "--", "veg_high": ":"}
PERIODS = ("2012-2016", "2016-2020", "2020-2024", "2012-2024")


def read_csv(path):
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def main():
    summary = read_csv(SUMMARY)
    changes = read_csv(CHANGES)
    lookup = {(row["scenario"], row["period"]): row for row in summary}
    if len(lookup) != len(SCENARIOS) * len(PERIODS):
        raise RuntimeError("Interval summary is incomplete")

    FIGURES.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 9,
        "axes.titlesize": 11,
        "axes.labelsize": 9.5,
        "xtick.labelsize": 8.5,
        "ytick.labelsize": 8.5,
        "legend.fontsize": 8.5,
        "axes.spines.top": False,
        "axes.spines.right": False,
    })

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.8, 4.4), gridspec_kw={"width_ratios": [1.45, 1]})

    x = np.arange(len(PERIODS))
    offsets = {"veg_low": -0.08, "veg_balanced": 0.0, "veg_high": 0.08}
    for scenario in SCENARIOS:
        medians = np.array([float(lookup[(scenario, period)]["median_percent_change"]) for period in PERIODS])
        q25 = np.array([float(lookup[(scenario, period)]["q25_percent_change"]) for period in PERIODS])
        q75 = np.array([float(lookup[(scenario, period)]["q75_percent_change"]) for period in PERIODS])
        ax1.errorbar(
            x + offsets[scenario],
            medians,
            yerr=np.vstack((medians - q25, q75 - medians)),
            color=COLORS[scenario],
            marker=MARKERS[scenario],
            linestyle=LINESTYLES[scenario],
            linewidth=1.5,
            markersize=5,
            capsize=3,
            label=LABELS[scenario],
        )
    ax1.axhline(0, color="#4D4D4D", linewidth=0.9)
    ax1.set_xticks(x, [period.replace("-", "–") for period in PERIODS])
    ax1.set_ylabel("Effective-cost change across links (%)")
    ax1.set_title("A  Recent increases reverse earlier cost declines", loc="left", fontweight="bold")
    ax1.grid(axis="y", color="#D9D9D9", linewidth=0.6)
    ax1.legend(frameon=False, loc="upper left")

    distributions = []
    for scenario in SCENARIOS:
        values = [
            float(row["cost_change_percent_2012_2024"])
            for row in changes if row["scenario"] == scenario
        ]
        if len(values) != 45:
            raise RuntimeError(f"Expected 45 links for {scenario}; found {len(values)}")
        distributions.append(values)
    box = ax2.boxplot(
        distributions,
        patch_artist=True,
        widths=0.55,
        showfliers=False,
        medianprops={"color": "black", "linewidth": 1.3},
        whiskerprops={"color": "#555555"},
        capprops={"color": "#555555"},
    )
    for patch, scenario in zip(box["boxes"], SCENARIOS):
        patch.set_facecolor(COLORS[scenario])
        patch.set_alpha(0.55)
        patch.set_edgecolor(COLORS[scenario])

    rng = np.random.default_rng(42)
    for position, (scenario, values) in enumerate(zip(SCENARIOS, distributions), 1):
        jitter = rng.uniform(-0.13, 0.13, len(values))
        ax2.scatter(
            np.full(len(values), position) + jitter,
            values,
            s=11,
            facecolor="white",
            edgecolor=COLORS[scenario],
            linewidth=0.65,
            alpha=0.8,
            zorder=3,
        )
    ax2.axhline(0, color="#4D4D4D", linewidth=0.9)
    ax2.set_xticks((1, 2, 3), ("Low", "Balanced", "High"))
    ax2.set_ylabel("2012–2024 effective-cost change (%)")
    ax2.set_title("B  Magnitude depends on vegetation weighting", loc="left", fontweight="bold")
    ax2.grid(axis="y", color="#D9D9D9", linewidth=0.6)

    fig.suptitle(
        "Temporal vegetation sensitivity of modeled core-to-core connectivity",
        fontsize=12.5,
        fontweight="bold",
        x=0.5,
        y=1.01,
    )
    fig.text(
        0.5,
        -0.015,
        "Points and intervals summarize 45 fixed core pairs. Negative values indicate lower modeled resistance; positive values indicate higher modeled resistance.",
        ha="center",
        va="top",
        fontsize=8.2,
    )
    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=300, bbox_inches="tight")
    fig.savefig(OUT_PDF, bbox_inches="tight")
    plt.close(fig)

    OUT_ALT.write_text(
        "# Alt text\n\n"
        "Two-panel figure comparing effective-cost change for 45 fixed cheetah core "
        "pairs under low, balanced, and high vegetation-resistance assumptions. "
        "Panel A shows median and interquartile change for 2012–2016, 2016–2020, "
        "2020–2024, and 2012–2024. Median costs declined in the first two intervals "
        "and increased from 2020 to 2024 under all three assumptions. Panel B shows "
        "the link-level 2012–2024 distributions; increasing vegetation weight widens "
        "the magnitude of both positive and negative changes. Forty-three of 45 links "
        "retained the same direction across all three scenarios.\n",
        encoding="utf-8",
    )
    print(f"figure PNG: {OUT_PNG}")
    print(f"figure PDF: {OUT_PDF}")
    print(f"alt text: {OUT_ALT}")


if __name__ == "__main__":
    main()
