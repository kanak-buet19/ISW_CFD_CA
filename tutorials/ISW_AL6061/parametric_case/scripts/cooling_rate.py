#!/usr/bin/env python3

import os
import re
import gc
import numpy as np
import pandas as pd
import vtk
from vtk.util.numpy_support import vtk_to_numpy
from tqdm import tqdm

# ─── CONFIG ────────────────────────────────────────────────────────────────
import sys

# ─── CONFIG ────────────────────────────────────────────────────────────────
T_liquidus     = 873
T_solid        = T_liquidus - 100  # 773 K for solidification threshold
VOF_THRESH     = 0.5

# Work directory = passed as arg, or current dir
if len(sys.argv) > 1:
    WORK_DIR = sys.argv[1]
else:
    WORK_DIR = os.getcwd()

# Input VTS folder
VTS_DIR        = os.path.join(WORK_DIR, "vts")

# Output CSV
OUTPUT_CSV     = os.path.join(WORK_DIR, "output_results.csv")

PATTERN = re.compile(r"data-(\d+(?:\.\d+)?)\.vts$")

n              = 1
timestep_size  = 1
# ────────────────────────────────────────────────────────────────────────────

def get_timestep(filename):
    return float(PATTERN.match(filename).group(1))


def load_temperature_from_file(filepath, mask):
    reader = vtk.vtkXMLStructuredGridReader()
    reader.SetFileName(filepath)
    reader.Update()
    grid = reader.GetOutput()
    temp_full = vtk_to_numpy(grid.GetPointData().GetArray("temperature"))
    temp_masked = temp_full[mask].astype(np.float32)
    del temp_full, grid
    reader = None
    gc.collect()
    return temp_masked

# 1) Gather & sort sample files
all_files = [f for f in os.listdir(VTS_DIR) if PATTERN.match(f)]
all_files.sort(key=get_timestep)
sampled = all_files[::n]
M = len(sampled)
if M < 2:
    raise RuntimeError("Need at least two sampled files")

# 2) Read LAST file to get coords and final VOF (used for filtering)
reader = vtk.vtkXMLStructuredGridReader()
last_path = os.path.join(VTS_DIR, sampled[-1])
reader.SetFileName(last_path)
reader.Update()
grid = reader.GetOutput()
pts_full = vtk_to_numpy(grid.GetPoints().GetData())
vof_full = vtk_to_numpy(grid.GetPointData().GetArray("metal_in625_vof"))
mask = vof_full > VOF_THRESH
pts = pts_full[mask]
N_total = pts_full.shape[0]
N = pts.shape[0]
del pts_full, vof_full, grid
reader = None
gc.collect()

print(f"Processing {N} points (VOF > {VOF_THRESH}) from {M} files...")
print(f"Total domain points: {N_total}, Filtered points: {N}")

# 3) Build time vector
time_indices = np.array([get_timestep(f) for f in sampled], dtype=np.float64)
times = time_indices * timestep_size
file_paths = [os.path.join(VTS_DIR, fname) for fname in sampled]

# 4) Preload all temperature data into memory (only for masked points)
print("\n🔄 Preloading all temperature data into memory...")
temp_all = np.empty((M, N), dtype=np.float32)
for j, filepath in enumerate(tqdm(file_paths, desc="  Preload files", unit="file")):
    temp_all[j] = load_temperature_from_file(filepath, mask)
print(f"✅ Loaded full temperature matrix: {temp_all.shape} → {temp_all.nbytes / 1024**3:.2f} GB")

# 5) Vectorized melt detection (when T > T_liquidus)
above_liquidus = temp_all > T_liquidus
first_above = np.argmax(above_liquidus, axis=0)
never_melted = ~np.any(above_liquidus, axis=0)
first_above[never_melted] = -1

# 6) Solidification detection (when T drops below T_solid = T_liquidus - 100 K)
print("\n🔄 Detecting solidification events...")
solid_idx = np.full(N, -1, dtype=np.int32)
below_solid = temp_all < T_solid  # Temperature below 773 K

for i in tqdm(np.where(~never_melted)[0], desc="  Solidification"):
    melt_frame = first_above[i]
    # Look for first time after melting when T drops below T_solid
    solid_range = below_solid[melt_frame+1:, i]
    if np.any(solid_range):
        solid_idx[i] = melt_frame + 1 + np.argmax(solid_range)

# 7) Statistics
never_melt = first_above == -1
num_never_melt = np.count_nonzero(never_melt)
num_melted = N - num_never_melt
valid = (first_above >= 0) & (solid_idx > first_above)
num_solidified = np.count_nonzero(valid)
num_melt_no_solidify = num_melted - num_solidified

