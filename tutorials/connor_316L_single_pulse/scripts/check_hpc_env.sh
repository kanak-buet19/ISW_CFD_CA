#!/usr/bin/env bash

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
JOB_SH="$CASE_DIR/job.sh"

EXPECTED_CONDA_ENV="${EXPECTED_CONDA_ENV:-isw_env}"
EXPECTED_OF_VERSION="${EXPECTED_OF_VERSION:-10}"
REQUIRED_PYTHON_MODULES="vtk matplotlib numpy pandas pyvista scipy"
REQUIRED_COMMANDS="blockMesh setSolidFraction transformPoints decomposePar reconstructPar foamToVTK laserbeamFoam_ISW mpirun sbatch"

export MPLCONFIGDIR="${MPLCONFIGDIR:-$CASE_DIR/.mplconfig}"
mkdir -p "$MPLCONFIGDIR"

failures=0
warnings=0

ok()
{
    printf '[OK] %s\n' "$*"
}

warn()
{
    warnings=$((warnings + 1))
    printf '[WARN] %s\n' "$*"
}

fail()
{
    failures=$((failures + 1))
    printf '[FAIL] %s\n' "$*"
}

check_file()
{
    if [ -e "$1" ]; then
        ok "$2: $1"
    else
        fail "$2 missing: $1"
    fi
}

check_executable()
{
    if [ -x "$1" ]; then
        ok "$2 executable: $1"
    else
        fail "$2 is not executable: $1"
    fi
}

check_command()
{
    if command -v "$1" >/dev/null 2>&1; then
        ok "$1 -> $(command -v "$1")"
    else
        fail "$1 is not visible in PATH"
    fi
}

extract_job_slice_python()
{
    awk -F= '/^[[:space:]]*export[[:space:]]+SLICE_PYTHON=/ {
        value=$2
        gsub(/^"/, "", value)
        gsub(/"$/, "", value)
        print value
        exit
    }' "$JOB_SH"
}

extract_job_ntasks()
{
    awk -F= '/^#SBATCH[[:space:]]+--ntasks-per-node=/ {
        print $2
        exit
    }' "$JOB_SH" | tr -d '[:space:]'
}

extract_decompose_subdomains()
{
    awk '/numberOfSubdomains/ {
        gsub(/;/, "", $2)
        print $2
        exit
    }' "$CASE_DIR/system/decomposeParDict"
}

check_python_modules()
{
    local python_bin="$1"
    local label="$2"

    if [ ! -x "$python_bin" ]; then
        fail "$label Python is not executable: $python_bin"
        return
    fi

    ok "$label Python executable: $python_bin"
    "$python_bin" - <<PY
import importlib
import sys

required = "$REQUIRED_PYTHON_MODULES".split()
missing = []

for module in required:
    try:
        importlib.import_module(module)
    except Exception as exc:
        missing.append(f"{module}: {exc}")

if missing:
    print("Missing Python modules:")
    for item in missing:
        print(f"  - {item}")
    sys.exit(1)

print("All required Python modules import successfully.")
PY
    if [ "$?" -eq 0 ]; then
        ok "$label Python modules: $REQUIRED_PYTHON_MODULES"
    else
        fail "$label Python is missing required modules"
    fi
}

echo "=== Connor 316L HPC pre-submit check ==="
echo "Case directory: $CASE_DIR"
echo

if [ "$(pwd)" = "$CASE_DIR" ]; then
    ok "Running from case directory"
else
    warn "Current directory is not the case directory. Recommended: cd $CASE_DIR"
fi

check_file "$JOB_SH" "Slurm job script"
check_file "$CASE_DIR/system/blockMeshDict" "blockMeshDict"
check_file "$CASE_DIR/system/decomposeParDict" "decomposeParDict"
check_file "$CASE_DIR/system/controlDict" "controlDict"
check_file "$CASE_DIR/initial" "initial directory"

echo
echo "=== Conda/Python ==="
if [ "${CONDA_DEFAULT_ENV:-}" = "$EXPECTED_CONDA_ENV" ]; then
    ok "Active conda environment is $EXPECTED_CONDA_ENV"
else
    fail "Active conda environment is '${CONDA_DEFAULT_ENV:-none}', expected '$EXPECTED_CONDA_ENV'"
