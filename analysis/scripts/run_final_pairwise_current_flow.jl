using Pkg
using Dates

try
    @eval using Circuitscape
catch
    println("Installing Circuitscape.jl in the current Julia environment...")
    Pkg.add("Circuitscape")
    @eval using Circuitscape
end

const INPUT_DIR = raw"C:\cheetah\circuitscape\inputs\final_balanced_fence_documented"
const OUTPUT_DIR = raw"C:\cheetah\circuitscape\outputs\final_balanced_fence_documented"
const YEARS = (2012, 2016, 2020, 2024)
const CORES = joinpath(INPUT_DIR, "cheetah_cores_fixed_23.asc")

mkpath(OUTPUT_DIR)
isfile(CORES) || error("Missing final focal-core raster: $CORES")

println("FINAL pairwise Circuitscape current-flow analysis")
println("Scenario: vegetation-balanced + documented finite KAZA/Kruger fences")
println("Julia threads: ", Threads.nthreads())
println("Fixed focal regions: 23; contributing pairs per year: 253")
println("Years: ", join(YEARS, ", "))

for year in YEARS
    resistance = joinpath(INPUT_DIR, "resistance_final_balanced_fence_documented_$(year).asc")
    isfile(resistance) || error("Missing final resistance raster: $resistance")
    output_base = joinpath(OUTPUT_DIR, "current_final_balanced_fence_documented_$(year)")
    cfg = Circuitscape.init_config()
    cfg["data_type"] = "raster"
    cfg["scenario"] = "pairwise"
    cfg["habitat_file"] = resistance
    cfg["habitat_map_is_resistances"] = "True"
    cfg["point_file"] = CORES
    cfg["use_included_pairs"] = "False"
    cfg["connect_four_neighbors_only"] = "False"
    cfg["connect_using_avg_resistances"] = "False"
    cfg["output_file"] = output_base
    cfg["write_cur_maps"] = "True"
    cfg["write_cum_cur_map_only"] = "True"
    cfg["write_max_cur_maps"] = "False"
    cfg["write_volt_maps"] = "False"
    cfg["write_as_tif"] = "True"
    cfg["set_null_currents_to_nodata"] = "True"
    cfg["log_transform_maps"] = "False"
    cfg["solver"] = "cg+amg"
    cfg["precision"] = "Double"
    cfg["use_64bit_indexing"] = "True"
    cfg["parallelize"] = "True"
    cfg["low_memory_mode"] = "True"
    cfg["preemptive_memory_release"] = "True"
    cfg["log_level"] = "INFO"
    cfg["log_file"] = joinpath(OUTPUT_DIR, "current_final_balanced_fence_documented_$(year).log")
    cfg["screenprint_log"] = "True"
    cfg["print_timings"] = "True"
    println("\nStarting final $year: ", Dates.now())
    Circuitscape.compute(cfg)
    println("Finished final $year: ", Dates.now())
end

open(joinpath(OUTPUT_DIR, "FINAL_PAIRWISE_CURRENT_FLOW_COMPLETE.txt"), "w") do io
    println(io, "completed=", Dates.now())
    println(io, "scenario=vegetation-balanced + documented finite KAZA/Kruger fence")
    println(io, "years=", join(YEARS, ","))
    println(io, "fixed_core_count=23")
    println(io, "pairs_per_year=253")
    println(io, "solver=cg+amg; precision=Double; neighbors=8")
end

println("\nAll final current-flow runs complete.")
println("Outputs: $OUTPUT_DIR")