print("\n=== Summary (VOF Filtered) ===")
print(f" Total points in domain:         {N_total}")
print(f" Points with VOF > {VOF_THRESH}:        {N}")
print(f" Points that never melted:       {num_never_melt}")
print(f" Points that melted (T > {T_liquidus} K): {num_melted}")
print(f"   of which solidified (T < {T_solid} K): {num_solidified}")
print(f"   of which did not solidify:    {num_melt_no_solidify}")
print("================================\n")

# 8) Precise time interpolation for valid solidification points
# FIXED VERSION - handles edge cases properly

valid_indices = np.nonzero(valid)[0]
fa = first_above[valid]
sa = solid_idx[valid]

# === MELTING TIME INTERPOLATION ===
# Skip points where melting happens at frame 0 (can't interpolate backwards)
can_interp_melt = fa > 0

# Get temperatures for interpolation
T0m = np.where(can_interp_melt, temp_all[fa - 1, valid_indices], np.nan)
T1m = temp_all[fa, valid_indices]

# Get times for interpolation
t0m = np.where(can_interp_melt, times[fa - 1], np.nan)
t1m = times[fa]

# Calculate interpolation fraction, avoiding division by zero
dT_melt = T1m - T0m
# If temperature doesn't change, use the later time
m_frac = np.where(
    np.abs(dT_melt) > 1e-6,  # Non-zero temperature change
    (T_liquidus - T0m) / dT_melt,
    1.0  # Default to t1m if no temperature change
)
# Clamp fraction to [0, 1] to avoid extrapolation
m_frac = np.clip(m_frac, 0.0, 1.0)

# Calculate melting time
tm = np.where(
    can_interp_melt,
    t0m + m_frac * (t1m - t0m),
    t1m  # If can't interpolate, use the frame time directly
)

# === SOLIDIFICATION TIME INTERPOLATION ===
# Skip points where solidification happens at frame 0 (can't interpolate backwards)
can_interp_solid = sa > 0

# Get temperatures for interpolation
T0s = np.where(can_interp_solid, temp_all[sa - 1, valid_indices], np.nan)
T1s = temp_all[sa, valid_indices]

# Get times for interpolation
t0s = np.where(can_interp_solid, times[sa - 1], np.nan)
t1s = times[sa]

# Calculate interpolation fraction, avoiding division by zero
dT_solid = T1s - T0s
s_frac = np.where(
    np.abs(dT_solid) > 1e-6,  # Non-zero temperature change
    (T_solid - T0s) / dT_solid,
    1.0  # Default to t1s if no temperature change
)
# Clamp fraction to [0, 1] to avoid extrapolation
s_frac = np.clip(s_frac, 0.0, 1.0)

# Calculate solidification time
ts = np.where(
    can_interp_solid,
    t0s + s_frac * (t1s - t0s),
    t1s  # If can't interpolate, use the frame time directly
)

# === SANITY CHECK ===
# Ensure tm < ts (melting before solidification)
valid_times = tm < ts
num_invalid = np.sum(~valid_times)

if num_invalid > 0:
    print(f"\n⚠️  WARNING: Found {num_invalid} points where tm >= ts")
    print("These will be excluded from the output.")
    
    # Filter to only physically valid points
    valid_indices = valid_indices[valid_times]
    tm = tm[valid_times]
    ts = ts[valid_times]

# Calculate cooling rate: ΔT / Δt = (873 - 773) / (ts - tm)
delta_T = T_liquidus - T_solid  # 100 K
delta_t = ts - tm

# Avoid division by zero for cooling rate
cooling_rate = np.where(
    delta_t > 1e-9,
    delta_T / delta_t,
    np.nan
)

# 9) Assemble and write result
df = pd.DataFrame({
    'x':  pts[valid_indices, 0],
    'y':  pts[valid_indices, 1],
    'z':  pts[valid_indices, 2],
    'tm': tm,
    'ts': ts,
    'cr': cooling_rate,
})

# Remove any rows with NaN values
df = df.dropna()

df.to_csv(OUTPUT_CSV, index=False)
print(f"✅ Wrote {len(df)} valid rows (melt+solidify) to {OUTPUT_CSV}")
print(f"\nCooling rate calculation: ΔT = {delta_T} K, between {T_liquidus} K and {T_solid} K")

# Print statistics
if len(df) > 0:
    print(f"\nCooling rate statistics:")
    print(f"  Min:  {df['cr'].min():.2e} K/s")
    print(f"  Max:  {df['cr'].max():.2e} K/s")
    print(f"  Mean: {df['cr'].mean():.2e} K/s")
    print(f"  Median: {df['cr'].median():.2e} K/s")
    print(f"\nTime range:")
    print(f"  Melting time (tm):        {df['tm'].min():.6f} to {df['tm'].max():.6f}")
    print(f"  Solidification time (ts): {df['ts'].min():.6f} to {df['ts'].max():.6f}")