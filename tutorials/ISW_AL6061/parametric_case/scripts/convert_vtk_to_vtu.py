import pyvista as pv
import os
import glob
import re
import sys
import numpy as np
from multiprocessing import Pool, cpu_count
from functools import partial
import signal

# --- PATHS ---
in_dir = "VTK"
out_dir = "vtu"
mesh_file = "fine_mesh.vts"

os.makedirs(out_dir, exist_ok=True)

# --- Load fine mesh to get bounds ---
if not os.path.exists(mesh_file):
    print(f"❌ Error: {mesh_file} not found. Cannot determine bounds.")
    sys.exit(1)

print(f"📂 Loading {mesh_file} to determine bounds...")
fine_mesh = pv.read(mesh_file)
target_bounds = fine_mesh.bounds  # (xmin, xmax, ymin, ymax, zmin, zmax)

print(f"✅ Target bounds: X[{target_bounds[0]:.6f}, {target_bounds[1]:.6f}], "
      f"Y[{target_bounds[2]:.6f}, {target_bounds[3]:.6f}], Z[{target_bounds[4]:.6f}, {target_bounds[5]:.6f}]")

# --- Get all vtk files ---
vtk_files = sorted(glob.glob(os.path.join(in_dir, "*.vtk")))

if not vtk_files:
    print(f"⚠️  Warning: No .vtk files found in the '{in_dir}' directory.")
    sys.exit()

total_files = len(vtk_files)
print(f"\n📂 Found {total_files} VTK files")

# --- Use ALL files (no sampling) ---
selected_files = vtk_files
print(f"✅ Converting ALL {total_files} files (no sampling)")

# --- Analyze first VTK file to adjust bounds ---
print(f"\n📂 Analyzing first VTK file to find nearest available data bounds...")
first_mesh = pv.read(vtk_files[0])
vtk_bounds = first_mesh.bounds

print(f"   VTK data bounds: X[{vtk_bounds[0]:.6f}, {vtk_bounds[1]:.6f}], "
      f"Y[{vtk_bounds[2]:.6f}, {vtk_bounds[3]:.6f}], Z[{vtk_bounds[4]:.6f}, {vtk_bounds[5]:.6f}]")

# Snap target bounds to nearest available data
def snap_to_nearest(target_min, target_max, data_min, data_max, tolerance=1e-3):
    """
    Snap target bounds to nearest available data bounds.
    If target is outside data, snap to data boundary.
    If target is inside data, use target.
    Add small buffer for numerical stability.
    """
    # Snap minimum
    if target_min < data_min:
        actual_min = data_min
        snapped_min = True
    elif target_min > data_max:
        actual_min = data_max
        snapped_min = True
    else:
        actual_min = max(target_min, data_min)
        snapped_min = abs(target_min - data_min) > tolerance
    
    # Snap maximum
    if target_max > data_max:
        actual_max = data_max
        snapped_max = True
    elif target_max < data_min:
        actual_max = data_min
        snapped_max = True
    else:
        actual_max = min(target_max, data_max)
        snapped_max = abs(target_max - data_max) > tolerance
    
    return actual_min, actual_max, snapped_min or snapped_max

# Snap each axis
x_min, x_max, x_snapped = snap_to_nearest(target_bounds[0], target_bounds[1], vtk_bounds[0], vtk_bounds[1])
y_min, y_max, y_snapped = snap_to_nearest(target_bounds[2], target_bounds[3], vtk_bounds[2], vtk_bounds[3])
z_min, z_max, z_snapped = snap_to_nearest(target_bounds[4], target_bounds[5], vtk_bounds[4], vtk_bounds[5])

actual_bounds = [x_min, x_max, y_min, y_max, z_min, z_max]

if x_snapped or y_snapped or z_snapped:
    print(f"⚠️  Target bounds adjusted to nearest available data:")
    if x_snapped:
        print(f"   X: [{target_bounds[0]:.6f}, {target_bounds[1]:.6f}] → [{x_min:.6f}, {x_max:.6f}]")
    if y_snapped:
        print(f"   Y: [{target_bounds[2]:.6f}, {target_bounds[3]:.6f}] → [{y_min:.6f}, {y_max:.6f}]")
    if z_snapped:
        print(f"   Z: [{target_bounds[4]:.6f}, {target_bounds[5]:.6f}] → [{z_min:.6f}, {z_max:.6f}]")
else:
    print(f"✅ Target bounds are within VTK data bounds - using exact bounds")

