"""Independent plausibility check against the Limpopo (Thabazimbi) cheetah tracks.

Implements protocol steps 23.1-23.5:
  23.1 load the EWT tracking data (GBIF DOI 10.15468/0nsr0r, CC-BY 4.0)
  23.2 thin to one location per individual per 24 hours (calendar day)
  23.3 draw availability points from the same landscape as the tracks,
       about ten times the thinned count
  23.4 extract modeled resistance and current at both point sets
  23.5 compare the two distributions

The tracks are 2003-2008, so they are compared with the 2012 surfaces, the
earliest snapshot. Current inside the fixed cores is forced high by the model
(cores are sources and grounds), so current is also reported outside cores.
This is a plausibility check, not a validation: no surface was fitted to these
data, and nine animals in one landscape cannot speak for the whole network.
"""

from __future__ import annotations

import csv
import json
import time
import urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer
from scipy.stats import mannwhitneyu
from shapely.geometry import MultiPoint, Point
from shapely.prepared import prep

DATASET_KEY = "77b04b75-97f5-4d3c-9184-8cc5c12d71ae"
SEED = 20261005
AVAIL_MULTIPLIER = 10
BUFFER_SENSITIVITY_M = 20_000

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
CACHE = REPORTS / "limpopo_ewt_tracks_gbif_raw.csv"
CS = Path(r"C:\cheetah\circuitscape")
SURFACES = {
    "final_balanced_fence_documented": {
        "resistance": CS / "inputs/final_balanced_fence_documented/resistance_final_balanced_fence_documented_2012.asc",
        "current": CS / "outputs/final_balanced_fence_documented/current_final_balanced_fence_documented_2012_cum_curmap.tif",
    },
    "primary_unfenced": {
        "resistance": CS / "inputs/resistance_primary_unfenced_2012.asc",
        "current": CS / "outputs/current_primary_unfenced_2012_cum_curmap.tif",
    },
}
CORES = CS / "inputs/final_balanced_fence_documented/cheetah_cores_fixed_23.asc"
ALBERS = ("+proj=aea +lat_1=20 +lat_2=-23 +lat_0=0 +lon_0=25 "
          "+x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs")


def download() -> list[dict]:
    if CACHE.exists():
        with CACHE.open(encoding="utf-8") as f:
            return list(csv.DictReader(f))
    rows, offset = [], 0
    while True:
        url = (f"https://api.gbif.org/v1/occurrence/search?datasetKey={DATASET_KEY}"
               f"&limit=300&offset={offset}")
        with urllib.request.urlopen(url) as r:
            page = json.load(r)
        for o in page["results"]:
            rows.append({
                "gbifID": o["gbifID"], "organismID": o.get("organismID", ""),
                "organismName": o.get("organismName", ""), "sex": o.get("sex", ""),
                "eventDate": o.get("eventDate", ""), "eventTime": o.get("eventTime", ""),
                "lat": o["decimalLatitude"], "lon": o["decimalLongitude"],
            })
        offset += 300
        if page["endOfRecords"]:
            break
        time.sleep(0.2)
    with CACHE.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return rows


def parse_time(row: dict) -> datetime:
    day = row["eventDate"][:10]
    t = row["eventTime"].strip()
    for fmt in ("%I:%M:%S %p", "%H:%M:%S"):
        try:
            return datetime.strptime(f"{day} {t}", f"%Y-%m-%d {fmt}")
        except ValueError:
            pass
    return datetime.strptime(day, "%Y-%m-%d")


def thin(rows: list[dict]) -> list[dict]:
    """Keep the earliest fix per individual per calendar day."""
    best: dict[tuple, dict] = {}
    for r in rows:
        # 17 records carry only a year or year-month; they cannot be placed on a day.
        if not r["organismID"] or len(r["eventDate"][:10]) < 10:
            continue
        r["_t"] = parse_time(r)
        key = (r["organismName"], r["_t"].date())  # organismID has a -9999 placeholder for one CBU collar
        if key not in best or r["_t"] < best[key]["_t"]:
            best[key] = r
    return sorted(best.values(), key=lambda r: (r["organismName"], r["_t"]))


def sample(path: Path, xy: np.ndarray) -> np.ndarray:
    with rasterio.open(path) as src:
        vals = np.array([v[0] for v in src.sample(xy)], dtype="float64")
        if src.nodata is not None:
            vals[vals == src.nodata] = np.nan
    vals[~np.isfinite(vals)] = np.nan
    return vals


def availability(points: np.ndarray, n: int, buffer_m: float, rng, ref: Path):
    hull = MultiPoint([tuple(p) for p in points]).convex_hull
    if buffer_m:
        hull = hull.buffer(buffer_m)
    ph = prep(hull)
    minx, miny, maxx, maxy = hull.bounds
    out: list = []
    while len(out) < n:
        cand = np.column_stack([rng.uniform(minx, maxx, n * 3), rng.uniform(miny, maxy, n * 3)])
        keep = [c for c in cand if ph.contains(Point(c))]
        if keep:
            keep = np.array(keep)
            ok = np.isfinite(sample(ref, keep))  # drop cells outside the modeled surface
            out.extend(keep[ok].tolist())
    return np.array(out[:n]), hull.area / 1e6


