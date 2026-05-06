#!/bin/bash
#SBATCH --job-name=connor316L
#SBATCH --time=30:00:00
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=64
#SBATCH --account=mch250110
#SBATCH --output=output_%j.out
#SBATCH --error=output_%j.err

set -Eeo pipefail

echo "=== Slurm job bootstrap ==="
echo "Script: $0"
echo "Submit directory: ${SLURM_SUBMIT_DIR:-unset}"
echo "Launch directory: $PWD"
echo "Shell: $SHELL"
echo "==========================="

SLICE_WATCHER_PID=""

finish_watcher()
{
    if [ -d slice_plots ]; then
        touch slice_plots/.solverDone
    fi

    if [ -n "$SLICE_WATCHER_PID" ]; then
        wait "$SLICE_WATCHER_PID" || true
    fi
}

on_error()
{
    local status="$?"
    local line="${BASH_LINENO[0]:-unknown}"
    local command="${BASH_COMMAND:-unknown}"

    echo
    echo "ERROR: job.sh failed"
    echo "Exit status: $status"
    echo "Line: $line"
    echo "Command: $command"
    echo "Working directory: $PWD"
    echo "Time: $(date)"
    echo

    finish_watcher
    exit "$status"
}

trap on_error ERR

cd "$SLURM_SUBMIT_DIR"
export MPLCONFIGDIR="${MPLCONFIGDIR:-$SLURM_SUBMIT_DIR/.mplconfig}"
mkdir -p "$MPLCONFIGDIR"

module load gcc/11.2.0 openmpi/4.0.6
export WM_PROJECT_DIR=$HOME/OpenFOAM/OpenFOAM-10

echo "Sourcing OpenFOAM: $WM_PROJECT_DIR/etc/bashrc"
trap - ERR
set +e
source "$WM_PROJECT_DIR/etc/bashrc"
OPENFOAM_SOURCE_STATUS=$?
set -e
trap on_error ERR

echo "OpenFOAM source exit status: $OPENFOAM_SOURCE_STATUS"
if [ "$OPENFOAM_SOURCE_STATUS" -ne 0 ]; then
    echo "WARNING: OpenFOAM bashrc returned nonzero status during setup."
    echo "Continuing to explicit command checks so the missing tool is visible."
fi

export FOAM_SIGFPE=0

. "$WM_PROJECT_DIR/bin/tools/RunFunctions"

RESTART="${RESTART:-0}"

echo "=== Environment Check ==="
gcc --version | head -1
which mpirun
mpirun --version
echo "WM_PROJECT_DIR=$WM_PROJECT_DIR"
echo "WM_PROJECT_VERSION=${WM_PROJECT_VERSION:-unset}"
echo "FOAM_USER_APPBIN=${FOAM_USER_APPBIN:-unset}"
echo "FOAM_APPBIN=${FOAM_APPBIN:-unset}"
command -v blockMesh
command -v setSolidFraction
command -v transformPoints
command -v decomposePar
command -v laserbeamFoam_ISW
echo "========================"

echo "Job started at: $(date)"
echo "Running on node: $(hostname)"
echo "Job ID: ${SLURM_JOB_ID:-unknown}"
echo "Number of tasks: ${SLURM_NTASKS:-unknown}"
echo "Restart mode: $RESTART"

if [ "$RESTART" = "1" ]; then
    echo "=== Manual restart mode ==="

    if ! find processor0 -maxdepth 1 -mindepth 1 -type d 2>/dev/null | grep -q .; then
        echo "ERROR: RESTART=1 was requested, but processor0 time folders were not found."
        echo "Cannot restart. Submit without RESTART=1 for a fresh run."
        exit 1
    fi

    echo "Keeping existing 0/, processor*/, mesh, and latest decomposed time folders."
    echo "Solver will restart because controlDict has startFrom latestTime."

else
    echo "=== Fresh run mode ==="

    echo "Removing old run data"
    rm -rf 0 processor* VTK post-processing-data slice_plots
    rm -f log.* *.OpenFOAM

    echo "Copying 'initial' to 0"
    cp -r initial 0

    echo "Running blockMesh"
    runApplication -o blockMesh

    echo "Running setSolidFraction"
    runApplication -o setSolidFraction

    echo "Running transformPoints with rotation"
    runApplication -o transformPoints "rotate=((0 1 0) (0 0 1))"

    echo "Decomposing domain for parallel run"
    decomposePar || exit 1
fi

# --- Watcher setup ---
mkdir -p slice_plots
rm -f slice_plots/.solverDone
export SLICE_PYTHON=/home/x-rkanak1/.conda/envs/isw_env/bin/python3

echo "=== Python watcher environment check ==="
if [ ! -x "$SLICE_PYTHON" ]; then
    echo "ERROR: SLICE_PYTHON is not executable: $SLICE_PYTHON"
    exit 1
fi

"$SLICE_PYTHON" - <<'PY'
import importlib
import sys

required = ["vtk", "matplotlib", "numpy", "pandas", "pyvista", "scipy"]
missing = []

for module in required:
    try:
        importlib.import_module(module)
    except Exception as exc:
        missing.append(f"{module}: {exc}")

if missing:
    print("ERROR: missing Python modules needed by watcher/post-processing scripts:")
    for item in missing:
        print(f"  - {item}")
    sys.exit(1)

print("Python environment OK: all watcher/post-processing modules imported.")
PY
echo "========================================"

chmod +x scripts/watch_reconstruct_slices.sh
./scripts/watch_reconstruct_slices.sh "$PWD" &
SLICE_WATCHER_PID=$!

# --- Main Simulation Run ---
echo "Starting parallel laserbeamFoam_ISW simulation with $SLURM_NTASKS cores"
set +e
mpirun -np "$SLURM_NTASKS" laserbeamFoam_ISW -parallel
SOLVER_STATUS=$?
set -e

finish_watcher

echo "Solver finished with exit code: $SOLVER_STATUS"

if [ "$SOLVER_STATUS" -ne 0 ]; then
    echo "laserbeamFoam_ISW failed with status $SOLVER_STATUS"
    exit "$SOLVER_STATUS"
fi

# --- Post-processing ---
echo "Reconstructing fields from parallel run"
reconstructPar

echo "Converting to VTK format"
foamToVTK -useTimeName

echo "Writing ParaView VTK series file"
"$SLICE_PYTHON" scripts/write_vtk_series.py VTK

echo "Job completed at: $(date)"
