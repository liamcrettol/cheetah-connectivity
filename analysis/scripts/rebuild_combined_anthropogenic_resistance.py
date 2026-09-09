"""Build the revised anthropogenic-pressure model and sensitivity surfaces.

Livestock is incorporated within anthropogenic pressure instead of being treated
as an independent top-level mechanism. Existing resistance rasters are preserved.
"""

import sys
import os
import csv

sys.path.insert(0, r"C:\Users\lcrettol\Documents\Codex\2026-08-25\i-am-working-on-this-spreadsheet\outputs")
from resistance_model_utils import *
from arcpy.sa import Raster

BUILT = os.path.join(GDB, "pressure_built_1_10")
ROADS = os.path.join(GDB, "pressure_roads_1_10")
LIVESTOCK = os.path.join(GDB, "pressure_livestock_index_1_10")
LIGHTS = os.path.join(GDB, "pressure_lights_1_10")
TERRAIN = os.path.join(GDB, "terrain_resistance_1_10")

ANTHRO_PRIMARY = os.path.join(GDB, "pressure_anthropogenic_primary_1_10")
ANTHRO_EQUAL = os.path.join(GDB, "pressure_anthropogenic_equal_1_10")
ANTHRO_INFRA = os.path.join(GDB, "pressure_anthropogenic_infrastructure_1_10")

BASE_PRIMARY = os.path.join(GDB, "resistance_primary_unfenced_combined")
BASE_EQUAL = os.path.join(GDB, "resistance_sensitivity_equal_unfenced")
BASE_INFRA = os.path.join(GDB, "resistance_sensitivity_infrastructure_unfenced")

MULTIPLIERS = {
    "fence_main": os.path.join(GDB, "fence_multiplier_main_1km"),
    "fence_nearbarrier": os.path.join(GDB, "fence_multiplier_nearbarrier_1km"),
    "kruger_documented": os.path.join(GDB, "fence_multiplier_main_kruger_documented_1km"),
    "kruger_conservative": os.path.join(GDB, "fence_multiplier_main_kruger_conservative_1km"),
}
SCENARIOS = {
    "fence_main": os.path.join(GDB, "resistance_primary_fence_main_combined"),
    "fence_nearbarrier": os.path.join(GDB, "resistance_primary_fence_nearbarrier_combined"),
    "kruger_documented": os.path.join(GDB, "resistance_primary_kruger_documented_combined"),
    "kruger_conservative": os.path.join(GDB, "resistance_primary_kruger_conservative_combined"),
}

WEIGHT_SETS = {
    "primary": {"built": 0.30, "roads": 0.30, "livestock": 0.30, "lights": 0.10},
    "equal": {"built": 0.25, "roads": 0.25, "livestock": 0.25, "lights": 0.25},
    "infrastructure": {"built": 0.35, "roads": 0.35, "livestock": 0.20, "lights": 0.10},
}


def weighted_anthropogenic(weights):
    return (
        weights["built"] * Raster(BUILT)
        + weights["roads"] * Raster(ROADS)
        + weights["livestock"] * Raster(LIVESTOCK)
        + weights["lights"] * Raster(LIGHTS)
    )


def save_raster(map_object, expression, output):
    replace(map_object, output)
    expression.save(output)
    arcpy.management.CalculateStatistics(output, 1, 1, [], "OVERWRITE")
    print(f"created: {Path(output).name}")


def main():
    setup_env()
    require(BUILT, ROADS, LIVESTOCK, LIGHTS, TERRAIN, *MULTIPLIERS.values())
    aprx, map_object, parent = project_and_map()
    backup(aprx, "combined_anthropogenic_resistance")

    component_group = group(map_object, parent, COMPONENT_GROUP)
    final_group = group(map_object, parent, FINAL_GROUP)

    save_raster(map_object, weighted_anthropogenic(WEIGHT_SETS["primary"]), ANTHRO_PRIMARY)
    save_raster(map_object, weighted_anthropogenic(WEIGHT_SETS["equal"]), ANTHRO_EQUAL)
    save_raster(map_object, weighted_anthropogenic(WEIGHT_SETS["infrastructure"]), ANTHRO_INFRA)

    save_raster(map_object, 0.80 * Raster(ANTHRO_PRIMARY) + 0.20 * Raster(TERRAIN), BASE_PRIMARY)
    save_raster(map_object, 0.80 * Raster(ANTHRO_EQUAL) + 0.20 * Raster(TERRAIN), BASE_EQUAL)
    save_raster(map_object, 0.80 * Raster(ANTHRO_INFRA) + 0.20 * Raster(TERRAIN), BASE_INFRA)

    for scenario, multiplier in MULTIPLIERS.items():
        save_raster(map_object, Raster(BASE_PRIMARY) * Raster(multiplier), SCENARIOS[scenario])

    for dataset in (ANTHRO_PRIMARY, ANTHRO_EQUAL, ANTHRO_INFRA):
        add_grouped(map_object, component_group, dataset, dataset == ANTHRO_PRIMARY)
    for dataset in (BASE_PRIMARY, BASE_EQUAL, BASE_INFRA, *SCENARIOS.values()):
        add_grouped(map_object, final_group, dataset, dataset == BASE_PRIMARY)
    component_group.visible = True
    final_group.visible = True

    REPORTS.mkdir(parents=True, exist_ok=True)
    decision_report = REPORTS / "combined_anthropogenic_resistance_decision.csv"
    with decision_report.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["model", "level", "component", "weight", "interpretation"])
        for model, weights in WEIGHT_SETS.items():
            for component, weight in weights.items():
                writer.writerow([model, "within_anthropogenic", component, weight, "explicit hypothesis; compare sensitivity models"])
        writer.writerow(["all", "top_level", "anthropogenic_pressure", 0.80, "built, roads, livestock, and lights combined"])
        writer.writerow(["all", "top_level", "terrain", 0.20, "separate physical movement-cost mechanism"])
        writer.writerow(["all", "context_only", "VCF and categorical land cover", 0, "interpretation and validation; no independent penalty"])

    aprx.save()
    arcpy.CheckInExtension("Spatial")
    print(f"decision report: {decision_report}")
    print("Complete. Revised primary and sensitivity surfaces were created; previous resistance surfaces were preserved.")


if __name__ == "__main__":
    main()
