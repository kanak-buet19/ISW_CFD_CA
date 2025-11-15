#!/usr/bin/env python3
import os
import glob
import numpy as np
import vtk

# ------------------------------
# Function to create structured mesh
# ------------------------------
def create_structured_mesh_vts(x_range, y_range, z_range, mesh_size, output_file):
    x_min, x_max = x_range
    y_min, y_max = y_range
    z_min, z_max = z_range

    nx = int(abs(x_max - x_min) / mesh_size) + 1
    ny = int(abs(y_max - y_min) / mesh_size) + 1
    nz = int(abs(z_max - z_min) / mesh_size) + 1

    x = np.linspace(x_min, x_max, nx)
    y = np.linspace(y_min, y_max, ny)
    z = np.linspace(z_min, z_max, nz)

    grid = vtk.vtkStructuredGrid()
    grid.SetDimensions(nx, ny, nz)

    pts = vtk.vtkPoints()
    for k in range(nz):
        for j in range(ny):
            for i in range(nx):
                pts.InsertNextPoint(x[i], y[j], z[k])
    grid.SetPoints(pts)

    writer = vtk.vtkXMLStructuredGridWriter()
    writer.SetFileName(output_file)
    writer.SetInputData(grid)
    writer.SetDataModeToBinary()
    writer.SetCompressorTypeToZLib()
    writer.Write()

    print(f"Structured grid saved: {output_file}, total points: {grid.GetNumberOfPoints()}")
    return grid

# ------------------------------
# Detect bounds from first VTK
# ------------------------------
def get_bounds_from_first_vtk(vtk_folder):
    vtk_files = sorted(glob.glob(os.path.join(vtk_folder, "*.vtk")))
    if not vtk_files:
        raise FileNotFoundError(f"No VTK files found in {vtk_folder}")

    reader = vtk.vtkGenericDataObjectReader()
    reader.SetFileName(vtk_files[0])
    reader.Update()
    mesh = reader.GetOutput()

    bounds = mesh.GetBounds()
    x_range = (bounds[0], bounds[1])
    y_range = (bounds[2], bounds[3])
    z_range = (bounds[4], bounds[5])

    print(f"Detected bounds from {os.path.basename(vtk_files[0])}:")
    print(f"  X: {x_range}, Y: {y_range}, Z: {z_range}")
    return x_range, y_range, z_range

# ------------------------------
# Main
# ------------------------------
if __name__ == "__main__":
    vtk_folder = os.path.join(os.getcwd(), "VTK")
    if not os.path.exists(vtk_folder):
        raise FileNotFoundError(f"{vtk_folder} does not exist!")

    # Automatically detect bounds from first VTK
    X_RANGE, Y_RANGE, Z_RANGE = get_bounds_from_first_vtk(vtk_folder)

    # Convert to micrometers for display
    x_min_um, x_max_um = np.array(X_RANGE) * 1e6
    y_min_um, y_max_um = np.array(Y_RANGE) * 1e6
    z_min_um, z_max_um = np.array(Z_RANGE) * 1e6

    print("\n==========================")
    print(" Mesh Bounds (in µm)")
    print("==========================")
    print(f"X: {x_min_um:.3f} – {x_max_um:.3f}")
    print(f"Y: {y_min_um:.3f} – {y_max_um:.3f}")
    print(f"Z: {z_min_um:.3f} – {z_max_um:.3f}")
    print("\n✅ Using FULL domain bounds (no cropping)")

    # Mesh size
    MESH_SIZE = 2.5e-6  # meters
    STRUCTURED_OUTPUT_FILE = "fine_mesh.vts"

    # Generate structured mesh over full domain
    print("\nGenerating fine mesh over full domain...")
    create_structured_mesh_vts(X_RANGE, Y_RANGE, Z_RANGE, MESH_SIZE, STRUCTURED_OUTPUT_FILE)