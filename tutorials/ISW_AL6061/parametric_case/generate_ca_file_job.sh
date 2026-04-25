#!/bin/bash
#SBATCH --job-name=vtk_pipeline
#SBATCH --time=48:00:00
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=32
#SBATCH --mem=100G
#SBATCH --account= use account name #search account name using this command : sacctmgr show user $USER
#SBATCH --output=pipeline_output_%j.out
#SBATCH --error=pipeline_output_%j.err

cd $SLURM_SUBMIT_DIR

echo "==============================="
echo " VTK Processing Pipeline Job"
echo "==============================="
echo "Job started at: $(date)"
echo "Running on node: $(hostname)"
echo "Job ID: $SLURM_JOB_ID"
echo "Number of cores: $SLURM_NTASKS"
echo "Memory allocated: 100GB"
echo ""

# ─── CONFIG ───────────────────────────────────────────────────────────────
ROOT_DIR="$(pwd)"
SCRIPTS_DIR="$ROOT_DIR/scripts"
CASES_DIR="/home/kanak/ISW_CFD_CA/tutorials/ISW_AL6061/parametric_case/cases"
RESULTS_DIR="$ROOT_DIR/All_results"

# IMPORTANT: Update these paths for your HPC environment
VENV_PATH="$HOME/venv312/bin/activate"
PARAVIEW_PATH="....../ParaView-5.13.3-MPI-Linux-Python3.10-x86_64/bin/pvpython"