def compare(obs: np.ndarray, av: np.ndarray, expect_lower: bool) -> dict:
    obs, av = obs[np.isfinite(obs)], av[np.isfinite(av)]
    alt = "less" if expect_lower else "greater"
    u, p = mannwhitneyu(obs, av, alternative=alt)
    auc = u / (len(obs) * len(av))  # P(observed > available), ties count half
    p_dir = 1 - auc if expect_lower else auc  # P(observed is in the expected direction)
    return {"n_observed": len(obs), "n_available": len(av),
            "median_observed": float(np.median(obs)), "median_available": float(np.median(av)),
            "prob_observed_in_expected_direction": float(p_dir),
            "mann_whitney_p_one_sided": float(p)}


def in_core(xy: np.ndarray) -> np.ndarray:
    v = sample(CORES, xy)
    return np.isfinite(v) & (v > 0)


def main() -> None:
    rng = np.random.default_rng(SEED)
    raw = download()
    pts = thin(raw)
    to_albers = Transformer.from_crs("EPSG:4326", ALBERS, always_xy=True)
    obs_xy = np.array([to_albers.transform(float(r["lon"]), float(r["lat"])) for r in pts])
    in_core_obs = in_core(obs_xy)

    results, per_ind = [], []
    for buffer_m in (0, BUFFER_SENSITIVITY_M):
        for name, paths in SURFACES.items():
            av_xy, area_km2 = availability(obs_xy, AVAIL_MULTIPLIER * len(obs_xy), buffer_m,
                                           rng, paths["resistance"])
            in_core_av = in_core(av_xy)
            ro, ra = sample(paths["resistance"], obs_xy), sample(paths["resistance"], av_xy)
            co, ca = sample(paths["current"], obs_xy), sample(paths["current"], av_xy)
            base = {"surface": name, "availability_buffer_km": buffer_m // 1000,
                    "availability_area_km2": round(area_km2, 1)}
            results.append({**base, "measure": "resistance (all points)", **compare(ro, ra, True)})
            results.append({**base, "measure": "current (all points)", **compare(co, ca, False)})
            results.append({**base, "measure": "current (outside cores)",
                            **compare(co[~in_core_obs], ca[~in_core_av], False)})
            if buffer_m == 0 and name == "final_balanced_fence_documented":
                av_med_r, av_med_c = np.nanmedian(ra), np.nanmedian(ca[~in_core_av])
                by = defaultdict(list)
                for i, r in enumerate(pts):
                    by[(r["organismName"], r["sex"])].append(i)
                for (nm, sx), idx in sorted(by.items()):
                    idx = np.array(idx)
                    out_idx = idx[~in_core_obs[idx]]
                    has_out = len(out_idx) > 0
                    per_ind.append({
                        "name": nm, "sex": sx, "thinned_fixes": len(idx),
                        "first": pts[idx[0]]["_t"].date().isoformat(),
                        "last": pts[idx[-1]]["_t"].date().isoformat(),
                        "share_fixes_in_cores": round(float(in_core_obs[idx].mean()), 3),
                        "median_resistance": round(float(np.nanmedian(ro[idx])), 3),
                        "below_available_median_resistance": bool(np.nanmedian(ro[idx]) < av_med_r),
                        "median_current_outside_cores": (round(float(np.nanmedian(co[out_idx])), 6)
                                                         if has_out else ""),
                        "above_available_median_current": (bool(np.nanmedian(co[out_idx]) > av_med_c)
                                                           if has_out else ""),
                    })

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    def write(name: str, rows: list[dict]) -> Path:
        path = REPORTS / f"{name}_{stamp}.csv"
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        return path

    p1 = write("plausibility_limpopo_summary", results)
    p2 = write("plausibility_limpopo_by_individual", per_ind)
    meta = {
        "source": "EWT Carnivore Conservation Programme Cheetah Tracking Data, GBIF DOI 10.15468/0nsr0r, CC-BY 4.0",
        "raw_records": len(raw),
        "dropped_incomplete_dates": sum(1 for r in raw if len(r["eventDate"][:10]) < 10),
        "thinned_fixes": len(pts),
        "individuals": len({r["organismName"] for r in pts}),
        "date_range": [min(r["_t"] for r in pts).date().isoformat(),
                       max(r["_t"] for r in pts).date().isoformat()],
        "share_thinned_fixes_in_cores": round(float(in_core_obs.mean()), 3),
        "surface_year_compared": 2012,
        "thinning_rule": "earliest fix per individual per calendar day",
        "availability_rule": (f"{AVAIL_MULTIPLIER}x thinned count, uniform inside the convex hull of all "
                              f"thinned fixes (0 km primary, {BUFFER_SENSITIVITY_M // 1000} km buffer "
                              "sensitivity), points with no modeled resistance dropped"),
        "seed": SEED, "summary_csv": str(p1), "by_individual_csv": str(p2),
    }
    (REPORTS / f"plausibility_limpopo_meta_{stamp}.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))
    for r in results:
        print(f"{r['surface'][:24]:24} buf{r['availability_buffer_km']:>3} {r['measure']:26} "
              f"obs={r['median_observed']:.5g} avail={r['median_available']:.5g} "
              f"P(dir)={r['prob_observed_in_expected_direction']:.3f} "
              f"p={r['mann_whitney_p_one_sided']:.3g} n={r['n_observed']}/{r['n_available']}")


if __name__ == "__main__":
    main()
