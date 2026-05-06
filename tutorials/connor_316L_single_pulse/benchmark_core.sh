#!/bin/bash
#SBATCH --job-name=connorBench
#SBATCH --time=02:00:00
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=64
#SBATCH --account=mch250110
#SBATCH --output=benchmark_core_%j.out
#SBATCH --error=benchmark_core_%j.err

set -u

cd "$SLURM_SUBMIT_DIR"

module load gcc/11.2.0 openmpi/4.0.6
export WM_PROJECT_DIR=$HOME/OpenFOAM/OpenFOAM-10
set +u
source "$WM_PROJECT_DIR/etc/bashrc"
set -u
export FOAM_SIGFPE=0
export OMP_NUM_THREADS=1

export MPLCONFIGDIR="${MPLCONFIGDIR:-$SLURM_SUBMIT_DIR/.mplconfig}"
mkdir -p "$MPLCONFIGDIR"

CORE_COUNTS="${CORE_COUNTS:-8 16 32 64}"
BENCHMARK_END_TIME="${BENCHMARK_END_TIME:-1e-4}"
SLICE_PYTHON="${SLICE_PYTHON:-/home/x-rkanak1/.conda/envs/isw_env/bin/python3}"

BENCH_ROOT="$SLURM_SUBMIT_DIR/benchmark_core_runs"
RESULTS_CSV="$BENCH_ROOT/benchmark_core_results.csv"
PLOT_FILE="$BENCH_ROOT/benchmark_core_results.png"

mkdir -p "$BENCH_ROOT"

echo "=== Connor core-scaling benchmark ==="
echo "Case: $SLURM_SUBMIT_DIR"
echo "Allocated Slurm tasks: ${SLURM_NTASKS:-unknown}"
echo "Core counts: $CORE_COUNTS"
echo "Benchmark solver endTime: $BENCHMARK_END_TIME s"
echo "Results: $RESULTS_CSV"
echo

printf 'cores,total_cells,target_end_time,final_sim_time,execution_time_s,clock_time_s,sim_seconds_per_clock_second,clock_seconds_per_sim_second,last_deltaT,status,run_dir,solver_log\n' > "$RESULTS_CSV"

set_control_value()
{
    local file="$1"
    local key="$2"
    local value="$3"
    local comment="${4:-}"

    if [ -n "$comment" ]; then
        sed -i -E "s|^([[:space:]]*$key[[:space:]]+).*|\\1$value;            // $comment|" "$file"
    else
        sed -i -E "s|^([[:space:]]*$key[[:space:]]+).*|\\1$value;|" "$file"
    fi
}

parse_solver_log()
{
    local log_file="$1"
    awk '
        /^Time = / {
            t = $3
            gsub(/s/, "", t)
            finalTime = t + 0
        }
        /^deltaT = / {
            deltaT = $3 + 0
        }
        /^ExecutionTime = / {
            executionTime = $3 + 0
            for (i = 1; i <= NF; i++) {
                if ($i == "ClockTime") {
                    clockTime = $(i + 1) + 0
                }
            }
        }
        END {
            if (clockTime > 0) {
                simPerClock = finalTime / clockTime
                clockPerSim = clockTime / finalTime
            } else {
                simPerClock = 0
                clockPerSim = 0
            }
            printf "%.12g,%.12g,%.12g,%.12g,%.12g", finalTime, executionTime, clockTime, simPerClock, clockPerSim
            printf ",%.12g", deltaT
        }
    ' "$log_file"
}

append_failure_row()
{
    local cores="$1"
    local total_cells="$2"
    local status_text="$3"
    local run_dir="$4"
    local solver_log="$5"

    printf '%s,%s,%s,,,,,,,%s,%s,%s\n' \
        "$cores" \
        "$total_cells" \
        "$BENCHMARK_END_TIME" \
        "$status_text" \
        "$run_dir" \
        "$solver_log" >> "$RESULTS_CSV"
}

make_plot()
{
    if [ ! -x "$SLICE_PYTHON" ]; then
        echo "Plot skipped: SLICE_PYTHON is not executable: $SLICE_PYTHON"
        return 0
    fi

    "$SLICE_PYTHON" - "$RESULTS_CSV" "$PLOT_FILE" <<'PY'
import csv
import sys
from pathlib import Path

csv_path = Path(sys.argv[1])
plot_path = Path(sys.argv[2])

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except Exception as exc:
    print(f"Plot skipped: matplotlib import failed: {exc}")
    raise SystemExit(0)

rows = []
with csv_path.open(newline="") as handle:
    reader = csv.DictReader(handle)
    for row in reader:
        if row["status"] == "0" and float(row["sim_seconds_per_clock_second"]) > 0:
            rows.append(row)

if not rows:
    print("Plot skipped: no successful benchmark rows")
    raise SystemExit(0)

cores = [int(row["cores"]) for row in rows]
speed = [float(row["sim_seconds_per_clock_second"]) for row in rows]
wall_per_ms = [float(row["clock_seconds_per_sim_second"]) / 1000.0 for row in rows]

fig, axes = plt.subplots(1, 2, figsize=(10, 4))

axes[0].bar([str(c) for c in cores], speed, color="#2f7d6d")
axes[0].set_xlabel("MPI ranks")
axes[0].set_ylabel("Simulated seconds / wall second")
axes[0].set_title("Solver speed")

axes[1].bar([str(c) for c in cores], wall_per_ms, color="#3f5f9f")
axes[1].set_xlabel("MPI ranks")
axes[1].set_ylabel("Wall seconds / simulated ms")
axes[1].set_title("Cost per simulated ms")

best = max(rows, key=lambda row: float(row["sim_seconds_per_clock_second"]))
fig.suptitle(f"Best speed: {best['cores']} ranks")
fig.tight_layout()
fig.savefig(plot_path, dpi=200)
print(f"Wrote {plot_path}")
PY
}

