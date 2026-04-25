#!/bin/bash

#SBATCH --job-name=case_002
#SBATCH --time=30:00:00
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=64
#SBATCH --account=PNS0496
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

# Source tutorial run functions
. $WM_PROJECT_DIR/bin/tools/RunFunctions

echo "Job started at: $(date)"
echo "Case: case_002"



# Setup case
cp -r initial 0
runApplication blockMesh
runApplication setSolidFraction
runApplication transformPoints "rotate=((0 1 0) (0 0 1))"
decomposePar

# Start monitoring in background
dos2unix recon_test
./recon_test &
MONITOR_PID=$!

# Run simulation
mpirun -np $SLURM_NTASKS laserbeamFoam_ISW -parallel

# Final reconstruction
reconstructPar
foamToVTK -useTimeName

# Stop monitoring
kill $MONITOR_PID 2>/dev/null || true

echo "Job completed at: $(date)"
