"""Report the discrete value distribution of the aligned cheetah density raster."""

from pathlib import Path
import csv
import arcpy
import numpy as np

SOURCE = r"C:\cheetah\gdb\cheetah_working.gdb\cheetah_density_aligned_1km"
REPORT = Path(r"C:\cheetah\reports\cheetah_density_value_distribution.csv")


def main():
    if not arcpy.Exists(SOURCE):
        raise FileNotFoundError(SOURCE)
    sentinel=-3.0e38
    array=arcpy.RasterToNumPyArray(SOURCE,nodata_to_value=sentinel).astype(np.float32,copy=False)
    values=array[(array>0)&(array>sentinel/2)&np.isfinite(array)]
    unique,counts=np.unique(values,return_counts=True)
    order=np.argsort(unique)[::-1]
    unique=unique[order]; counts=counts[order]
    total=int(counts.sum()); cumulative=0
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    with REPORT.open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f); w.writerow(["density_value","cell_count","percent_positive_cells","cumulative_percent_at_or_above"])
        for value,count in zip(unique,counts):
            cumulative+=int(count)
            w.writerow([float(value),int(count),100*int(count)/total,100*cumulative/total])
    print(f"positive cells: {total}")
    print(f"distinct positive values: {len(unique)}")
    print("highest density values:")
    cumulative=0
    for value,count in list(zip(unique,counts))[:20]:
        cumulative+=int(count)
        print(f"  value {float(value):g}: {int(count)} cells; {100*int(count)/total:.2f}% individually; {100*cumulative/total:.2f}% cumulative")
    print(f"report: {REPORT}")
    print("Complete. No raster or map layer was changed.")


if __name__=="__main__": main()
