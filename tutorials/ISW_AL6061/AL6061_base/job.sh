#!/bin/bash

#SBATCH --job-name=AL6061
#SBATCH --time=30:00:00
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=64
#SBATCH --account= '' #add acc name 
#SBATCH --output=output_%j.out
#SBATCH --error=output_%j.err

cd $SLURM_SUBMIT_DIR

# Clean MPI settings
module purge
unset OMPI_MCA_*
unset MPI_HOME

# Setup OpenMPI and OpenFOAM
export PATH="$HOME/openmpi-5.0.7-install/bin:$PATH"
export LD_LIBRARY_PATH="$HOME/openmpi-5.0.7-install/lib${LD_LIBRARY_PATH:+:}$LD_LIBRARY_PATH"
export WM_PROJECT_DIR=$HOME/OpenFOAM-10
source "$WM_PROJECT_DIR/etc/bashrc"
export FOAM_SIGFPE=0

# Verify it's picking your local mpirun
which mpirun
mpirun --version

# Source tutorial run functions
. $WM_PROJECT_DIR/bin/tools/RunFunctions

echo "Job started at: $(date)"
echo "Running on node: $(hostname)"
echo "Job ID: $SLURM_JOB_ID"
echo "Number of tasks: $SLURM_NTASKS"

echo "Copying 'initial' to 0"
cp -r initial 0

echo "Running blockMesh"
runApplication blockMesh

echo "Running setSolidFraction"
runApplication setSolidFraction

echo "Running transformPoints with rotation"
runApplication transformPoints "rotate=((0 1 0) (0 0 1))"

echo "Decomposing domain for parallel run"
decomposePar


dos2unix recon_test
# Run solver in foreground
echo "Starting parallel laserbeamFoam simulation with $SLURM_NTASKS cores"
mpirun -np $SLURM_NTASKS laserbeamFoam -parallel

# -------------------------
# Standard reconstruction steps
# -------------------------
echo "Reconstructing fields from parallel run"
reconstructPar

echo "Converting to VTK format"
foamToVTK -useTimeName

echo "Job completed at: $(date)"
