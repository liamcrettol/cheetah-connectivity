"""Run the 45-link primary least-cost network for historical snapshots."""

from pathlib import Path
import importlib
import os
import sys

OUTPUTS = r"C:\Users\lcrettol\Documents\Codex\2026-08-25\i-am-working-on-this-spreadsheet\outputs"
if OUTPUTS not in sys.path:
    sys.path.insert(0, OUTPUTS)

import create_reference_least_cost_paths as workflow

GDB = workflow.GDB
YEARS = (2012, 2016, 2020)


def main():
    for year in YEARS:
        # ArcGIS Pro keeps imported modules alive between runs; reload ensures
        # each year uses the settings assigned below.
        importlib.reload(workflow)
        workflow.RESISTANCE = os.path.join(GDB, f"resistance_primary_unfenced_combined_{year}")
        workflow.OUTPUT = os.path.join(GDB, f"least_cost_paths_primary_combined_{year}")
        workflow.REPORT = Path(r"C:\cheetah\reports") / f"least_cost_paths_primary_combined_{year}.csv"
        workflow.SCENARIO_LABEL = f"primary_unfenced_{year}"
        workflow.PAIRS_OVERRIDE = None
        print(f"running primary historical paths for {year}")
        workflow.main()
    print("Complete. Historical primary path reports are ready for temporal threat calculation.")


if __name__ == "__main__":
    main()
