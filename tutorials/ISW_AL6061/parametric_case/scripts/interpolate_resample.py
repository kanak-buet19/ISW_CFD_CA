#!/usr/bin/env pvpython

import glob
import os
import sys
from paraview.simple import *
from paraview.servermanager import Fetch

# --- Progress Bar Function ---
def print_progress_bar(iteration, total, prefix='Progress', suffix='Complete', length=50, fill='█'):
    """
    Call in a loop to create a terminal progress bar.
    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        length      - Optional  : character length of bar (Int)
        fill        - Optional  : bar fill character (Str)
    """
    percent = ("{0:.1f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    # The \r at the beginning moves the cursor to the start of the line
    sys.stdout.write(f'\r{prefix} |{bar}| {percent}% {suffix}')
    # Flush the buffer to make it visible immediately
    sys.stdout.flush()


# --- Directories ---
if len(sys.argv) > 1:
    work_dir = sys.argv[1]
    print(f"Using work directory from argument: {work_dir}")
else:
    work_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"Using script directory: {work_dir}")

input_dir = os.path.join(work_dir, "vtu")
mesh_file = os.path.join(work_dir, "fine_mesh.vts")
output_dir = os.path.join(work_dir, "vts")
os.makedirs(output_dir, exist_ok=True)

# --- Collect all VTU files ---
vtu_files = sorted(glob.glob(os.path.join(input_dir, "*.vtu")))
num_files = len(vtu_files)
print(f"Found {num_files} VTU files in {input_dir}")

if not vtu_files:
    print("⚠️ No VTU files found, exiting.")
    sys.exit(1)

if not os.path.exists(mesh_file):
    print(f"⚠️ Mesh file not found: {mesh_file}, exiting.")
    sys.exit(1)

# --- Load structured mesh once ---
print(f"Loading mesh: {mesh_file}")
fine_mesh = XMLStructuredGridReader(FileName=[mesh_file])
fine_mesh.TimeArray = 'None'

# --- Process each file ---
print("Resampling VTU to VTS...")
# Initialize the progress bar
print_progress_bar(0, num_files, prefix='Progress:', suffix='Complete', length=50)

for i, vtu_file in enumerate(vtu_files):
    base = os.path.splitext(os.path.basename(vtu_file))[0]
    output_file = os.path.join(output_dir, f"{base}.vts")

    # Load VTU
    data_vtu = XMLUnstructuredGridReader(FileName=[vtu_file])

    # Get available point data arrays
    vtk_src = Fetch(data_vtu)
    src_pd = vtk_src.GetPointData()
    src_arrays = [src_pd.GetArrayName(j) for j in range(src_pd.GetNumberOfArrays())]

    if not src_arrays:
        # Print warnings on a new line so they don't mess up the progress bar
        print(f"\n⚠️ No point data arrays found in {os.path.basename(vtu_file)}, skipping.")
        continue

    # Resample onto the structured mesh
    resampled = ResampleWithDataset(
        SourceDataArrays=data_vtu,
        DestinationMesh=fine_mesh
    )

    # Save the resampled data
    SaveData(output_file, proxy=resampled,
             PointDataArrays=src_arrays,
             DataMode="Binary", CompressorType="ZLib")
             
    # Update the progress bar
    print_progress_bar(i + 1, num_files, prefix='Progress:', suffix='Complete', length=50)

    Delete(resampled)
    Delete(data_vtu)

Delete(fine_mesh)
# Print a newline character at the end to move off the progress bar line
print()
print(f"\n✅ Processing complete! Created {num_files} VTS files in {output_dir}")