print(f"📦 Final extraction bounds: X[{actual_bounds[0]:.6f}, {actual_bounds[1]:.6f}], "
      f"Y[{actual_bounds[2]:.6f}, {actual_bounds[3]:.6f}], Z[{actual_bounds[4]:.6f}, {actual_bounds[5]:.6f}]")

# --- Timeout handler ---
def timeout_handler(signum, frame):
    raise TimeoutError("Processing timeout")

# --- Worker function for parallel processing ---
def convert_file(in_file, actual_bounds, out_dir, timeout=300):
    """Process a single VTK file with timeout"""
    vtk_name = os.path.basename(in_file)
    
    # Extract number from filename
    match = re.search(r"([0-9.]+)(?=\.vtk$)", vtk_name)
    if not match:
        return {"status": "skipped", "reason": "no number found", "file": vtk_name}
    
    number = match.group(1)
    out_file = os.path.join(out_dir, f"data-{number}.vtu")
    
    # Skip if already exists
    if os.path.exists(out_file):
        return {"status": "skipped", "reason": "already exists", "file": vtk_name}
    
    try:
        # Set timeout alarm
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout)
        
        # Read original mesh
        mesh = pv.read(in_file)
        
        # Clip to bounds
        clipped = mesh.clip_box(actual_bounds, invert=False)
        
        # Check if clipped mesh has data
        if clipped.n_points == 0:
            signal.alarm(0)  # Cancel alarm
            return {"status": "skipped", "reason": "no data in bounds", "file": vtk_name}
        
        # Create reduced mesh
        new_mesh = clipped.copy()
        new_mesh.point_data.clear()
        new_mesh.cell_data.clear()
        
        # Add required arrays
        warnings = []
        if "T" in clipped.point_data:
            new_mesh.point_data["temperature"] = clipped.point_data["T"]
        else:
            warnings.append("'T' field not found")
            
        if "alpha.metal" in clipped.point_data:
            new_mesh.point_data["metal_in625_vof"] = clipped.point_data["alpha.metal"]
        else:
            warnings.append("'alpha.metal' field not found")
        
        # Save
        new_mesh.save(out_file)
        
        signal.alarm(0)  # Cancel alarm
        return {"status": "converted", "file": vtk_name, "warnings": warnings}
        
    except TimeoutError:
        signal.alarm(0)
        return {"status": "error", "file": vtk_name, "error": "Processing timeout (>5min)"}
    except Exception as e:
        signal.alarm(0)
        return {"status": "error", "file": vtk_name, "error": str(e)}

# --- Convert files in parallel ---
total = len(selected_files)

# CRITICAL FIX: Limit cores to prevent memory exhaustion
# Rule of thumb: 1 core per 2GB available RAM for VTK processing
num_cores = min(cpu_count(), 16)  # Cap at 16 cores
print(f"\n🔄 Converting {total} VTK files using {num_cores} cores (limited for stability)...\n")

# Create worker function with bound parameters
worker = partial(convert_file, actual_bounds=actual_bounds, out_dir=out_dir)

# Use multiprocessing pool with timeout
converted = 0
skipped = 0
errors = 0

try:
    with Pool(processes=num_cores) as pool:
        # Use chunksize=1 to process files one at a time per worker
        results = pool.imap_unordered(worker, selected_files, chunksize=1)
        
        for i, result in enumerate(results, start=1):
            if result["status"] == "converted":
                converted += 1
            elif result["status"] == "skipped":
                skipped += 1
                if result["reason"] != "already exists":
                    print(f"\n⚠️  Skipped {result['file']} ({result['reason']})")
            elif result["status"] == "error":
                errors += 1
                print(f"\n❌ Error {result['file']}: {result['error']}")
            
            if result.get("warnings"):
                for warn in result["warnings"]:
                    print(f"   ⚠️  {result['file']}: {warn}")
            
            # Progress bar
            bar_len = 40
            filled_len = int(bar_len * i // total)
            bar = "█" * filled_len + "-" * (bar_len - filled_len)
            percent = (i / total) * 100
            sys.stdout.write(f"\r[{bar}] {i}/{total} ({percent:5.1f}%) | ✓{converted} ⚠{skipped} ✗{errors}")
            sys.stdout.flush()

except KeyboardInterrupt:
    print("\n\n⚠️  Interrupted by user. Partial progress saved.")
    pool.terminate()
    pool.join()

print(f"\n\n✅ Parallel VTK to VTU Conversion complete!")
print(f"   Converted: {converted}/{total} files")
print(f"   Skipped: {skipped}")
print(f"   Errors: {errors}")
print(f"   Cores used: {num_cores}")
print(f"💾 Extracted only the region within fine_mesh bounds.")