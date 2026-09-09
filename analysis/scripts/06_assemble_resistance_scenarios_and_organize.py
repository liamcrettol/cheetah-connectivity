"""Assemble the documented first resistance model and organize Contents.

Run only after inspecting scripts 01-05. Creates an unfenced base plus main
and near-barrier fence scenarios. Source and component rasters are preserved.
"""

import sys, os, csv
sys.path.insert(0, r"C:\Users\lcrettol\Documents\Codex\2026-08-25\i-am-working-on-this-spreadsheet\outputs")
from resistance_model_utils import *
from arcpy.sa import Raster

HUMAN=os.path.join(GDB,"pressure_human_index_1_10")
LIVESTOCK=os.path.join(GDB,"pressure_livestock_index_1_10")
TERRAIN=os.path.join(GDB,"terrain_resistance_1_10")
FENCE_NONE=os.path.join(GDB,"fence_multiplier_none_1km")
FENCE_MAIN=os.path.join(GDB,"fence_multiplier_main_1km")
FENCE_BARRIER=os.path.join(GDB,"fence_multiplier_nearbarrier_1km")
BASE=os.path.join(GDB,"resistance_base_unfenced_1_10")
MAIN=os.path.join(GDB,"resistance_scenario_fence_main")
BARRIER=os.path.join(GDB,"resistance_scenario_fence_nearbarrier")
WEIGHTS={"human_pressure":0.50,"livestock_exposure":0.30,"terrain":0.20}

def main():
    setup_env(); require(HUMAN,LIVESTOCK,TERRAIN,FENCE_NONE,FENCE_MAIN,FENCE_BARRIER)
    aprx,m,parent=project_and_map(); backup(aprx,"resistance_scenario_assembly")
    for output in (BASE,MAIN,BARRIER): replace(m,output)
    base=(WEIGHTS["human_pressure"]*Raster(HUMAN)+WEIGHTS["livestock_exposure"]*Raster(LIVESTOCK)+WEIGHTS["terrain"]*Raster(TERRAIN))
    base.save(BASE)
    (Raster(BASE)*Raster(FENCE_MAIN)).save(MAIN)
    (Raster(BASE)*Raster(FENCE_BARRIER)).save(BARRIER)
    for output in (BASE,MAIN,BARRIER): arcpy.management.CalculateStatistics(output,1,1,[],"OVERWRITE")
    target=group(m,parent,FINAL_GROUP)
    add_grouped(m,target,BASE,True); add_grouped(m,target,MAIN,False); add_grouped(m,target,BARRIER,False)
    REPORTS.mkdir(parents=True,exist_ok=True)
    with (REPORTS/"first_resistance_model_decision.csv").open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f); w.writerow(["role","input_or_output","weight_or_operation","status"])
        w.writerow(["component",HUMAN,WEIGHTS["human_pressure"],"initial hypothesis; sensitivity required"])
        w.writerow(["component",LIVESTOCK,WEIGHTS["livestock_exposure"],"initial hypothesis; sensitivity required"])
        w.writerow(["component",TERRAIN,WEIGHTS["terrain"],"initial hypothesis; sensitivity required"])
        w.writerow(["context","VCF and categorical land cover","not added","retained for interpretation and validation"])
        w.writerow(["scenario",BASE,"unfenced weighted base","created"])
        w.writerow(["scenario",MAIN,"base multiplied by main fence surface","created"])
        w.writerow(["scenario",BARRIER,"base multiplied by near-barrier fence surface","created"])
    aprx.save()
    print("created: resistance_base_unfenced_1_10")
    print("created: resistance_scenario_fence_main")
    print("created: resistance_scenario_fence_nearbarrier")
    print("organizing the complete Contents pane...")
    from tidy_cheetah_contents import main as tidy_contents
    tidy_contents()
    print("Complete. First resistance scenarios were assembled and Contents was organized. No source raster was changed.")

if __name__ == "__main__": main()

