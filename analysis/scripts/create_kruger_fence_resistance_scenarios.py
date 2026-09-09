"""Add documented and conservative Kruger fence scenarios to the resistance model.

Run inside the ArcGIS Pro Python window after prepare_kruger_fence_reference.py.
The default scenario penalizes only DOCUMENTED_FENCED boundary sections. The
conservative sensitivity scenario also penalizes UNCERTAIN sections. Sections
classified DOCUMENTED_OPEN are never penalized. Existing datasets are preserved.
"""

import csv
import os
import sys

sys.path.insert(0, r"C:\Users\lcrettol\Documents\Codex\2026-08-25\i-am-working-on-this-spreadsheet\outputs")
from resistance_model_utils import *
from arcpy.sa import CellStatistics, Con, IsNull, Raster


KRUGER_ALL = os.path.join(GDB, "kruger_boundary_fence_status_reference")
KRUGER_DOCUMENTED = os.path.join(GDB, "kruger_fence_documented_reference")
KAZA_MAIN = os.path.join(GDB, "fence_multiplier_main_1km")
BASE = os.path.join(GDB, "resistance_base_unfenced_1_10")

DOC_SELECTION = os.path.join(GDB, "tmp_kruger_fence_documented")
CONSERVATIVE_SELECTION = os.path.join(GDB, "tmp_kruger_fence_documented_uncertain")
DOC_RAW = os.path.join(GDB, "tmp_kruger_fence_documented_cells")
CONSERVATIVE_RAW = os.path.join(GDB, "tmp_kruger_fence_conservative_cells")

DOC_PRESENCE = os.path.join(GDB, "kruger_fence_presence_documented_1km")
CONSERVATIVE_PRESENCE = os.path.join(GDB, "kruger_fence_presence_conservative_1km")
DOC_MULTIPLIER = os.path.join(GDB, "kruger_fence_multiplier_documented_1km")
CONSERVATIVE_MULTIPLIER = os.path.join(GDB, "kruger_fence_multiplier_conservative_1km")
COMBINED_DOC_MULTIPLIER = os.path.join(GDB, "fence_multiplier_main_kruger_documented_1km")
COMBINED_CONSERVATIVE_MULTIPLIER = os.path.join(GDB, "fence_multiplier_main_kruger_conservative_1km")
DOC_RESISTANCE = os.path.join(GDB, "resistance_scenario_kruger_documented")
CONSERVATIVE_RESISTANCE = os.path.join(GDB, "resistance_scenario_kruger_conservative")

# Same finite, crossable value used by the existing main veterinary-fence model.
# It is an explicit sensitivity assumption, not an empirically fitted coefficient.
FENCE_MULTIPLIER = 25
REFERENCE_GROUP = "11 Veterinary fences · scenarios"


def rasterize(lines, temporary, presence):
    arcpy.conversion.PolylineToRaster(
        lines, "OBJECTID", temporary, "MAXIMUM_LENGTH", cellsize=SNAP
    )
    Con(IsNull(temporary), 0, 1).save(presence)


