import sys, os, csv
sys.path.insert(0, r"C:\Users\lcrettol\Documents\Codex\2026-08-25\i-am-working-on-this-spreadsheet\outputs")
from resistance_model_utils import *
from arcpy.sa import Raster

SOURCES=[os.path.join(GDB,x) for x in ("pressure_built_1_10","pressure_lights_1_10","pressure_roads_1_10")]
OUTPUT=os.path.join(GDB,"pressure_human_index_1_10")

def main():
    setup_env(); require(*SOURCES)
    aprx,m,parent=project_and_map(); backup(aprx,"human_pressure_index")
    replace(m,OUTPUT); ((Raster(SOURCES[0])+Raster(SOURCES[1])+Raster(SOURCES[2]))/3.0).save(OUTPUT); arcpy.management.CalculateStatistics(OUTPUT,1,1,[],"OVERWRITE")
    add_grouped(m,group(m,parent,COMPONENT_GROUP),OUTPUT,True)
    REPORTS.mkdir(parents=True,exist_ok=True)
    with (REPORTS/"human_pressure_index_decision.csv").open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f); w.writerow(["component","weight_within_human_index","reason"]); [w.writerow([x,1/3,"equal initial weight; sensitivity required"]) for x in ("built","lights","roads")]
    aprx.save(); print("created: pressure_human_index_1_10"); print("Built, lights, and roads each contribute one third. Inspect before final assembly.")
if __name__ == "__main__": main()

