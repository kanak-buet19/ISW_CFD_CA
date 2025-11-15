# --------------------------------------------------------------------------
# Keyhole analysis: depth + mouth detection
# --------------------------------------------------------------------------




# Cell 1: Imports and setup
import pyvista as pv
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import griddata
import os
import glob
import csv


def get_substrate_height(case_dir):
    bedplate_file = os.path.join(case_dir, "system", "bedPlateDict")
    with open(bedplate_file, "r") as f:
        for line in f:
            if line.strip().startswith("zmax"):
                value_m = float(line.split()[1].replace(";", ""))  # in meters
                return -value_m * 1000  # convert to mm and flip sign
    raise ValueError("zmax not found in bedPlateDict")





# Cell 2: Directory setup
base_dir = os.getcwd()
vtk_dir = os.path.join(base_dir, "testing/vtk")
plot_dir = os.path.join(base_dir, "testing/plots")
os.makedirs(plot_dir, exist_ok=True)

base_case = base_dir  # point directly to case_000

substrate_height = get_substrate_height(base_case)
print(f"📏 Substrate height set from bedPlateDict: {substrate_height:.3f} mm")


# Cell 3: Load latest VTK file
vtk_files = glob.glob(os.path.join(vtk_dir, "*.vtk"))
if not vtk_files:
    raise FileNotFoundError(f"No .vtk files found in {vtk_dir}")

latest_file = max(vtk_files, key=os.path.getmtime)
print(f"Loading: {os.path.basename(latest_file)}")

# Cell 4: Read mesh and create slice
mesh = pv.read(latest_file)
x_mid = (mesh.bounds[0] + mesh.bounds[1]) / 2
x_coords = mesh.points[:, 0]
x_snap = x_coords[np.abs(x_coords - x_mid).argmin()]

print(f"Midpoint X = {x_mid*1000:.3f} mm, snapped to {x_snap*1000:.3f} mm")

slice_yz = mesh.slice(normal="x", origin=(x_snap, 0, 0))


# Extract coordinates and alpha values (convert to mm)
points = slice_yz.points * 1000  # convert to mm
y, z = points[:, 1], points[:, 2]
alpha = slice_yz.point_data["alpha.metal"]

print(f"Slice at X = {x_mid*1000:.2f} mm")
print(f"Y range: [{y.min():.2f}, {y.max():.2f}] mm")
print(f"Z range: [{z.min():.2f}, {z.max():.2f}] mm")

# Cell 5: Create regular grid for visualization
ny, nz = 300, 300
yi = np.linspace(y.min(), y.max(), ny)
zi = np.linspace(z.min(), z.max(), nz)
ZI, YI = np.meshgrid(zi, yi)  # Note: Z first for correct orientation

# Interpolate alpha values
alpha_grid = griddata((z, y), alpha, (ZI, YI), method='linear')

# --------------------------------------------------------------------------
# Cell 6: Find keyhole depth (positive Y = deeper)


fig_temp, ax_temp = plt.subplots()
CS = ax_temp.contour(ZI, YI, alpha_grid, levels=[0.7])
plt.close(fig_temp)

y_deep = z_deep = depth_um = None
if CS.allsegs[0]:
    contour_points = np.vstack(CS.allsegs[0])
    z_contour, y_contour = contour_points[:, 0], contour_points[:, 1]

    inside_keyhole = y_contour >= substrate_height
    if np.any(inside_keyhole):
        y_deep = y_contour[inside_keyhole].max()
        idx = y_contour[inside_keyhole].argmax()
        z_deep = z_contour[inside_keyhole][idx]
        depth_um = (y_deep - substrate_height) * 1000

        print(f"Keyhole depth: {depth_um:.1f} µm")
        # print(f"Deepest point: Z={z_deep:.2f} mm, Y={y_deep:.2f} mm")

# --------------------------------------------------------------------------
# Cell 7: Find substrate intersections and keyhole mouth
intersection_points = []

if CS.allsegs[0]:
    for seg in CS.allsegs[0]:
        for i in range(len(seg) - 1):
            y1, y2 = seg[i, 1], seg[i+1, 1]
            z1, z2 = seg[i, 0], seg[i+1, 0]

            if (y1 - substrate_height) * (y2 - substrate_height) <= 0:
                t = (substrate_height - y1) / (y2 - y1 + 1e-12)
                z_int = z1 + t * (z2 - z1)
                intersection_points.append((z_int, substrate_height))

if intersection_points:
    intersection_points = sorted(intersection_points, key=lambda p: p[0])
    print("\nIntersection points (Z, Y):")
    for pt in intersection_points:
        print(f"  Z={pt[0]:.3f} mm, Y={pt[1]:.3f} mm")

# Detect mouth edges: only keep the two intersections spanning the deepest point
keyhole_mouth = None
mouth_width_um = None