def main():
    setup_env()
    require(KRUGER_ALL, KRUGER_DOCUMENTED, KAZA_MAIN, BASE)
    aprx, map_object, parent = project_and_map()
    backup(aprx, "kruger_fence_scenarios")

    outputs = (
        DOC_PRESENCE, CONSERVATIVE_PRESENCE, DOC_MULTIPLIER,
        CONSERVATIVE_MULTIPLIER, COMBINED_DOC_MULTIPLIER,
        COMBINED_CONSERVATIVE_MULTIPLIER, DOC_RESISTANCE,
        CONSERVATIVE_RESISTANCE,
    )
    temporaries = (DOC_SELECTION, CONSERVATIVE_SELECTION, DOC_RAW, CONSERVATIVE_RAW)
    for dataset in outputs + temporaries:
        replace(map_object, dataset)

    # Re-select from the complete classified boundary so the logic is explicit
    # and reproducible even if the derived reference layer changes later.
    arcpy.analysis.Select(KRUGER_ALL, DOC_SELECTION, "STATUS = 'DOCUMENTED_FENCED'")
    arcpy.analysis.Select(
        KRUGER_ALL,
        CONSERVATIVE_SELECTION,
        "STATUS IN ('DOCUMENTED_FENCED', 'UNCERTAIN')",
    )
    rasterize(DOC_SELECTION, DOC_RAW, DOC_PRESENCE)
    rasterize(CONSERVATIVE_SELECTION, CONSERVATIVE_RAW, CONSERVATIVE_PRESENCE)

    Con(Raster(DOC_PRESENCE) == 1, FENCE_MULTIPLIER, 1).save(DOC_MULTIPLIER)
    Con(Raster(CONSERVATIVE_PRESENCE) == 1, FENCE_MULTIPLIER, 1).save(CONSERVATIVE_MULTIPLIER)

    # MAX avoids multiplying overlapping KAZA and Kruger fence penalties twice.
    CellStatistics([KAZA_MAIN, DOC_MULTIPLIER], "MAXIMUM", "DATA").save(COMBINED_DOC_MULTIPLIER)
    CellStatistics([KAZA_MAIN, CONSERVATIVE_MULTIPLIER], "MAXIMUM", "DATA").save(COMBINED_CONSERVATIVE_MULTIPLIER)
    (Raster(BASE) * Raster(COMBINED_DOC_MULTIPLIER)).save(DOC_RESISTANCE)
    (Raster(BASE) * Raster(COMBINED_CONSERVATIVE_MULTIPLIER)).save(CONSERVATIVE_RESISTANCE)

    for dataset in outputs:
        arcpy.management.CalculateStatistics(dataset, 1, 1, [], "OVERWRITE")
    for dataset in temporaries:
        if arcpy.Exists(dataset):
            arcpy.management.Delete(dataset)

    reference_group = group(map_object, parent, REFERENCE_GROUP)
    final_group = group(map_object, parent, FINAL_GROUP)
    for dataset in (DOC_PRESENCE, CONSERVATIVE_PRESENCE, DOC_MULTIPLIER,
                    CONSERVATIVE_MULTIPLIER, COMBINED_DOC_MULTIPLIER,
                    COMBINED_CONSERVATIVE_MULTIPLIER):
        add_grouped(map_object, reference_group, dataset, False)
    add_grouped(map_object, final_group, DOC_RESISTANCE, True)
    add_grouped(map_object, final_group, CONSERVATIVE_RESISTANCE, False)

    REPORTS.mkdir(parents=True, exist_ok=True)
    report = REPORTS / "kruger_fence_resistance_scenario_decision.csv"
    with report.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["scenario", "penalized_status", "multiplier", "role", "methodological_basis"])
        writer.writerow(["documented", "DOCUMENTED_FENCED", FENCE_MULTIPLIER,
                         "main Kruger scenario",
                         "finite penalty because cheetah fence permeability can exceed 50%; exact Kruger permeability is unresolved"])
        writer.writerow(["conservative", "DOCUMENTED_FENCED + UNCERTAIN", FENCE_MULTIPLIER,
                         "spatial-uncertainty sensitivity test",
                         "tests whether uncertain boundary sections create implausible modeled shortcuts"])
        writer.writerow(["excluded from both", "DOCUMENTED_OPEN", 1,
                         "known open/transfrontier connections",
                         "SANParks documents unfenced and fence-removed boundary sections"])

    literature = REPORTS / "kruger_fence_methodology_literature.csv"
    with literature.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["citation", "doi_or_url", "relevance_to_decision"])
        writer.writerow(["Cozzi et al. 2013, Journal of Animal Ecology",
                         "https://doi.org/10.1111/1365-2656.12039",
                         "GPS study: fence response was species-specific; adjusted permeability exceeded 50% for cheetahs and wild dogs"])
        writer.writerow(["Jori et al. 2011, Preventive Veterinary Medicine",
                         "https://doi.org/10.1016/j.prevetmed.2011.03.015",
                         "Kruger western/southern fence permeability varied with electrification, maintenance, watercourses, and damage"])
        writer.writerow(["Osipova et al. 2018, Journal of Applied Ecology",
                         "https://doi.org/10.1111/1365-2664.13246",
                         "Compared existing and future fencing connectivity scenarios; high resistance represented an expected impermeable fence"])
        writer.writerow(["SANParks Kruger elephant management plan",
                         "https://www.sanparks.org/wp-content/uploads/2021/03/knp-elephant-management-plan.pdf",
                         "Documents fenced, unfenced, and fence-removed portions of the Kruger boundary"])

    aprx.save()
    print(f"created main Kruger scenario: {DOC_RESISTANCE}")
    print(f"created conservative Kruger scenario: {CONSERVATIVE_RESISTANCE}")
    print(f"fence multiplier: {FENCE_MULTIPLIER} (finite and crossable)")
    print(f"decision report: {report}")
    print(f"literature log: {literature}")
    print("organizing the complete Contents pane...")
    from tidy_cheetah_contents import main as tidy_contents
    tidy_contents()
    print("Complete. Existing resistance surfaces and source layers were unchanged.")


if __name__ == "__main__":
    main()
