import sys, os, csv
sys.path.insert(0, r"C:\Users\lcrettol\Documents\Codex\2026-08-25\i-am-working-on-this-spreadsheet\outputs")
from resistance_model_utils import *
from arcpy.sa import Con, Raster

SOURCES = [os.path.join(GDB, f"livestock_{x}_2020_1km") for x in ("cattle","goats","sheep")]
OUTPUT = os.path.join(GDB, "pressure_livestock_index_1_10")

def main():
    setup_env(); require(*SOURCES)
    aprx, m, parent = project_and_map(); backup(aprx, "livestock_index")
    thresholds = [positive_percentile(x) for x in SOURCES]
    normalized=[]
    for source, threshold in zip(SOURCES, thresholds):
        r=Raster(source); normalized.append(Con(r <= 0, 0, Con(r >= threshold, 1, r/threshold)))
    index=(normalized[0]+normalized[1]+normalized[2])/3.0
    replace(m, OUTPUT); (1+9*index).save(OUTPUT); arcpy.management.CalculateStatistics(OUTPUT,1,1,[],"OVERWRITE")
    add_grouped(m, group(m,parent,COMPONENT_GROUP),OUTPUT,True)
    REPORTS.mkdir(parents=True,exist_ok=True)
    with (REPORTS/"livestock_index_transformation.csv").open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f); w.writerow(["species","source","positive_p95","combination"])
        for species,source,t in zip(("cattle","goats","sheep"),SOURCES,thresholds): w.writerow([species,source,t,"equal mean after separate 0-1 standardization"])
    aprx.save(); print("positive-cell 95th percentiles:"); [print(f"  {s}: {t}") for s,t in zip(("cattle","goats","sheep"),thresholds)]; print("created: pressure_livestock_index_1_10"); print("Inspect before continuing; species sources were unchanged.")
if __name__ == "__main__": main()