if len(intersection_points) >= 2 and z_deep is not None:
    z_vals = [p[0] for p in intersection_points]

    # Find the two neighbors around z_deep
    for i in range(len(z_vals) - 1):
        if z_vals[i] <= z_deep <= z_vals[i+1]:
            left_pt = intersection_points[i]
            right_pt = intersection_points[i+1]
            keyhole_mouth = (left_pt, right_pt)
            mouth_width_um = (right_pt[0] - left_pt[0]) * 1000
            break

if keyhole_mouth:
    # print(f"\nKeyhole mouth edges: {keyhole_mouth[0]}, {keyhole_mouth[1]}")
    print(f"Keyhole length: {mouth_width_um:.1f} µm")

#--------------------------------------------------------------------------
# Cell 8: Create final plot
fig, ax = plt.subplots(figsize=(20, 5))

im = ax.imshow(alpha_grid, extent=[zi.min(), zi.max(), yi.min(), yi.max()],
               origin='lower', cmap='coolwarm', aspect='auto', vmin=0, vmax=1)

cbar = plt.colorbar(im, ax=ax, shrink=0.8)
cbar.set_label('α.metal', fontsize=12)

# Substrate line
ax.axhline(substrate_height, color='white', linestyle='--', linewidth=2,
           label=f'Substrate (Y={substrate_height} mm)')

# Contour
# --- Contour only inside mouth region ---
if keyhole_mouth:
    (zL, yL), (zR, yR) = keyhole_mouth

    # Extract α=0.5 contour again
    fig_temp, ax_temp = plt.subplots()
    CS_temp = ax_temp.contour(ZI, YI, alpha_grid, levels=[0.7])
    plt.close(fig_temp)

    if CS_temp.allsegs[0]:
        contour_points = np.vstack(CS_temp.allsegs[0])
        z_contour, y_contour = contour_points[:, 0], contour_points[:, 1]

        # Keep only points between the mouth edges
        inside_mouth = (z_contour >= zL) & (z_contour <= zR)
        z_mouth = z_contour[inside_mouth]
        y_mouth = y_contour[inside_mouth]

        ax.plot(z_mouth, y_mouth, color='black', linewidth=3)

ax.clabel(CS, fmt='α=0.5', fontsize=10, colors='cyan')

# # All intersections
# if intersection_points:
#     for (z_int, y_int) in intersection_points:
#         ax.scatter(z_int, y_int, color='lime', s=80, marker='o', zorder=10)




# Keyhole mouth
if keyhole_mouth:
    (zL, yL), (zR, yR) = keyhole_mouth
    ax.scatter([zL, zR], [yL, yR], color='yellow', s=100, marker='x', zorder=12)
    ax.plot([zL, zR], [yL, yR], color='red', linewidth=3, linestyle='-')
    ax.text((zL+zR)/2, yL-0.01, f"{mouth_width_um:.0f} µm", color='red',
            fontsize=12, weight='bold', ha='center',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='black', alpha=0.6))

# Keyhole depth
if y_deep is not None:
    ax.annotate('', xy=(z_deep, substrate_height), xytext=(z_deep, y_deep),
                arrowprops=dict(arrowstyle='<-', color='yellow', lw=3))
    ax.text(z_deep + 0.1, (y_deep + substrate_height)/2, f'{depth_um:.0f} µm',
            color='yellow', fontsize=12, weight='bold', va='center',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='black', alpha=0.6))
    # ax.scatter(z_deep, y_deep, color='yellow', s=80, marker='x', linewidth=3, zorder=10)

# Formatting
ax.set_xlabel('Z [mm]', fontsize=12)
ax.set_ylabel('Y [mm]', fontsize=12)
ax.set_title(f'Keyhole Analysis - Slice at X={x_mid*1000:.2f} mm', fontsize=14)
ax.grid(True, alpha=0.3)
ax.legend(loc='upper right')
ax.invert_yaxis()

# Save
base_name = os.path.splitext(os.path.basename(latest_file))[0]
out_file = os.path.join(plot_dir, f"{base_name}_keyhole_full.png")
fig.savefig(out_file, dpi=300, bbox_inches='tight', facecolor='white')
plt.close(fig)

print(f"\nAnalysis complete. Plot saved: {out_file}")


import csv

# --------------------------------------------------------------------------
# Cell 9: Save results to CSV inside plots folder
csv_file = os.path.join(plot_dir, "keyhole_results.csv")

# Use the base filename (without extension) instead of only number
file_name = os.path.splitext(os.path.basename(latest_file))[0]

# Ensure values exist
depth_val = depth_um if depth_um is not None else 0.0
width_val = mouth_width_um if mouth_width_um is not None else 0.0

# Write header if file doesn't exist
write_header = not os.path.exists(csv_file)

with open(csv_file, mode='a', newline='') as f:
    writer = csv.writer(f)
    if write_header:
        writer.writerow(["file_name", "depth_um", "width_um"])
    writer.writerow([file_name, f"{depth_val:.2f}", f"{width_val:.2f}"])

print(f"Results saved to {csv_file}")

