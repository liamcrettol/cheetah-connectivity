"""Three follow-ups to the step-based Limpopo plausibility check.

All three reuse the exact moves and matched alternatives from
plausibility_limpopo_steps.py (same seed), so the numbers line up.

  A. Layer breakdown. The main 2012 surface is rebuilt point by point from its
     parts (same scaling and weights as build_temporal_vegetation_sensitivity.py
     and build_final_balanced_fence_resistance.py) and checked against the
     stored raster. Then each part is scored on its own, and the main surface is
     rescored with each part left out. This shows which inputs carry the lean.
  B. All nine surfaces. The main surface plus the eight one-change alternatives
     (two other human-pressure weightings, two other vegetation weights, four
     other fence treatments), resistance only. A robustness statement, not a way
     to pick a surface.
  C. Road crossings. Each straight-line move is tested against GRIP4 road lines
     and compared with its alternatives. Mapped fences are absent from the
     tracking area, so fences cannot be tested with these data.

Nothing here changes any weight. Plausibility, not validation.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pyogrio
import rasterio
import shapely
from shapely.strtree import STRtree

from plausibility_limpopo_steps import (LINE_SPACING_M, N_ALT, SEED, animal_summary,
                                        beat_share, build_steps)
from plausibility_limpopo_tracks import sample

GDB = r"C:\cheetah\gdb\cheetah_working.gdb"
GEE = Path(r"C:\cheetah\github_repo\gis\cheetah_connectivity\cheetah\rasters\gee_exports")
YEARS = (2012, 2016, 2020, 2024)
ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"

ANTHRO_WEIGHTS = {
    "main": {"built": 0.30, "roads": 0.30, "livestock": 0.30, "lights": 0.10},
    "equal": {"built": 0.25, "roads": 0.25, "livestock": 0.25, "lights": 0.25},
    "infrastructure": {"built": 0.35, "roads": 0.35, "livestock": 0.20, "lights": 0.10},
}
TOP_WEIGHTS = {
    "veg20": {"anthropogenic": 0.60, "vegetation": 0.20, "terrain": 0.20},
    "veg10": {"anthropogenic": 0.70, "vegetation": 0.10, "terrain": 0.20},
    "veg40": {"anthropogenic": 0.40, "vegetation": 0.40, "terrain": 0.20},
}
FENCES = {
    "documented": "fence_multiplier_main_kruger_documented_1km",
    "none": "fence_multiplier_none_1km",
    "kaza_only": "fence_multiplier_main_1km",
    "near_barrier": "fence_multiplier_nearbarrier_1km",
    "kruger_conservative": "fence_multiplier_main_kruger_conservative_1km",
}
SURFACES = [  # (label, group, anthropogenic weights, top weights, fence)
    ("main", "main", "main", "veg20", "documented"),
    ("equal human-pressure weights", "human-pressure weighting", "equal", "veg20", "documented"),
    ("infrastructure emphasis", "human-pressure weighting", "infrastructure", "veg20", "documented"),
    ("vegetation 10 percent", "vegetation weight", "main", "veg10", "documented"),
    ("vegetation 40 percent", "vegetation weight", "main", "veg40", "documented"),
    ("no fences", "fence treatment", "main", "veg20", "none"),
    ("KAZA fences only", "fence treatment", "main", "veg20", "kaza_only"),
    ("near-barrier fences", "fence treatment", "main", "veg20", "near_barrier"),
    ("Kruger conservative", "fence treatment", "main", "veg20", "kruger_conservative"),
]


def gdb(name: str) -> str:
    return f"OpenFileGDB:{GDB}:{name}"


def full_range(src: str) -> tuple[float, float]:
    with rasterio.open(src) as s:
        a = s.read(1, masked=True).astype("float64")
    a = np.ma.masked_invalid(a)
    return float(a.min()), float(a.max())


def scale(v: np.ndarray, lo: float, hi: float) -> np.ndarray:
    return np.ones_like(v) if hi <= lo else (v - lo) / (hi - lo) * 9 + 1


def lights_src(year: int) -> str:
    try:
        with rasterio.open(gdb(f"lights_{year}_1km_flaremasked")):
            return gdb(f"lights_{year}_1km_flaremasked")
    except rasterio.errors.RasterioIOError:
        return str(GEE / f"lights_{year}_1km.tif")


def path_points(a: np.ndarray, b: np.ndarray):
    d = np.hypot(*(b - a).T)
    n = np.maximum(2, np.ceil(d / LINE_SPACING_M).astype(int) + 1)
    seg = np.repeat(np.arange(len(a)), n)
    t = np.concatenate([np.linspace(0, 1, k) for k in n])
    return a[seg] + (b - a)[seg] * t[:, None], seg


def seg_mean(vals: np.ndarray, seg: np.ndarray, n: int) -> np.ndarray:
    ok = np.isfinite(vals)
    s = np.bincount(seg, weights=np.where(ok, vals, 0), minlength=n)
    c = np.bincount(seg, weights=ok, minlength=n)
    out = np.full(n, np.nan)
    out[c > 0] = s[c > 0] / c[c > 0]
    return out


def main() -> None:
    st = build_steps(np.random.default_rng(SEED))
    rng = np.random.default_rng(SEED + 1)
    xy, ends, animal = st["xy"], st["ends"], st["animal"]
    a0, flat_alt, flat_start = st["a0"], st["flat_alt"], st["flat_start"]
    n_steps = len(ends)

    # Every location any score needs, sampled once per layer.
    obs_path, obs_seg = path_points(a0, xy[ends])
    alt_path, alt_seg = path_points(flat_start, flat_alt)
    groups = {"obs_end": xy[ends], "alt_end": flat_alt, "obs_path": obs_path, "alt_path": alt_path}
    order = list(groups)
    allpts = np.concatenate([groups[k] for k in order])
    cuts = np.cumsum([0] + [len(groups[k]) for k in order])

    def at(src: str) -> np.ndarray:
        return sample(src, allpts)

    built_lo = min(full_range(str(GEE / f"built_{y}_1km.tif"))[0] for y in YEARS)
    built_hi = max(full_range(str(GEE / f"built_{y}_1km.tif"))[1] for y in YEARS)
    lights_lo = min(full_range(lights_src(y))[0] for y in YEARS)
    lights_hi = max(full_range(lights_src(y))[1] for y in YEARS)
    roads_lo, roads_hi = full_range(gdb("pressure_roads_1_10"))
    live_lo, live_hi = full_range(gdb("pressure_livestock_index_1_10"))

    part = {
        "built": scale(at(str(GEE / "built_2012_1km.tif")), built_lo, built_hi),
        "roads": scale(at(gdb("pressure_roads_1_10")), roads_lo, roads_hi),
        "livestock": scale(at(gdb("pressure_livestock_index_1_10")), live_lo, live_hi),
        "lights": scale(at(lights_src(2012)), lights_lo, lights_hi),
        "vegetation": at(gdb("vegetation_resistance_2012_1_10")),
        "terrain": at(gdb("terrain_resistance_1_10")),
    }
    fence = {k: at(gdb(v)) for k, v in FENCES.items()}
    stored_main = at(gdb("resistance_final_balanced_fence_documented_2012"))

    def flat_weights(aw: str, tw: str) -> dict:
        t = TOP_WEIGHTS[tw]
        w = {k: t["anthropogenic"] * v for k, v in ANTHRO_WEIGHTS[aw].items()}
        w["vegetation"], w["terrain"] = t["vegetation"], t["terrain"]
        return w

    def combine(w: dict, fence_key: str) -> np.ndarray:
        return sum(part[k] * v for k, v in w.items()) * fence[fence_key]

    main_w = flat_weights("main", "veg20")
    rebuilt = combine(main_w, "documented")
    ok = np.isfinite(rebuilt) & np.isfinite(stored_main)
    diff = np.abs(rebuilt[ok] - stored_main[ok])
    rebuild_check = {"points_compared": int(ok.sum()), "points_off_by_more_than_0_01": int((diff > 0.01).sum()),
                     "max_abs_diff": float(diff.max())}

    def score(vals: np.ndarray, lower: bool = True) -> dict[str, np.ndarray]:
        g = {k: vals[cuts[i]:cuts[i + 1]] for i, k in enumerate(order)}
        out = {"endpoint": beat_share(g["obs_end"], g["alt_end"].reshape(n_steps, N_ALT), lower)}
        obs_line = seg_mean(g["obs_path"], obs_seg, n_steps)
        alt_line = seg_mean(g["alt_path"], alt_seg, n_steps * N_ALT).reshape(n_steps, N_ALT)
        out["straight-line path"] = beat_share(obs_line, alt_line, lower)
        return out

    rows_a, rows_b, rows_c = [], [], []

    # A. Each part alone, then the main surface with each part left out.
    for name in part:
        for kind, s in score(part[name]).items():
            summ, _ = animal_summary(s, animal, rng)
            rows_a.append({"test": "this layer alone", "layer": name,
                           "weight_in_main": round(main_w[name], 3), "comparison": kind, **summ})
    for name in part:
        w = {k: v for k, v in main_w.items() if k != name}
        total = sum(w.values())
        w = {k: v / total for k, v in w.items()}
        for kind, s in score(combine(w, "documented")).items():
            summ, _ = animal_summary(s, animal, rng)
            rows_a.append({"test": "main surface without this layer", "layer": name,
                           "weight_in_main": round(main_w[name], 3), "comparison": kind, **summ})

    # B. All nine surfaces.
    for label, group, aw, tw, fk in SURFACES:
        vals = combine(flat_weights(aw, tw), fk)
        for kind, s in score(vals).items():
            summ, _ = animal_summary(s, animal, rng)
            rows_b.append({"surface": label, "group": group, "comparison": kind, **summ})
    fence_in_area = {k: sorted({round(float(v), 3) for v in f[np.isfinite(f)]}) for k, f in fence.items()}

    # C. Road crossings along straight-line moves.
    bbox = tuple(np.concatenate([allpts.min(0) - 5000, allpts.max(0) + 5000]))
    obs_lines = shapely.linestrings(np.stack([a0, xy[ends]], 1))
    alt_lines = shapely.linestrings(np.stack([flat_start, flat_alt], 1))
    road_info = {}
    for layer in ("roads_grip4_major", "roads_grip4_minor", "roads_grip4"):
        crs = pyogrio.read_info(GDB, layer=layer)["crs"]
        geoms = pyogrio.raw.read(GDB, layer=layer, bbox=bbox, read_geometry=True, columns=[])[2]
        roads = shapely.from_wkb(geoms)
        tree = STRtree(roads)

        def crossings(lines):
            pairs = tree.query(lines, predicate="intersects")
            return np.bincount(pairs[0], minlength=len(lines)).astype(float)

        obs_c = crossings(obs_lines)
        alt_c = crossings(alt_lines).reshape(n_steps, N_ALT)
        s = beat_share(obs_c, alt_c, expect_lower=True)
        summ, _ = animal_summary(s, animal, rng)
        rows_c.append({"roads": layer, "road_segments_in_area": len(roads),
                       "share_real_moves_crossing": round(float((obs_c > 0).mean()), 3),
                       "share_alternative_moves_crossing": round(float((alt_c > 0).mean()), 3),
                       **summ})
        road_info[layer] = crs[:60] if crs else None

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    for name, data in (("plausibility_limpopo_layers", rows_a),
                       ("plausibility_limpopo_all_surfaces", rows_b),
                       ("plausibility_limpopo_road_crossings", rows_c)):
        with (REPORTS / f"{name}_{stamp}.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(data[0]))
            w.writeheader()
            w.writerows(data)
    meta = {
        "steps": n_steps, "alternatives_per_step": N_ALT, "seed": SEED,
        "rebuilt_main_vs_stored_surface": rebuild_check,
        "scaling_bounds": {"built": [built_lo, built_hi], "lights": [lights_lo, lights_hi],
                           "roads": [roads_lo, roads_hi], "livestock": [live_lo, live_hi]},
        "fence_multiplier_values_at_sampled_points": fence_in_area,
        "road_layer_crs": road_info,
        "note": "Scores are the share of matched alternatives the real move beats; 0.5 = no difference. "
                "Animal-weighted, 95% CI from 10,000 resamples of animals.",
    }
    (REPORTS / f"plausibility_limpopo_followups_meta_{stamp}.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))
    for r in rows_a + rows_b + rows_c:
        lab = r.get("layer") or r.get("surface") or r.get("roads")
        print(f"{r.get('test', r.get('group', 'roads'))[:32]:32} {lab[:28]:28} {r.get('comparison', ''):19} "
              f"{r['mean_share_beaten_animal_weighted']:.3f} [{r['ci95_low']:.3f}, {r['ci95_high']:.3f}] "
              f"{r['animals_above_0_5']}/{r['animals']}"
              + (f"  cross real={r['share_real_moves_crossing']} alt={r['share_alternative_moves_crossing']}"
                 if "share_real_moves_crossing" in r else ""))


if __name__ == "__main__":
    main()
