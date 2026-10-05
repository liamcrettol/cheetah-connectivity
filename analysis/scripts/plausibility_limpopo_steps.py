"""Step-based follow-up to the Limpopo plausibility check.

The first check (plausibility_limpopo_tracks.py) compares cheetah fixes with
points scattered over the whole convex hull, and its Mann-Whitney p-values treat
1,006 daily fixes as independent. This script addresses both weaknesses:

  1. Animal is the unit. Each animal gets its own score, and confidence
     intervals come from resampling animals, not fixes.
  2. Matched availability. For every day-to-day move, the place the cheetah
     actually went is compared with places it could have gone instead: same
     starting point, step lengths drawn from that animal's own moves, random
     direction. This asks "given where it was, did it pick the easier ground?"
     instead of "is the whole home area easier than the hull?"

Scores are the share of matched alternatives the real move beats (lower
resistance, higher current). 0.50 means no difference. Nothing is fitted to
the tracks: the surfaces are read as they are. Plausibility, not validation.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
from pyproj import Transformer

from plausibility_limpopo_tracks import ALBERS, SURFACES, download, sample, thin

SEED = 20261006
N_ALT = 20             # alternative endpoints per real step
MIN_STEP_M = 1_000     # shorter moves stay in the same 1 km cell
MAX_GAP_DAYS = 1       # only consecutive-day moves
N_BOOT = 10_000
LINE_SPACING_M = 250   # sampling interval along a straight-line move

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"


def line_mean(path: Path, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Mean raster value along straight segments a[i] -> b[i]."""
    d = np.hypot(*(b - a).T)
    n = np.maximum(2, np.ceil(d / LINE_SPACING_M).astype(int) + 1)
    seg_id = np.repeat(np.arange(len(a)), n)
    t = np.concatenate([np.linspace(0, 1, k) for k in n])
    pts = a[seg_id] + (b - a)[seg_id] * t[:, None]
    vals = sample(path, pts)
    sums = np.bincount(seg_id, weights=np.nan_to_num(vals), minlength=len(a))
    cnt = np.bincount(seg_id, weights=np.isfinite(vals), minlength=len(a))
    out = np.full(len(a), np.nan)
    ok = cnt > 0
    out[ok] = sums[ok] / cnt[ok]
    return out


def beat_share(obs: np.ndarray, alt: np.ndarray, expect_lower: bool) -> np.ndarray:
    """Per step: share of alternatives the real move beats, ties count half."""
    o = obs[:, None]
    better = (alt > o) if expect_lower else (alt < o)
    tie = alt == o
    valid = np.isfinite(alt)
    score = (better & valid).sum(1) + 0.5 * (tie & valid).sum(1)
    n = valid.sum(1)
    out = np.full(len(obs), np.nan)
    ok = (n > 0) & np.isfinite(obs)
    out[ok] = score[ok] / n[ok]
    return out


def boot_ci(per_animal: np.ndarray, rng) -> tuple[float, float]:
    idx = rng.integers(0, len(per_animal), (N_BOOT, len(per_animal)))
    means = per_animal[idx].mean(1)
    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def build_steps(rng):
    """Real day-to-day moves and their matched alternatives (shared by the follow-up checks)."""
    pts = thin(download())
    to_albers = Transformer.from_crs("EPSG:4326", ALBERS, always_xy=True)
    xy = np.array([to_albers.transform(float(r["lon"]), float(r["lat"])) for r in pts])

    by = defaultdict(list)
    for i, r in enumerate(pts):
        by[r["organismName"]].append(i)

    starts, ends, animal, lengths = [], [], [], defaultdict(list)
    short = gap = 0
    for nm, idx in by.items():
        for i, j in zip(idx[:-1], idx[1:]):
            if (pts[j]["_t"].date() - pts[i]["_t"].date()).days > MAX_GAP_DAYS:
                gap += 1
                continue
            d = float(np.hypot(*(xy[j] - xy[i])))
            if d < MIN_STEP_M:
                short += 1
                continue
            starts.append(i); ends.append(j); animal.append(nm); lengths[nm].append(d)
    starts, ends, animal = np.array(starts), np.array(ends), np.array(animal)

    # Alternatives: same start, step length from the same animal's own moves, random bearing.
    alt_len = np.array([rng.choice(lengths[a], N_ALT) for a in animal])
    ang = rng.uniform(0, 2 * np.pi, (len(starts), N_ALT))
    a0 = xy[starts]
    alt_xy = a0[:, None, :] + np.stack([alt_len * np.cos(ang), alt_len * np.sin(ang)], -1)
    flat_alt = alt_xy.reshape(-1, 2)
    flat_start = np.repeat(a0, N_ALT, axis=0)
    return {"xy": xy, "starts": starts, "ends": ends, "animal": animal, "lengths": lengths,
            "a0": a0, "flat_alt": flat_alt, "flat_start": flat_start, "short": short, "gap": gap}


