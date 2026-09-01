"""Read-only diagnostic for flare-masked VIIRS rasters and their change layers."""

from pathlib import Path

import arcpy


GDB = Path(r"C:\cheetah\gdb\cheetah_working.gdb")
YEARS = (2012, 2016, 2020, 2024)
PAIRS = ((2012, 2016), (2016, 2020), (2020, 2024), (2012, 2024))


def read_property(path, name):
    try:
        return arcpy.management.GetRasterProperties(str(path), name).getOutput(0)
    except arcpy.ExecuteError as exc:
        return f"ERROR: {arcpy.GetMessages(2) or exc}"


def report(path):
    print(f"\n{path.name}")
    print(f"exists: {arcpy.Exists(str(path))}")
    if not arcpy.Exists(str(path)):
        return
    desc = arcpy.Describe(str(path))
    print(f"extent: {desc.extent.XMin}, {desc.extent.YMin}, {desc.extent.XMax}, {desc.extent.YMax}")
    for property_name in ("ROWCOUNT", "COLUMNCOUNT", "ANYNODATA", "ALLNODATA", "MINIMUM", "MAXIMUM"):
        print(f"{property_name}: {read_property(path, property_name)}")


def main():
    print("Masked source rasters")
    for year in YEARS:
        report(GDB / f"lights_{year}_1km_flaremasked")
    print("\nAbsolute change rasters")
    for start, end in PAIRS:
        report(GDB / f"d_lights_{start}_{end}_1km")
    print("\nDiagnostic complete; nothing was changed.")


if __name__ == "__main__":
    main()
