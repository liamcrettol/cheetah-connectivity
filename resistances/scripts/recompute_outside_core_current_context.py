"""Recompute current-derived results on the outside-core domain.

Why this exists
---------------
Every cell in the top 10%, 5% and 1% of positive final current falls inside an
input core, in all four snapshot years. That is a property of the pairwise
source/ground experiment: each of the 23 focal regions participates in 22 of the
253 pairs, and 22/253 = 0.08696 against a reported 90th-percentile current of
0.08702, so core cells sit on a plateau created by focal-node current injection.
The cores also cover 246,654 of the 2,503,870 valid model cells (9.85%), which is
slightly more than a top decile, so the decile fits inside them with room to
spare.

Consequently the source-inclusive protected-area comparison and the
"current geography is stationary" observation both describe the fixed core
footprint rather than the connecting landscape. This script recomputes those
results on the domain the paper actually wants to talk about: valid model cells
outside cores carrying positive modelled current.

``set_focal_node_currents_to_zero`` is documented as not implemented in
Circuitscape 5 (installed 5.17.1), so this is post-hoc domain masking. It removes
the core plateau from the reported statistics; it does not remove focal-region
influence from the underlying solve. State that when reporting.

Reads only. Writes CSV/JSON/PNG to REPORTS. No geodatabase is modified.

Outputs
-------
outside_core_current_pa_curve_<stamp>.csv      PA coverage vs current percentile, per year
outside_core_current_summary_<stamp>.json      headline values, crossover, spatial null
outside_core_temporal_overlap_<stamp>.csv      top-decile Jaccard between years
outside_core_pa_coverage_curve_<stamp>.png     the curve, for the paper
"""

from __future__ import annotations

import csv
import datetime as dt
import json
from pathlib import Path

import numpy as np
from osgeo import gdal

gdal.UseExceptions()

WORK_GDB = r"C:\cheetah\gdb\cheetah_working.gdb"
CURRENT_GDB = r"C:\cheetah\circuitscape\derived\current_final_balanced_fence.gdb"
CORE = "cheetah_core_primary_density051_min500_1km"
PA = "wdpa_aug2026_coverage_1km"
CURRENT_TEMPLATE = "current_final_balanced_fence_{year}_mean"
YEARS = (2012, 2016, 2020, 2024)
REPORTS = Path(r"C:\cheetah\reports")

# Percentiles of positive outside-core current at which coverage is reported.
CURVE = (50, 60, 70, 75, 80, 85, 90, 92.5, 95, 97.5, 99, 99.5, 99.9)
HEADLINE = (90, 95, 99)

# Core-exclusion buffers, in cells (1 km grid). Grid-distance sensitivity only;
# these are not biological buffer recommendations.
BUFFERS_KM = (0, 1, 5, 10)

# Spatial null. Block edge length in cells (= km on this grid). Two scales are
# reported so the reader can see how much the assumed autocorrelation scale
# matters; neither is fitted to the data.
BLOCK_SCALES_KM = (25, 50)
N_DRAWS = 499
RNG_SEED = 20260909

NP_DTYPE = {
    gdal.GDT_Byte: "u1",
    gdal.GDT_Int16: "i2",
    gdal.GDT_UInt16: "u2",
    gdal.GDT_Int32: "i4",
    gdal.GDT_UInt32: "u4",
    gdal.GDT_Float32: "f4",
    gdal.GDT_Float64: "f8",
}


def read_raster(gdb: str, name: str):
    """Read a file-geodatabase raster without gdal_array (broken in this env)."""
    dataset = gdal.Open(f'OpenFileGDB:"{gdb}":{name}')
    band = dataset.GetRasterBand(1)
    raw = band.ReadRaster(0, 0, dataset.RasterXSize, dataset.RasterYSize)
    array = np.frombuffer(raw, dtype=NP_DTYPE[band.DataType])
    array = array.reshape(dataset.RasterYSize, dataset.RasterXSize)
    geometry = (dataset.RasterXSize, dataset.RasterYSize, dataset.GetGeoTransform())
    return array, band.GetNoDataValue(), geometry


