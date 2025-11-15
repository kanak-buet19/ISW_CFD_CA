


import pyvista as pv
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import griddata
import os, glob, sys



substrate_height = -0.3  # mm reference height

# --- Directories ---
base_dir = os.getcwd()
vtk_dir = os.path.join(base_dir, "VTK")
vtk_files = sorted(glob.glob(os.path.join(vtk_dir, "*.vtk")))

if not vtk_files:
    raise FileNotFoundError(f"No .vtk files found in {vtk_dir}")

times, depths = [], []

# --- Loop with progress bar ---
n_files = len(vtk_files)
for idx, vtk_file in enumerate(vtk_files, 1):
    base_name = os.path.splitext(os.path.basename(vtk_file))[0]

    # --- Extract time value from filename (after last underscore) ---
    time_str = base_name.split("_")[-1]
    try:
        time_val = float(time_str) * 1e6  # convert seconds → microseconds
    except ValueError:
        continue  # skip non-data files like back.vtk, topWall.vtk, etc.

    # --- Load mesh and slice ---
    mesh = pv.read(vtk_file)
    x_mid = (mesh.bounds[0] + mesh.bounds[1]) / 2
    slice_yz = mesh.slice(normal="x", origin=(x_mid, 0, 0))

    points = slice_yz.points * 1000  # convert to mm
    y, z = points[:, 1], points[:, 2]
    alpha = slice_yz.point_data["alpha.metal"]

    # --- Regular grid ---
    ny, nz = 300, 300
    yi = np.linspace(y.min(), y.max(), ny)
    zi = np.linspace(z.min(), z.max(), nz)
    ZI, YI = np.meshgrid(zi, yi)
    alpha_grid = griddata((z, y), alpha, (ZI, YI), method="linear")

    # --- Contour (alpha = 0.7) ---
    fig_temp, ax_temp = plt.subplots()
    CS = ax_temp.contour(ZI, YI, alpha_grid, levels=[0.7])
    plt.close(fig_temp)

    depth_um = 0.0
    if CS.allsegs[0]:
        contour_points = np.vstack(CS.allsegs[0])
        z_contour, y_contour = contour_points[:, 0], contour_points[:, 1]

        inside_keyhole = y_contour >= substrate_height
        if np.any(inside_keyhole):
            y_deep = y_contour[inside_keyhole].max()
            depth_um = (y_deep - substrate_height) * 1000  # µm

    times.append(time_val)
    depths.append(depth_um)

    # --- Progress bar ---
    progress = int(50 * idx / n_files)
    bar = "█" * progress + "-" * (50 - progress)
    sys.stdout.write(f"\r[{bar}] {idx}/{n_files} files processed")
    sys.stdout.flush()

print("\nProcessing complete.")

# --- Sort by time ---
times, depths = zip(*sorted(zip(times, depths)))

# --- Truncate to match experimental range (0–1000 µs) ---
max_time_exp = 1000  # µs
times, depths = zip(*[(t, d) for t, d in zip(times, depths) if t <= max_time_exp])

# --- Load experimental data ---
# Format: 2 columns → time [µs], depth [µm]
exp_file = os.path.join(base_dir, "exp_data.csv")
exp_time, exp_depth = np.loadtxt(exp_file, delimiter=",", unpack=True, skiprows=1)


# --- Plot both curves ---
plt.figure(figsize=(8,5))
plt.plot(times, depths, marker="o", label="Simulation")
plt.plot(exp_time, exp_depth, "r--o", label="Experiment")
plt.xlabel("Time [µs]", fontsize=12)
plt.ylabel("Keyhole Depth [µm]", fontsize=12)
plt.title("Keyhole Depth vs Time (Simulation vs Experiment)", fontsize=14)
plt.grid(True, alpha=0.4)
plt.legend()
plt.tight_layout()

# Save instead of just showing
out_file = os.path.join(base_dir, "time_vs_keyhole.png")
plt.savefig(out_file, dpi=300, bbox_inches="tight", facecolor="white")

print(f"Plot saved: {out_file}")