# Clean and create results directory
if [[ -d "$RESULTS_DIR" ]]; then
    echo "🗑️  Cleaning existing results directory..."
    rm -rf "$RESULTS_DIR"/*
    echo "✅ Cleaned All_results directory"
fi
mkdir -p "$RESULTS_DIR"
# ────────────────────────────────────────────────────────────────────────────

# ─── HARDCODED CASE LIST ──────────────────────────────────────────────────
# Specify which cases to run (leave empty to run all cases)
SELECTED_CASES=("case_000")  # Example: ("case_001" "case_005" "case_010")
# ────────────────────────────────────────────────────────────────────────────

echo "==============================="
echo " Automated Processing Pipeline"
echo "==============================="
echo "Running with full domain processing"
echo "Processing all steps (0-6) for all data"
echo ""

# ─── CASE SELECTION ───────────────────────────────────────────────────────
# Check if SELECTED_CASES is defined and not empty
if [[ ${#SELECTED_CASES[@]} -gt 0 ]]; then
    echo "Using hardcoded case list:"
    CASES_TO_RUN=()
    for case_name in "${SELECTED_CASES[@]}"; do
        CASE_PATH="$CASES_DIR/$case_name"
        if [[ -d "$CASE_PATH" ]]; then
            CASES_TO_RUN+=("$CASE_PATH")
            echo "   ✅ $case_name"
        else
            echo "   ⚠️ Warning: $case_name not found, skipping"
        fi
    done
else
    # If SELECTED_CASES is empty, run all cases
    CASES_TO_RUN=("$CASES_DIR"/case_*)
    echo "Running ALL cases in $CASES_DIR"
fi

if [[ ${#CASES_TO_RUN[@]} -eq 0 ]]; then
    echo "❌ No valid cases found. Exiting."
    exit 1
fi

echo ""
echo "Found ${#CASES_TO_RUN[@]} case(s) to process:"
for c in "${CASES_TO_RUN[@]}"; do
    echo "   - $(basename "$c")"
done
echo ""

# Process all steps (0-6) for all cases
START_STEP=0
END_STEP=6

# ─── PROCESSING LOOP ──────────────────────────────────────────────────────
for CASE in "${CASES_TO_RUN[@]}"; do
    CASE_NAME=$(basename "$CASE")
    echo ""
    echo "==============================="
    echo " Processing $CASE_NAME"
    echo "==============================="
    
    WORK_DIR="$CASE/work"
    
    # Clean up existing work directory if it exists
    if [[ -d "$WORK_DIR" ]]; then
        echo "��️  Removing existing work directory..."
        rm -rf "$WORK_DIR"
        echo "✅ Cleaned up old work directory"
    fi
    
    mkdir -p "$WORK_DIR"
    cd "$WORK_DIR"
    
    mkdir -p VTK vts vtu
    
    # ─── STEP 0: VTK Linking and Renaming ─────────────────────────────────
    echo ""
    echo ">>> Step 0: Linking and renaming VTK files"
    
    if ls "$CASE"/VTK/*.vtk 1> /dev/null 2>&1; then
        ln -sf "$CASE"/VTK/*.vtk VTK/
        echo "✅ Linked VTK files from $CASE/VTK/"
        
        cd VTK
        for f in *.vtk; do
            if [[ $f =~ ([0-9]+\.[0-9]+)e([-+][0-9]+) ]]; then
                base=${f%%.vtk}
                num=${BASH_REMATCH[1]}
                exp=${BASH_REMATCH[2]}
                dec=$(printf "%.12f" $(echo "$num * 10^$exp" | bc -l))
                newname="data-${dec}.vtk"
                mv -v "$f" "$newname"
            fi
        done
        cd ..
        echo "✅ Renamed VTK files to decimal notation"
    else
        echo "❌ No VTK files found in $CASE/VTK/"
        cd "$ROOT_DIR"
        continue
    fi
    
    # ─── STEP 1: Mesh Generation (Full Domain) ────────────────────────────
    echo ""
    echo ">>> Step 1: Generating fine mesh over full domain"
    source "$VENV_PATH"
    python "$SCRIPTS_DIR/mesh_gen_vts.py"
    
    if [[ ! -f "fine_mesh.vts" ]]; then
        echo "❌ Error: fine_mesh.vts was not created"
        deactivate || true
        cd "$ROOT_DIR"
        continue
    fi
    echo "✅ Fine mesh generated over full domain: fine_mesh.vts"
    deactivate || true
    
    # ─── STEP 2: VTK to VTU Conversion (All Data) ─────────────────────────
    echo ""
    echo ">>> Step 2: Converting all VTK to VTU"
    source "$VENV_PATH"
    python "$SCRIPTS_DIR/convert_vtk_to_vtu.py"
    
    VTU_COUNT=$(find vtu/ -name "*.vtu" 2>/dev/null | wc -l)
    if [[ $VTU_COUNT -eq 0 ]]; then
        echo "❌ Error: No VTU files were created"
        deactivate || true
        cd "$ROOT_DIR"
        continue
    fi
    echo "✅ Created $VTU_COUNT VTU files from all data"
    deactivate || true
    
    # ─── STEP 3: Interpolation/Resampling (All Data) ──────────────────────
    echo ""
    echo ">>> Step 3: Interpolating/resampling all data"
    
    WORK_DIR_ABS=$(pwd)
    echo "Calling ParaView with work directory: $WORK_DIR_ABS"
    "$PARAVIEW_PATH" "$SCRIPTS_DIR/interpolate_resample.py" "$WORK_DIR_ABS"
    
    VTS_COUNT=$(find vts/ -maxdepth 1 -name "data-*.vts" 2>/dev/null | wc -l)
    if [[ $VTS_COUNT -lt 2 ]]; then
        echo "❌ Error: Need at least 2 VTS files, found $VTS_COUNT"
        echo "Contents of vts directory:"
        ls -la vts/
        cd "$ROOT_DIR"
        continue
    fi
    echo "✅ Created $VTS_COUNT VTS files from all data"
    
    # ─── STEP 4: Cooling Rate Calculation ─────────────────────────────────
    echo ""
    echo ">>> Step 4: Calculating cooling rate for all data"
    source "$VENV_PATH"
    python "$SCRIPTS_DIR/cooling_rate.py" "$WORK_DIR"
    
    if [[ ! -f "output_results.csv" ]]; then
        echo "⚠️ Warning: output_results.csv not created"
    else
        echo "✅ Cooling rate calculation completed"
    fi
    deactivate || true
    
    # ─── STEP 5: Remapping ─────────────────────────────────────────────────
    echo ""
    echo ">>> Step 5: Remapping"
    source "$VENV_PATH"
    python "$SCRIPTS_DIR/remap.py"
    
    if [[ ! -f "output_results_remapped.csv" ]]; then
        echo "⚠️ Warning: output_results_remapped.csv not created"
    else
        echo "✅ Remapping completed"
    fi
    deactivate || true
    
    # ─── STEP 6: Copy Results ──────────────────────────────────────────────
    echo ""
    echo ">>> Step 6: Copying results"
    
    if [[ -f "output_results_remapped.csv" ]]; then
        cp -v output_results_remapped.csv "$RESULTS_DIR/output_${CASE_NAME}_remapped.csv"
    else
        echo "⚠️ Warning: output_results_remapped.csv not found"
    fi
    
    if [[ -f "output_results.vtk" ]]; then
        cp -v output_results.vtk "$RESULTS_DIR/output_${CASE_NAME}.vtk"
    else
        echo "⚠️ Warning: output_results.vtk not found"
    fi
    
    if [[ -f "output_results.vtp" ]]; then
        cp -v output_results.vtp "$RESULTS_DIR/output_${CASE_NAME}.vtp"
    else
        echo "⚠️ Warning: output_results.vtp not found"
    fi
    
    echo "✅ Results copied to $RESULTS_DIR"
    
    echo ""
    echo "✅ $CASE_NAME processing completed!"
    cd "$ROOT_DIR"
done

echo ""
echo "==============================="
echo "✅ All cases finished!"
echo "==============================="
echo "All steps (0-6) completed for all cases"
echo "Full domain processing with all data"
echo "Outputs collected in $RESULTS_DIR"
echo ""
echo "Job completed at: $(date)"
