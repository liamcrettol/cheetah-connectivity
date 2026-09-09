"""Read-only QC for final four-year pairwise Circuitscape outputs."""

import datetime as task_datetime
from pathlib import Path
import json
import math
import re

import arcpy
import numpy as np


OUT = Path(r"C:\cheetah\circuitscape\outputs\final_balanced_fence_documented")
REPORTS = Path(r"C:\cheetah\reports")
YEARS = (2012, 2016, 2020, 2024)
EXPECTED_PAIRS = 253


def grid(path):
    r = arcpy.Raster(str(path))
    e = r.extent
    return {"columns": int(r.width), "rows": int(r.height),
            "cell_width": float(r.meanCellWidth), "cell_height": float(r.meanCellHeight),
            "xmin": float(e.XMin), "ymin": float(e.YMin),
            "xmax": float(e.XMax), "ymax": float(e.YMax),
            "wkid": int(r.spatialReference.factoryCode or 0)}


def same_grid(left, right):
    if left["columns"] != right["columns"] or left["rows"] != right["rows"] or left["wkid"] != right["wkid"]:
        return False
    return all(math.isclose(left[key], right[key], rel_tol=0, abs_tol=0.001)
               for key in ("cell_width", "cell_height", "xmin", "ymin", "xmax", "ymax"))


def raster_summary(path):
    """Read values directly so QC does not create/overwrite raster statistics."""
    values = arcpy.RasterToNumPyArray(str(path), nodata_to_value=np.nan).astype(np.float64, copy=False)
    valid = np.isfinite(values)
    if not valid.any():
        raise RuntimeError(f"No finite current values: {path}")
    return float(np.nanmin(values)), float(np.nanmax(values)), float(np.nanmean(values))


def main():
    complete = OUT / "FINAL_PAIRWISE_CURRENT_FLOW_COMPLETE.txt"
    if not complete.exists():
        raise FileNotFoundError(f"Missing completion receipt: {complete}")
    receipt = complete.read_text(encoding="utf-8")
    required = ("fixed_core_count=23", f"pairs_per_year={EXPECTED_PAIRS}", "solver=cg+amg")
    if any(item not in receipt for item in required):
        raise RuntimeError(f"Completion receipt lacks expected configuration:\n{receipt}")

    records, failures = [], []
    reference = None
    for year in YEARS:
        base = f"current_final_balanced_fence_documented_{year}"
        tif = OUT / f"{base}_cum_curmap.tif"
        log = OUT / f"{base}.log"
        matrix = OUT / f"{base}_resistances.out"
        for path in (tif, log, matrix):
            if not path.exists() or path.stat().st_size == 0:
                failures.append(f"{year}: missing/empty {path.name}")
        if failures:
            continue
        text = log.read_text(encoding="utf-8", errors="replace")
        solved = bool(re.search(r"Solving pair\s+253\s+of\s+253", text))
        errors = [line for line in text.splitlines() if re.search(r"\b(ERROR|FATAL|Exception)\b", line, re.I)]
        rows = matrix.read_text(encoding="utf-8", errors="replace").splitlines()
        matrix_rows = len([line for line in rows if line.strip()])
        g = grid(tif)
        if reference is None:
            reference = g
        elif not same_grid(reference, g):
            failures.append(f"{year}: current raster grid differs from 2012")
        minimum, maximum, mean = raster_summary(tif)
        if not maximum > 0 or not mean > 0:
            failures.append(f"{year}: non-positive current summary")
        if not solved:
            failures.append(f"{year}: log does not show pair 253/253")
        if errors:
            failures.append(f"{year}: error-like log records: {errors[:3]}")
        if matrix_rows != 24:
            failures.append(f"{year}: expected 24 populated resistance-matrix rows; found {matrix_rows}")
        records.append({"year": year, "current_raster": str(tif), "log": str(log),
                        "matrix": str(matrix), "pair_253_logged": solved,
                        "error_like_log_records": len(errors), "matrix_rows": matrix_rows,
                        "minimum": minimum, "maximum": maximum, "mean": mean,
                        "grid": g})

    report = {"created": task_datetime.datetime.now().isoformat(timespec="seconds"),
              "scenario": "final vegetation-balanced + documented finite KAZA/Kruger fences",
              "completion_receipt": receipt, "expected_pairs_per_year": EXPECTED_PAIRS,
              "records": records, "failures": failures,
              "scope": "Execution and structural output QC only; not biological validation, current normalization, priority ranking, or map interpretation."}
    REPORTS.mkdir(parents=True, exist_ok=True)
    stamp = task_datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = REPORTS / f"final_pairwise_current_flow_qc_{stamp}.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"years checked: {len(records)}; failures: {len(failures)}")
    for record in records:
        print(f"{record['year']}: 253/253 logged; current mean={record['mean']:.8g}; max={record['maximum']:.8g}")
    for failure in failures:
        print("REVIEW: " + failure)
    print(f"report: {out}")
    print("No outputs, rasters, ArcGIS map layers, or solver inputs were changed.")
    return report


if __name__ == "__main__":
    main()
