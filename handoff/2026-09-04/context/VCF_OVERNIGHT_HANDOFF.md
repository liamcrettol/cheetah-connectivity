# Overnight corrected-VCF diagnostic

## Purpose and scope

Run the corrected common-support VCF through the balanced model for 2012,
2016, 2020 and 2024, with the existing 45 pairs and fixed 23 cores. This is
180 comparisons and at most 84 source cost-distance solves, not 180 solves.
Reuse each source surface for all its destinations. Use the maximum saved
feasible-route candidate cost for that source plus 5% as an accumulated-cost
bound. This is not a geographic crop: positive costs imply an optimal prefix
cannot cost more than the complete feasible route. Validate extracted costs
against both line integrals and the saved feasible route.

This repeats the controlled pilot method. Missing candidate VCF retains old
resistance only to isolate the input change while preserving model support.
This is NOT a final missing-land/water decision. The 4,866 missing cells,
including ambiguous water classifications, must still receive a defensible
final treatment before production adoption. A route avoiding fallback cells
does not prove those cells cannot influence the optimum.

No low/high runs, fence scenarios, Circuitscape, rankings, production layers,
spreadsheet edits, commits or paper edits occur. Existing results remain intact.
The old one-pair pilot is used for testing, not imported as a batch checkpoint.

## Start from the ArcGIS Pro Python window

```python
import runpy; _job = runpy.run_path(r"C:\Users\lcrettol\Documents\Codex\2026-08-25\i-am-working-on-this-spreadsheet\outputs\start_vcf_v2_balanced_overnight.py", run_name="__main__")
```

The launcher starts a hidden standalone ArcGIS Python process and immediately
returns. Check progress after approximately one minute with:

```python
import runpy; _job = runpy.run_path(r"C:\Users\lcrettol\Documents\Codex\2026-08-25\i-am-working-on-this-spreadsheet\outputs\check_vcf_v2_overnight.py", run_name="__main__")
```

Leave the computer powered on and plugged in. The worker requests Windows to
avoid idle sleep while running; do not close a lid that triggers sleep, manually
sleep, reboot, sign out, or alter input data. ArcGIS Pro is not the parent
execution environment for the calculations; work runs in a separate process.
Spatial Analyst must be available to standalone ArcGIS Python. License or input
failure stops the job; no substitute algorithm or data are silently used.

## Outputs and restart

All outputs are under `C:\cheetah\diagnostics\vcf_v2_balanced_overnight_v1`:

- `STATUS.json`: current operation or COMPLETE/STOPPED.
- `console_*.log`: timestamped progress and errors. `latest_launch.json` identifies current log.
- `SUMMARY.md`: partial/final plain-language summary.
- `comparisons.csv`: costs, lengths, both-direction 1 km/5 km overlap,
  endpoint displacement and fallback exposure for each completed source group.
- `temporal_comparison.json`: old versus candidate 2012-2024 cost changes.
- Per-year/source diagnostic geodatabases: candidate rasters, routes and
  retained distance/backlink rasters for restart.

Rerun the SAME launcher to resume after an ordinary interruption. Completed
source groups are validated and skipped; completed distance/backlink surfaces
can be reused even if path extraction was interrupted. A partly calculated
distance surface without a completed receipt is recomputed in a new attempt
geodatabase. Partial attempts are retained, not deleted. A crashed worker's
lock is removed only after its PID is confirmed exited. An active/uncertain PID
blocks a duplicate launch. Input/script/version changes block stale reuse.

Require at least 20 GB free initially; stop before a new solve if free space
falls below 5 GB. Retained rasters consume disk space. No old outputs are
automatically deleted. Runtime is not guaranteed to fit one night.

If stopped: read the last log lines. After correcting a transient environment
issue, rerun the launcher. If an input or code fingerprint changed, do not erase
the manifest or force resume: preserve this diagnostic and use a new output
folder after review. Do not treat partial output as complete.

## Verification before handoff

- All four years/180 saved routes passed read-only input, endpoint, grid,
  feasible-route cost and common-support checks.
- New comparison code reproduced the completed 2016 core 17-24 pilot's
  optimized cost change (+1.040336%) and overlap values without a new solve.
- The actual path-extraction operation passed a smoke test using the existing
  pilot cost-distance/backlink rasters and the new copied-geometry destination
  approach. Output: `C:\cheetah\diagnostics\overnight_extraction_smoke_15ad4b5142`.
  No new CostDistance calculation was run for that test.
- Syntax and Windows process-presence tests passed. Approximately 589 GB
  free space was available at handoff; the worker checks again at runtime.
- The full overnight batch has NOT been launched by the assistant.

## Interpretation

Small cost changes can accompany large geographic shifts. Endpoint movement
within fixed cores is reported separately. Distances and 95% coverage are
descriptive review measures, not validated biological cutoffs. Temporal sign
differences are not significance tests. Final mask policy, vegetation-response
assumptions, other weights and current-flow sensitivity remain outside this job.