def animal_summary(s: np.ndarray, animal: np.ndarray, rng) -> dict:
    animals = sorted(set(animal))
    pa = np.array([np.nanmean(s[animal == a]) for a in animals])
    lo, hi = boot_ci(pa, rng)
    return {"steps": int(np.isfinite(s).sum()), "animals": len(animals),
            "mean_share_beaten_animal_weighted": round(float(pa.mean()), 3),
            "ci95_low": round(lo, 3), "ci95_high": round(hi, 3),
            "animals_above_0_5": int((pa > 0.5).sum()),
            "mean_share_beaten_step_weighted": round(float(np.nanmean(s)), 3)}, pa


def main() -> None:
    rng = np.random.default_rng(SEED)
    st = build_steps(rng)
    xy, starts, ends, animal, lengths = st["xy"], st["starts"], st["ends"], st["animal"], st["lengths"]
    a0, flat_alt, flat_start, short, gap = st["a0"], st["flat_alt"], st["flat_start"], st["short"], st["gap"]

    animals = sorted(lengths)
    rows, per_animal_rows = [], []
    for surf, paths in SURFACES.items():
        for measure, key, lower in (("resistance", "resistance", True), ("current", "current", False)):
            p = paths[key]
            for kind in ("endpoint", "straight-line path"):
                if kind == "endpoint":
                    obs = sample(p, xy[ends])
                    alt = sample(p, flat_alt).reshape(len(starts), N_ALT)
                else:
                    obs = line_mean(p, a0, xy[ends])
                    alt = line_mean(p, flat_start, flat_alt).reshape(len(starts), N_ALT)
                s = beat_share(obs, alt, lower)
                summ, pa = animal_summary(s, animal, rng)
                rows.append({"surface": surf, "measure": measure, "comparison": kind, **summ})
                for a, v in zip(animals, pa):
                    per_animal_rows.append({"surface": surf, "measure": measure, "comparison": kind,
                                            "animal": a, "steps": int((animal == a).sum()),
                                            "mean_share_beaten": round(float(v), 3)})

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    for name, data in (("plausibility_limpopo_steps_summary", rows),
                       ("plausibility_limpopo_steps_by_individual", per_animal_rows)):
        with (REPORTS / f"{name}_{stamp}.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(data[0]))
            w.writeheader()
            w.writerows(data)
    meta = {
        "steps_used": len(starts), "steps_dropped_gap_over_1_day": gap,
        "steps_dropped_under_1km": short, "alternatives_per_step": N_ALT,
        "median_step_km": round(float(np.median(np.concatenate([lengths[a] for a in animals]))) / 1000, 2),
        "steps_per_animal": {a: len(lengths[a]) for a in animals},
        "bootstrap": f"{N_BOOT} resamples of animals, equal weight per animal",
        "seed": SEED, "surface_year_compared": 2012,
    }
    (REPORTS / f"plausibility_limpopo_steps_meta_{stamp}.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))
    for r in rows:
        print(f"{r['surface'][:24]:24} {r['measure']:10} {r['comparison']:19} "
              f"share={r['mean_share_beaten_animal_weighted']:.3f} "
              f"[{r['ci95_low']:.3f}, {r['ci95_high']:.3f}] "
              f"animals>0.5={r['animals_above_0_5']}/{r['animals']} steps={r['steps']}")


if __name__ == "__main__":
    main()