for cores in $CORE_COUNTS; do
    if [ -n "${SLURM_NTASKS:-}" ] && [ "$cores" -gt "$SLURM_NTASKS" ]; then
        echo "Skipping $cores cores: only $SLURM_NTASKS Slurm tasks allocated"
        continue
    fi

    RUN_DIR="$BENCH_ROOT/core_${cores}"
    CASE_DIR="$RUN_DIR/case"
    SOLVER_LOG="$RUN_DIR/log.solver"

    echo "=== Benchmark: $cores cores ==="
    rm -rf "$RUN_DIR"
    mkdir -p "$CASE_DIR"

    cp -a system constant initial "$CASE_DIR/"

    set_control_value "$CASE_DIR/system/controlDict" "startFrom" "startTime" "benchmark"
    set_control_value "$CASE_DIR/system/controlDict" "startTime" "0" "benchmark"
    set_control_value "$CASE_DIR/system/controlDict" "endTime" "$BENCHMARK_END_TIME" "benchmark"
    set_control_value "$CASE_DIR/system/controlDict" "writeInterval" "$BENCHMARK_END_TIME" "benchmark"
    set_control_value "$CASE_DIR/system/decomposeParDict" "numberOfSubdomains" "$cores" "benchmark"

    cd "$CASE_DIR" || exit 1

    echo "Preparing mesh and decomposition for $cores cores..."
    rm -rf 0 processor* postProcessing VTK
    cp -a initial 0

    blockMesh > "$RUN_DIR/log.blockMesh" 2>&1 || {
        echo "blockMesh failed for $cores cores"
        append_failure_row "$cores" "unknown" "blockMesh_failed" "$RUN_DIR" "$SOLVER_LOG"
        cd "$SLURM_SUBMIT_DIR" || exit 1
        continue
    }

    setSolidFraction > "$RUN_DIR/log.setSolidFraction" 2>&1 || {
        echo "setSolidFraction failed for $cores cores"
        append_failure_row "$cores" "unknown" "setSolidFraction_failed" "$RUN_DIR" "$SOLVER_LOG"
        cd "$SLURM_SUBMIT_DIR" || exit 1
        continue
    }

    transformPoints "rotate=((0 1 0) (0 0 1))" > "$RUN_DIR/log.transformPoints" 2>&1 || {
        echo "transformPoints failed for $cores cores"
        append_failure_row "$cores" "unknown" "transformPoints_failed" "$RUN_DIR" "$SOLVER_LOG"
        cd "$SLURM_SUBMIT_DIR" || exit 1
        continue
    }

    decomposePar > "$RUN_DIR/log.decomposePar" 2>&1 || {
        echo "decomposePar failed for $cores cores"
        append_failure_row "$cores" "unknown" "decomposePar_failed" "$RUN_DIR" "$SOLVER_LOG"
        cd "$SLURM_SUBMIT_DIR" || exit 1
        continue
    }

    total_cells="$(awk '/nCells:/ {print $2; exit}' "$RUN_DIR/log.blockMesh")"
    total_cells="${total_cells:-unknown}"

    echo "Running solver only on $cores cores..."
    mpirun -np "$cores" laserbeamFoam_ISW -parallel > "$SOLVER_LOG" 2>&1
    status=$?

    parsed="$(parse_solver_log "$SOLVER_LOG")"
    printf '%s,%s,%s,%s,%s,%s,%s,%s\n' \
        "$cores" \
        "$total_cells" \
        "$BENCHMARK_END_TIME" \
        "$parsed" \
        "$status" \
        "$RUN_DIR" \
        "$SOLVER_LOG" >> "$RESULTS_CSV"

    echo "Finished $cores cores with solver status $status"
    cd "$SLURM_SUBMIT_DIR" || exit 1
    echo
done

echo "=== Benchmark CSV ==="
cat "$RESULTS_CSV"
echo

make_plot

echo
echo "Benchmark complete."
echo "CSV:  $RESULTS_CSV"
echo "Plot: $PLOT_FILE"
