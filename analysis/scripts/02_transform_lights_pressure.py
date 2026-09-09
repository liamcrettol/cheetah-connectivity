import sys, os, csv
sys.path.insert(0, r"C:\Users\lcrettol\Documents\Codex\2026-08-25\i-am-working-on-this-spreadsheet\outputs")
from resistance_model_utils import *

SOURCE = os.path.join(GDB, "lights_2024_1km_flaremasked")
OUTPUT = os.path.join(GDB, "pressure_lights_1_10")

def main():
    setup_env(); require(SOURCE)
    aprx, m, parent = project_and_map(); backup(aprx, "lights_pressure")
    threshold = positive_percentile(SOURCE); replace(m, OUTPUT); pressure_1_10(SOURCE, OUTPUT, threshold)
    add_grouped(m, group(m, parent, COMPONENT_GROUP), OUTPUT, True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    with (REPORTS / "lights_pressure_transformation.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w=csv.writer(f); w.writerow(["source","output","positive_p95","minimum_resistance","maximum_resistance","flare_masked"]); w.writerow([SOURCE,OUTPUT,threshold,1,10,"yes"])
    aprx.save(); print(f"positive-cell 95th percentile: {threshold}"); print("created: pressure_lights_1_10"); print("Inspect before continuing; source was unchanged.")
if __name__ == "__main__": main()