def dilate(mask: np.ndarray, radius_cells: int) -> np.ndarray:
    """Square-kernel dilation by shifting. Chebyshev distance, adequate here."""
    if radius_cells <= 0:
        return mask
    out = mask.copy()
    for dy in range(-radius_cells, radius_cells + 1):
        for dx in range(-radius_cells, radius_cells + 1):
            if dy == 0 and dx == 0:
                continue
            out |= np.roll(np.roll(mask, dy, axis=0), dx, axis=1)
    return out


def coverage(pa: np.ndarray, mask: np.ndarray) -> float:
    n = int(mask.sum())
    return float(100.0 * pa[mask].mean()) if n else float("nan")


def crossover_percentile(pcts, observed, background) -> float | None:
    """Percentile at which coverage first crosses the background rate."""
    for i in range(1, len(pcts)):
        a, b = observed[i - 1] - background, observed[i] - background
        if np.isnan(a) or np.isnan(b) or a == b:
            continue
        if (a < 0) != (b < 0):
            return float(pcts[i - 1] + (pcts[i] - pcts[i - 1]) * (-a) / (b - a))
    return None


def block_null(pa, domain, target_cells, block_cells, n_draws, rng):
    """Spatial null: assemble a same-sized selection from whole square blocks.

    Why not a toroidal shift of the observed selection. The outside-core domain
    is irregular and covers only about 41% of the grid, so a rigid shift pushes
    most of the selection off-domain: median retention was 46% of the observed
    cell count and 27% of draws retained under a tenth of it. Those small
    retained samples produce extreme coverage values and a null interval that
    spans almost the whole range, which has no power to distinguish anything.

    Blocks stay inside the domain by construction and preserve clumping at the
    block scale, which is what a cell-wise hypergeometric draw fails to do. The
    block scale is the assumed autocorrelation scale and is reported, not fitted.
    """
    rows, cols = domain.shape
    row_index = np.arange(rows) // block_cells
    col_index = np.arange(cols) // block_cells
    block_id = (row_index[:, None] * (cols // block_cells + 1) + col_index[None, :])

    ids = block_id[domain]
    protected = pa[domain]
    order = np.argsort(ids, kind="stable")
    ids_sorted, protected_sorted = ids[order], protected[order]
    boundaries = np.flatnonzero(np.diff(ids_sorted)) + 1
    counts = np.diff(np.concatenate(([0], boundaries, [ids_sorted.size])))
    protected_counts = np.add.reduceat(protected_sorted.astype(np.int64),
                                       np.concatenate(([0], boundaries)))

    n_blocks = counts.size
    draws = []
    for _ in range(n_draws):
        shuffled = rng.permutation(n_blocks)
        cumulative = np.cumsum(counts[shuffled])
        take = int(np.searchsorted(cumulative, target_cells)) + 1
        chosen = shuffled[:take]
        total = int(counts[chosen].sum())
        if total:
            draws.append(100.0 * float(protected_counts[chosen].sum()) / total)
    return np.asarray(draws, dtype=float), n_blocks


def main() -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    rng = np.random.default_rng(RNG_SEED)

    core, _, core_geometry = read_raster(WORK_GDB, CORE)
    pa_raw, _, pa_geometry = read_raster(WORK_GDB, PA)
    pa = pa_raw.astype(bool)
    in_core = core > 0

    currents, valids, geometries = {}, {}, [core_geometry, pa_geometry]
    for year in YEARS:
        array, nodata, geometry = read_raster(CURRENT_GDB, CURRENT_TEMPLATE.format(year=year))
        currents[year] = array
        valids[year] = np.isfinite(array) & (array != nodata)
        geometries.append(geometry)

    if len({(g[0], g[1], tuple(round(v, 6) for v in g[2])) for g in geometries}) != 1:
        raise RuntimeError("Input grids do not share size and geotransform")

    curve_rows, headline, temporal = [], {}, {}

    for year in YEARS:
        current, valid = currents[year], valids[year]
        outside_all = valid & ~in_core
        domain = outside_all & (current > 0)

        # Matched background: the population the selection is actually drawn
        # from. The wider outside-core background (which includes zero-current
        # cells) is reported alongside because the earlier audit used it.
        background = coverage(pa, domain)
        background_incl_zero = coverage(pa, outside_all)

        values = current[domain]
        observed_curve = []
        for percentile in CURVE:
            threshold = float(np.percentile(values, percentile))
            selection = domain & (current >= threshold)
            observed = coverage(pa, selection)
            observed_curve.append(observed)
            curve_rows.append({
                "year": year,
                "percentile": percentile,
                "current_threshold": threshold,
                "selected_cells": int(selection.sum()),
                "protected_percent": round(observed, 5),
                "background_percent_matched": round(background, 5),
                "difference_percentage_points": round(observed - background, 5),
            })

        headline[year] = {
            "domain_cells": int(domain.sum()),
            "outside_core_cells_including_zero_current": int(outside_all.sum()),
            "background_percent_matched": round(background, 5),
            "background_percent_including_zero_current": round(background_incl_zero, 5),
            "crossover_percentile": crossover_percentile(CURVE, observed_curve, background),
            "bands": {},
            "buffer_sensitivity": [],
        }

        for percentile in HEADLINE:
            threshold = float(np.percentile(values, percentile))
            selection = domain & (current >= threshold)
            entry = {
                "current_threshold": threshold,
                "selected_cells": int(selection.sum()),
                "protected_percent": round(coverage(pa, selection), 5),
                "difference_percentage_points": round(coverage(pa, selection) - background, 5),
            }
            if year == 2024:
                observed = coverage(pa, selection)
                entry["spatial_null"] = {}
                for block_km in BLOCK_SCALES_KM:
                    draws, n_blocks = block_null(pa, domain, int(selection.sum()),
                                                 block_km, N_DRAWS, rng)
                    entry["spatial_null"][f"{block_km}km_blocks"] = {
                        "method": (f"{len(draws)} draws assembling a same-sized selection "
                                   f"from whole {block_km} km blocks within the domain"),
                        "blocks_in_domain": int(n_blocks),
                        "mean_percent": round(float(draws.mean()), 5),
                        "p025_percent": round(float(np.percentile(draws, 2.5)), 5),
                        "p975_percent": round(float(np.percentile(draws, 97.5)), 5),
                        "one_sided_low_tail_probability":
                            float((np.count_nonzero(draws <= observed) + 1) / (len(draws) + 1)),
                        "one_sided_high_tail_probability":
                            float((np.count_nonzero(draws >= observed) + 1) / (len(draws) + 1)),
                    }
            headline[year]["bands"][percentile] = entry

        for buffer_km in BUFFERS_KM:
            excluded = dilate(in_core, buffer_km)
            buffered_domain = valid & ~excluded & (current > 0)
            if not buffered_domain.any():
                continue
            buffered_values = current[buffered_domain]
            buffered_background = coverage(pa, buffered_domain)
            for percentile in HEADLINE:
                threshold = float(np.percentile(buffered_values, percentile))
                selection = buffered_domain & (current >= threshold)
                headline[year]["buffer_sensitivity"].append({
                    "core_exclusion_buffer_km": buffer_km,
                    "percentile": percentile,
                    "selected_cells": int(selection.sum()),
                    "protected_percent": round(coverage(pa, selection), 5),
                    "background_percent_matched": round(buffered_background, 5),
                })

        threshold_90 = float(np.percentile(values, 90))
        temporal[year] = domain & (current >= threshold_90)

    overlap_rows = []
    pairs = [(YEARS[i], YEARS[i + 1]) for i in range(len(YEARS) - 1)] + [(YEARS[0], YEARS[-1])]
    for early, late in pairs:
        a, b = temporal[early], temporal[late]
        intersection, union = int((a & b).sum()), int((a | b).sum())
        overlap_rows.append({
            "early_year": early,
            "late_year": late,
            "early_cells": int(a.sum()),
            "late_cells": int(b.sum()),
            "intersection": intersection,
            "union": union,
            "jaccard": round(intersection / union, 6) if union else None,
        })

    curve_path = REPORTS / f"outside_core_current_pa_curve_{stamp}.csv"
    with curve_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(curve_rows[0]))
        writer.writeheader()
        writer.writerows(curve_rows)

    overlap_path = REPORTS / f"outside_core_temporal_overlap_{stamp}.csv"
    with overlap_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(overlap_rows[0]))
        writer.writeheader()
        writer.writerows(overlap_rows)

    summary_path = REPORTS / f"outside_core_current_summary_{stamp}.json"
    summary_path.write_text(json.dumps({
        "created": dt.datetime.now().isoformat(timespec="seconds"),
        "scenario": "final vegetation-balanced + documented finite KAZA/Kruger fences",
        "domain": "valid model cells outside input cores carrying positive modelled current",
        "why": (
            "The top 10/5/1 percent of positive current lies entirely inside input "
            "cores in all four years, so source-inclusive statistics describe the "
            "fixed core footprint rather than connecting landscape."
        ),
        "core_cells": int(in_core.sum()),
        "valid_model_cells": int(valids[2024].sum()),
        "core_share_of_valid_percent": round(100 * in_core.sum() / valids[2024].sum(), 4),
        "masking_limit": (
            "Post-hoc domain masking. set_focal_node_currents_to_zero is documented as "
            "not implemented in Circuitscape 5 (installed 5.17.1), so focal-region "
            "influence remains in the underlying solve."
        ),
        "null_limit": (
            "The block null preserves clumping at the stated block scale and stays "
            "inside the domain, but it is not habitat-matched and is not a causal "
            "test. A toroidal-shift null was tried first and abandoned: the domain "
            "is irregular and covers only 41 percent of the grid, so shifts pushed "
            "most of the selection off-domain (median retention 46 percent of the "
            "observed cell count) and the resulting interval spanned almost the "
            "whole range. The descriptive comparison against the matched background "
            "is the primary result; the null is context."
        ),
        "per_year": headline,
        "temporal_overlap": overlap_rows,
    }, indent=2), encoding="utf-8")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        figure, axis = plt.subplots(figsize=(7.2, 4.6))
        for year in YEARS:
            rows = [r for r in curve_rows if r["year"] == year]
            axis.plot([r["percentile"] for r in rows],
                      [r["protected_percent"] for r in rows],
                      marker="o", markersize=3.5, linewidth=1.6, label=str(year))
        axis.axhline(headline[2024]["background_percent_matched"], color="0.35",
                     linestyle="--", linewidth=1.2,
                     label=f"background {headline[2024]['background_percent_matched']:.1f}%")
        crossover = headline[2024]["crossover_percentile"]
        if crossover:
            axis.axvline(crossover, color="0.6", linestyle=":", linewidth=1.1)
            axis.annotate(f"crossover ~{crossover:.1f}th", xy=(crossover, axis.get_ylim()[0]),
                          xytext=(4, 8), textcoords="offset points", fontsize=8, color="0.35")
        axis.set_xlabel("Percentile of modelled current, outside input cores")
        axis.set_ylabel("Protected-area coverage (%)")
        axis.set_title("Protected-area coverage of modelled connecting landscape")
        axis.legend(frameon=False, fontsize=8)
        axis.grid(alpha=0.25, linewidth=0.6)
        figure.tight_layout()
        figure_path = REPORTS / f"outside_core_pa_coverage_curve_{stamp}.png"
        figure.savefig(figure_path, dpi=200)
        plt.close(figure)
        print(f"figure : {figure_path}")
    except Exception as error:  # noqa: BLE001 - figure is optional
        print(f"figure skipped: {error}")

    print(f"curve  : {curve_path}")
    print(f"overlap: {overlap_path}")
    print(f"summary: {summary_path}")
    for year in YEARS:
        entry = headline[year]
        band = entry["bands"][90]
        print(f"  {year}: background {entry['background_percent_matched']:.2f}%  "
              f"top decile {band['protected_percent']:.2f}%  "
              f"({band['difference_percentage_points']:+.2f} pp)  "
              f"crossover ~{entry['crossover_percentile']:.1f}th")


if __name__ == "__main__":
    main()
