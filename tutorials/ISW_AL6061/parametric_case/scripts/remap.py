import pandas as pd

# Load CSV
data1 = pd.read_csv("output_results.csv")

# Remap columns: x→y, y→z, z→x
data1 = data1.rename(columns={"x": "y_tmp", "y": "z", "z": "x"})
data1 = data1.rename(columns={"y_tmp": "y"})

# Reorder columns explicitly
data1 = data1[["x", "y", "z", "tm", "ts", "cr"]]

# Save to new CSV
data1.to_csv("output_results_remapped.csv", index=False)

print("Saved remapped file as output_results_remapped.csv")


import pandas as pd
import pyvista as pv

# Load the remapped CSV
data = pd.read_csv("output_results_remapped.csv")

# Create a point cloud (x,y,z as coordinates)
points = data[["x", "y", "z"]].values

# Make a PolyData object
cloud = pv.PolyData(points)

# Attach other columns as point data
for col in ["tm", "ts", "cr"]:
    cloud.point_data[col] = data[col].values

cloud.save("output_results.vtp")   # XML PolyData, great for ParaView
cloud.save("output_results.vtk")   # Legacy PolyData

print("Saved as output_results.vtk and output_results.vtu")