fi

if command -v python >/dev/null 2>&1; then
    active_python="$(command -v python)"
    check_python_modules "$active_python" "active conda"
else
    fail "python is not visible in PATH"
fi

job_slice_python="$(extract_job_slice_python)"
if [ -n "$job_slice_python" ]; then
    check_python_modules "$job_slice_python" "job.sh SLICE_PYTHON"
    if command -v python >/dev/null 2>&1 && [ "$(readlink -f "$(command -v python)")" = "$(readlink -f "$job_slice_python" 2>/dev/null)" ]; then
        ok "job.sh SLICE_PYTHON matches active python"
    else
        warn "job.sh SLICE_PYTHON does not match active python: $job_slice_python"
    fi
else
    fail "Could not find SLICE_PYTHON export in job.sh"
fi

echo
echo "=== OpenFOAM/OpenMPI ==="
if [ -n "${WM_PROJECT_DIR:-}" ]; then
    ok "WM_PROJECT_DIR=$WM_PROJECT_DIR"
    if [ -f "$WM_PROJECT_DIR/etc/bashrc" ]; then
        ok "OpenFOAM bashrc exists"
    else
        fail "OpenFOAM bashrc missing: $WM_PROJECT_DIR/etc/bashrc"
    fi
else
    fail "WM_PROJECT_DIR is not set. Run your of10 setup before this check."
fi

if [ "${WM_PROJECT_VERSION:-}" = "$EXPECTED_OF_VERSION" ]; then
    ok "WM_PROJECT_VERSION=$WM_PROJECT_VERSION"
else
    warn "WM_PROJECT_VERSION='${WM_PROJECT_VERSION:-unset}', expected '$EXPECTED_OF_VERSION'"
fi

for command_name in $REQUIRED_COMMANDS; do
    check_command "$command_name"
done

echo
echo "=== Case scripts ==="
check_executable "$CASE_DIR/scripts/watch_reconstruct_slices.sh" "watcher"
check_executable "$CASE_DIR/scripts/write_vtk_series.py" "VTK series writer"
check_file "$CASE_DIR/scripts/analyze_meltpool_vtk.py" "meltpool analysis script"

if bash -n "$JOB_SH"; then
    ok "job.sh shell syntax"
else
    fail "job.sh shell syntax"
fi

if bash -n "$CASE_DIR/scripts/watch_reconstruct_slices.sh"; then
    ok "watch_reconstruct_slices.sh shell syntax"
else
    fail "watch_reconstruct_slices.sh shell syntax"
fi

if [ -n "${active_python:-}" ] && "$active_python" -m py_compile \
    "$CASE_DIR/scripts/analyze_meltpool_vtk.py" \
    "$CASE_DIR/scripts/write_vtk_series.py"; then
    ok "Python scripts compile"
else
    fail "Python scripts compile"
fi

echo
echo "=== Slurm/decomposition ==="
job_ntasks="$(extract_job_ntasks)"
subdomains="$(extract_decompose_subdomains)"

if [ -n "$job_ntasks" ]; then
    ok "job.sh ntasks-per-node=$job_ntasks"
else
    fail "Could not read ntasks-per-node from job.sh"
fi

if [ -n "$subdomains" ]; then
    ok "decomposeParDict numberOfSubdomains=$subdomains"
else
    fail "Could not read numberOfSubdomains from decomposeParDict"
fi

if [ -n "$job_ntasks" ] && [ -n "$subdomains" ]; then
    if [ "$job_ntasks" = "$subdomains" ]; then
        ok "Slurm task count matches OpenFOAM decomposition"
    else
        fail "Slurm task count ($job_ntasks) does not match numberOfSubdomains ($subdomains)"
    fi
fi

echo
if [ "$failures" -eq 0 ]; then
    if [ "$warnings" -eq 0 ]; then
        echo "GREEN SIGNAL: environment looks ready for sbatch job.sh"
    else
        echo "GREEN SIGNAL WITH WARNINGS: no blocking failures, but review warnings above"
    fi
    exit 0
fi

echo "NO GREEN SIGNAL: $failures blocking check(s) failed, $warnings warning(s)"
exit 1
