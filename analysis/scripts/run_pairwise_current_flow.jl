using Pkg
using Dates

try
    @eval using Circuitscape
catch
    println("Installing Circuitscape.jl in the current Julia environment...")
    Pkg.add("Circuitscape")
    @eval using Circuitscape
end

const INPUT_DIR = raw"C:\cheetah\circuitscape\inputs"
const OUTPUT_DIR = raw"C:\cheetah\circuitscape\outputs"
const YEARS = (2012, 2016, 2020, 2024)
const CORES = joinpath(INPUT_DIR, "cheetah_cores_fixed_23.asc")

mkpath(OUTPUT_DIR)

if !isfile(CORES)
    error("Missing focal-core raster: $CORES")
end

println("Pairwise Circuitscape current-flow analysis")
println("Julia threads: ", Threads.nthreads())
println("Fixed focal regions: 23")
println("Contributing pairs per year: 253")
println("Years: ", join(YEARS, ", "))

for year in YEARS
    habitat = joinpath(INPUT_DIR, "resistance_primary_unfenced_$(year).asc")
    if !isfile(habitat)
        error("Missing resistance raster: $habitat")
    end

    output_base = joinpath(OUTPUT_DIR, "current_primary_unfenced_$(year)")
    cfg = Circuitscape.init_config()
    cfg["data_type"] = "raster"
    cfg["scenario"] = "pairwise"
    cfg["habitat_file"] = habitat
    cfg["habitat_map_is_resistances"] = "True"
    cfg["point_file"] = CORES
    cfg["use_included_pairs"] = "False"

    # Standard eight-neighbor raster connectivity and Circuitscape's default
    # conductance averaging are held constant across all four snapshots.
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

    # CG+AMG is the documented solver for large grids. Double precision avoids
    # adding a numerical-precision sensitivity to the biological scenarios.
    cfg["solver"] = "cg+amg"
    cfg["precision"] = "Double"
    cfg["use_64bit_indexing"] = "True"
    cfg["parallelize"] = "True"
    cfg["low_memory_mode"] = "True"
    cfg["preemptive_memory_release"] = "True"
    cfg["log_level"] = "INFO"
    cfg["log_file"] = joinpath(OUTPUT_DIR, "current_primary_unfenced_$(year).log")
    cfg["screenprint_log"] = "True"
    cfg["print_timings"] = "True"

    println("\nStarting $year: ", Dates.now())
    Circuitscape.compute(cfg)
    println("Finished $year: ", Dates.now())
end

open(joinpath(OUTPUT_DIR, "PAIRWISE_CURRENT_FLOW_COMPLETE.txt"), "w") do io
    println(io, "completed=", Dates.now())
    println(io, "years=", join(YEARS, ","))
    println(io, "fixed_core_count=23")
    println(io, "pairs_per_year=253")
    println(io, "solver=cg+amg")
    println(io, "precision=Double")
    println(io, "neighbors=8")
    println(io, "edge_aggregation=average_conductance")
end

println("\nAll four years complete.")
println("Outputs: $OUTPUT_DIR")
