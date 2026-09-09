"""Run the 45 reference paths on the revised combined anthropogenic model."""

from pathlib import Path
import os
import sys

OUTPUTS = r"C:\Users\lcrettol\Documents\Codex\2026-08-25\i-am-working-on-this-spreadsheet\outputs"
if OUTPUTS not in sys.path:
    sys.path.insert(0, OUTPUTS)

import create_reference_least_cost_paths as workflow

workflow.RESISTANCE = os.path.join(workflow.GDB, "resistance_primary_unfenced_combined")
workflow.OUTPUT = os.path.join(workflow.GDB, "least_cost_paths_primary_combined_unfenced")
workflow.REPORT = Path(r"C:\cheetah\reports\least_cost_paths_primary_combined_unfenced.csv")

if __name__ == "__main__":
    workflow.main()
