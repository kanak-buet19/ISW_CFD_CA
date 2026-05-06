#!/usr/bin/env bash

set -Eeo pipefail

CASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$CASE_DIR"

on_error()
{
    local status="$?"
    local line="${BASH_LINENO[0]:-unknown}"
    local command="${BASH_COMMAND:-unknown}"

    echo
    echo "ERROR: trial_allrun.sh failed"
    echo "Exit status: $status"
    echo "Line: $line"
    echo "Command: $command"
    echo "Working directory: $PWD"
    echo "Time: $(date)"
    echo
    exit "$status"
}

trap on_error ERR

echo "=== Trial Allrun: setup only ==="
echo "Case directory: $CASE_DIR"
echo "Host: $(hostname)"
echo "Shell: $SHELL"
echo "Time: $(date)"
echo

echo "=== Modules ==="
module load gcc/11.2.0 openmpi/4.0.6
module list 2>&1
echo

export WM_PROJECT_DIR=$HOME/OpenFOAM/OpenFOAM-10
echo "=== OpenFOAM setup ==="
echo "Sourcing: $WM_PROJECT_DIR/etc/bashrc"
trap - ERR
set +e
source "$WM_PROJECT_DIR/etc/bashrc"
OPENFOAM_SOURCE_STATUS=$?
set -e
trap on_error ERR

echo "OpenFOAM source exit status: $OPENFOAM_SOURCE_STATUS"
echo "WM_PROJECT_DIR=$WM_PROJECT_DIR"
echo "WM_PROJECT_VERSION=${WM_PROJECT_VERSION:-unset}"
echo "FOAM_USER_APPBIN=${FOAM_USER_APPBIN:-unset}"
echo "FOAM_APPBIN=${FOAM_APPBIN:-unset}"
echo

echo "=== Required commands ==="
for command_name in \
    gcc \
    mpirun \
    blockMesh \
    setSolidFraction \
    transformPoints \
    decomposePar \
    reconstructPar \
    foamToVTK \
    laserbeamFoam_ISW
do
    printf '%-22s' "$command_name"
    command -v "$command_name"
done
echo

echo "=== Versions ==="
gcc --version | head -1
mpirun --version | head -3
echo

export MPLCONFIGDIR="${MPLCONFIGDIR:-$CASE_DIR/.mplconfig}"
mkdir -p "$MPLCONFIGDIR"

export SLICE_PYTHON="${SLICE_PYTHON:-/home/x-rkanak1/.conda/envs/isw_env/bin/python3}"
echo "=== Python watcher environment ==="
echo "SLICE_PYTHON=$SLICE_PYTHON"
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
echo

echo "=== Case files ==="
for path in \
    initial \
    constant \
    system \
    scripts/watch_reconstruct_slices.sh \
    scripts/write_vtk_series.py \
    scripts/analyze_meltpool_vtk.py \
    system/blockMeshDict \
    system/decomposeParDict \
    system/controlDict
do
    if [ -e "$path" ]; then
        echo "OK: $path"
    else
        echo "MISSING: $path"
        exit 1
    fi
done
echo

echo "Trial setup completed. Solver was not run."
