# -----------------------------
# SETTINGS
# -----------------------------
VTK_PATH = "/home/kanak/ISW_CFD_CA/tutorials/Connor_316L_base/VTK/Connor_316L_base_0.0009003816413.vtk"
OUTPUT_DIR = "/home/kanak/ISW_CFD_CA/meltpool_VTK_testing"
FIGURE_PDF = "meltpool_yz_xy_summary.pdf"
XY_SUMMARY_CSV = "xy_summary.csv"

T_LIQ = 1563.0
SURFACE_Y_UM = 1200.0   # substrate surface location in um
NX, NZ, NY = 180, 180, 180
INTERP_METHOD = "linear"   # use "nearest" if needed

import numpy as np
import pandas as pd
import pyvista as pv
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from pathlib import Path
from scipy.interpolate import griddata

output_dir = Path(OUTPUT_DIR)
figure_pdf = output_dir / FIGURE_PDF
xy_summary_csv = output_dir / XY_SUMMARY_CSV

# -----------------------------
# READ DATA
# -----------------------------
mesh = pv.read(VTK_PATH)
centers = mesh.cell_centers()
xyz = centers.points

df = pd.DataFrame({
    "x": xyz[:, 0],
    "y": xyz[:, 1],
    "z": xyz[:, 2],
    "alpha.metal": mesh.cell_data["alpha.metal"],
    "T": mesh.cell_data["T"],
})

# -----------------------------
# CONVERT TO MICRONS
# z = scan track
# y = depth
# x = width
# -----------------------------
df["x_um"] = df["x"] * 1e6
df["y_um"] = np.abs(df["y"]) * 1e6
df["z_um"] = df["z"] * 1e6

# -----------------------------
# TAKE YZ SLICE AT MID-X
# -----------------------------
x_mid = 0.5 * (df["x"].min() + df["x"].max())
x_plane = df.loc[(df["x"] - x_mid).abs().idxmin(), "x"]
yz = df[np.isclose(df["x"], x_plane)].copy()

print(f"x_plane = {x_plane:.12e} m = {x_plane * 1e6:.3f} um")
print("slice shape:", yz.shape)
print("alpha range:", yz["alpha.metal"].min(), yz["alpha.metal"].max())
print("T range:", yz["T"].min(), yz["T"].max())

def interpolate_slice(slice_df, x_col, y_col, nx, ny):
    points = slice_df[[x_col, y_col]].to_numpy()
    xg = np.linspace(slice_df[x_col].min(), slice_df[x_col].max(), nx)
    yg = np.linspace(slice_df[y_col].min(), slice_df[y_col].max(), ny)
    Xg, Yg = np.meshgrid(xg, yg)

    alpha_vals = slice_df["alpha.metal"].to_numpy()
    T_vals = slice_df["T"].to_numpy()

    Ag = griddata(points, alpha_vals, (Xg, Yg), method=INTERP_METHOD)
    Tg = griddata(points, T_vals, (Xg, Yg), method=INTERP_METHOD)

    Ag_near = griddata(points, alpha_vals, (Xg, Yg), method="nearest")
    Tg_near = griddata(points, T_vals, (Xg, Yg), method="nearest")

    Ag[np.isnan(Ag)] = Ag_near[np.isnan(Ag)]
    Tg[np.isnan(Tg)] = Tg_near[np.isnan(Tg)]

    Tg_liq_region = np.ma.masked_where((Ag <= 0.5) | (Ag >= 1.0), Tg)
    return xg, yg, Xg, Yg, Ag, Tg_liq_region


def find_max_depth(contour_set, SURFACE_Y_UM, contour_name):
    segments = [seg for seg in contour_set.allsegs[0] if len(seg) > 0]

    if len(segments) == 0:
        print(f"No {contour_name} contour found.")
        return None

    pts = np.vstack(segments)
    x_contour = pts[:, 0]
    y_contour = pts[:, 1]

    # below surface means y is LESS than 1200 in your plotted coordinate
    mask = y_contour <= SURFACE_Y_UM

    if not np.any(mask):
        print(f"No {contour_name} contour found below y = {SURFACE_Y_UM:.1f} um")
        return None

    x_below = x_contour[mask]
    y_below = y_contour[mask]

    # deepest point = minimum y
    i = np.argmin(y_below)
    x_at_max_depth = x_below[i]
    y_at_max_depth = y_below[i]
    max_depth_um = SURFACE_Y_UM - y_at_max_depth

    return x_at_max_depth, y_at_max_depth, max_depth_um


def find_surface_width(contour_set, SURFACE_Y_UM, contour_name):
    intersections = []

    for segment in contour_set.allsegs[0]:
        if len(segment) < 2:
            continue

        x_vals = segment[:, 0]
        y_vals = segment[:, 1]

        for i in range(len(segment) - 1):
            x1, y1 = x_vals[i], y_vals[i]
            x2, y2 = x_vals[i + 1], y_vals[i + 1]

            if y1 == y2:
                continue

            crosses_surface = (y1 - SURFACE_Y_UM) * (y2 - SURFACE_Y_UM) <= 0
            if not crosses_surface:
                continue

            t = (SURFACE_Y_UM - y1) / (y2 - y1)
            if 0.0 <= t <= 1.0:
                intersections.append(x1 + t * (x2 - x1))

    if len(intersections) < 2:
        print(f"Less than 2 {contour_name} intersections with y = {SURFACE_Y_UM:.1f} um")
        return None

    intersections = np.array(sorted(intersections))
    unique_intersections = []
    for x_int in intersections:
        if len(unique_intersections) == 0 or abs(x_int - unique_intersections[-1]) > 1e-6:
            unique_intersections.append(x_int)

    x_left = min(unique_intersections)
    x_right = max(unique_intersections)
    width_um = x_right - x_left
    return x_left, x_right, width_um


def mark_surface_width(ax, width_result, SURFACE_Y_UM, color):
    if width_result is None:
        return

    x_left, x_right, _ = width_result
    ax.plot(
        [x_left, x_right],
        [SURFACE_Y_UM, SURFACE_Y_UM],
        color=color,
        linewidth=3.0,
        solid_capstyle="round",
        zorder=23
    )
    ax.scatter(
        [x_left, x_right],
        [SURFACE_Y_UM, SURFACE_Y_UM],
        color=color,
        edgecolor="black",
        s=45,
        zorder=24
    )


def depth_value(depth_result):
    if depth_result is None:
        return np.nan
    return depth_result[2]


def depth_x_position(depth_result):
    if depth_result is None:
        return np.nan
    return depth_result[0]


def depth_y_position(depth_result):
    if depth_result is None:
        return np.nan
    return depth_result[1]


def width_value(width_result):
    if width_result is None:
        return np.nan
    return width_result[2]


def width_left_position(width_result):
    if width_result is None:
        return np.nan
    return width_result[0]


def width_right_position(width_result):
    if width_result is None:
        return np.nan
    return width_result[1]


def mark_combined_depths(
    ax,
    keyhole_depth,
    meltpool_depth,
    SURFACE_Y_UM,
    x_grid,
    label_x_name,
    extra_text_lines=None,
    show_contour_positions=True,
):
    available_depths = [depth for depth in [keyhole_depth, meltpool_depth] if depth is not None]
    if len(available_depths) == 0:
        return

    x_min = x_grid.min()
    x_max = x_grid.max()
    x_span = x_max - x_min
    y_deepest = min(depth[1] for depth in available_depths)
    x_scale = x_max - 0.08 * x_span
    tick_width = 0.025 * x_span

    ax.annotate(
        "",
        xy=(x_scale, y_deepest),
        xytext=(x_scale, SURFACE_Y_UM),
        arrowprops=dict(
            arrowstyle="<->",
            color="black",
            linewidth=2.5,
            shrinkA=0,
            shrinkB=0,
        ),
        zorder=20
    )

    text_lines = []
    if keyhole_depth is not None:
        x_keyhole, y_keyhole, keyhole_depth_um = keyhole_depth
        ax.hlines(
            y_keyhole,
            min(x_keyhole, x_scale),
            max(x_keyhole, x_scale),
            colors="black",
            linestyles=":",
            linewidth=1.5,
            zorder=19
        )
        ax.hlines(
            y_keyhole,
            x_scale - tick_width,
            x_scale + tick_width,
            colors="black",
            linewidth=2.0,
            zorder=21
        )
        text_lines.append(f"keyhole_depth = {keyhole_depth_um:.1f} um")
        if show_contour_positions:
            text_lines.append(f"keyhole {label_x_name} = {x_keyhole:.1f} um")

    if meltpool_depth is not None:
        x_meltpool, y_meltpool, meltpool_depth_um = meltpool_depth
        ax.hlines(
            y_meltpool,
            min(x_meltpool, x_scale),
            max(x_meltpool, x_scale),
            colors="gold",
            linestyles=":",
            linewidth=1.5,
            zorder=19
        )
        ax.hlines(
            y_meltpool,
            x_scale - tick_width,
            x_scale + tick_width,
            colors="gold",
            linewidth=2.0,
            zorder=21
        )
        text_lines.append(f"meltpool_depth = {meltpool_depth_um:.1f} um")
        if show_contour_positions:
            text_lines.append(f"meltpool {label_x_name} = {x_meltpool:.1f} um")

    if extra_text_lines:
        text_lines.extend(extra_text_lines)

    ax.text(
        0.02,
        0.98,
        "\n".join(text_lines),
        transform=ax.transAxes,
        color="black",
        va="top",
        ha="left",
        bbox=dict(facecolor="white", edgecolor="black", alpha=0.85),
        zorder=22
    )


def plot_slice(ax, Xg, Yg, Ag, Tg_liq_region, title, xlabel):
    pcm = ax.pcolormesh(
        Xg, Yg, Ag,
        shading="auto",
        cmap="coolwarm",
        vmin=0, vmax=1,
        rasterized=True
    )

    cs_alpha = ax.contour(
        Xg, Yg, Ag,
        levels=[0.5],
        colors="black",
        linewidths=2
    )
    if hasattr(cs_alpha, "collections"):
        for collection in cs_alpha.collections:
            collection.set_rasterized(True)

    cs_tliq = ax.contour(
        Xg, Yg, Tg_liq_region,
        levels=[T_LIQ],
        colors="yellow",
        linewidths=2
    )
    if hasattr(cs_tliq, "collections"):
        for collection in cs_tliq.collections:
            collection.set_rasterized(True)

    ax.axhline(
        y=SURFACE_Y_UM,
        linestyle="--",
        linewidth=1.5,
        color="white",
        zorder=10
    )

    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Y / depth (um)")
    ax.axis("equal")

    return pcm, cs_alpha, cs_tliq


# -----------------------------
# INTERPOLATE YZ SLICE
# -----------------------------
zg, yg, Zg, Yg, Ag_yz, Tg_yz_liq_region = interpolate_slice(yz, "z_um", "y_um", NZ, NY)

# -----------------------------
# PLOT YZ FIRST, THEN USE ITS DEEPEST Z FOR XY
# -----------------------------
fig, axes = plt.subplots(1, 2, figsize=(15, 6), constrained_layout=True)

pcm, cs_yz, cs_tliq_yz = plot_slice(
    axes[0], Zg, Yg, Ag_yz, Tg_yz_liq_region,
    title=f"YZ slice at x = {x_plane * 1e6:.1f} um",
    xlabel="Z / scan track (um)"
)

yz_depth = find_max_depth(cs_yz, SURFACE_Y_UM, "alpha.metal = 0.5")
meltpool_yz_depth = find_max_depth(cs_tliq_yz, SURFACE_Y_UM, f"T = {T_LIQ:.0f} K")
mark_combined_depths(axes[0], yz_depth, meltpool_yz_depth, SURFACE_Y_UM, zg, "z")
if meltpool_yz_depth is not None:
    z_at_meltpool_depth, y_at_meltpool_depth, meltpool_depth_um = meltpool_yz_depth
    print(f"YZ melt pool depth below surface = {meltpool_depth_um:.3f} um")
    print(f"YZ melt pool deepest point: z = {z_at_meltpool_depth:.3f} um, y = {y_at_meltpool_depth:.3f} um")

if yz_depth is None:
    z_at_max_depth = yz["z_um"].iloc[len(yz) // 2]
    print(f"Using fallback z for XY slice = {z_at_max_depth:.3f} um")
else:
    z_at_max_depth, y_at_max_depth, max_depth_um = yz_depth
    print(f"Max depth below surface = {max_depth_um:.3f} um")
    print(f"Z coordinate at max depth = {z_at_max_depth:.3f} um")
    print(f"Deepest contour point: z = {z_at_max_depth:.3f} um, y = {y_at_max_depth:.3f} um")

z_plane = df.loc[(df["z_um"] - z_at_max_depth).abs().idxmin(), "z"]
xy = df[np.isclose(df["z"], z_plane)].copy()

print(f"z_plane = {z_plane:.12e} m = {z_plane * 1e6:.3f} um")
print("XY slice shape:", xy.shape)
print("XY alpha range:", xy["alpha.metal"].min(), xy["alpha.metal"].max())
print("XY T range:", xy["T"].min(), xy["T"].max())

xg, yg_xy, Xg, Yg_xy, Ag_xy, Tg_xy_liq_region = interpolate_slice(xy, "x_um", "y_um", NX, NY)

_, cs_xy, cs_tliq_xy = plot_slice(
    axes[1], Xg, Yg_xy, Ag_xy, Tg_xy_liq_region,
    title=f"XY slice at z = {z_plane * 1e6:.1f} um",
    xlabel="X / width (um)"
)
xy_depth = find_max_depth(cs_xy, SURFACE_Y_UM, "alpha.metal = 0.5")
meltpool_xy_depth = find_max_depth(cs_tliq_xy, SURFACE_Y_UM, f"T = {T_LIQ:.0f} K")
keyhole_width = find_surface_width(cs_xy, SURFACE_Y_UM, "alpha.metal = 0.5")
meltpool_width = find_surface_width(cs_tliq_xy, SURFACE_Y_UM, f"T = {T_LIQ:.0f} K")

mark_surface_width(axes[1], meltpool_width, SURFACE_Y_UM, "gold")
mark_surface_width(axes[1], keyhole_width, SURFACE_Y_UM, "black")

xy_summary_lines = []
if keyhole_width is not None:
    x_left, x_right, keyhole_width_um = keyhole_width
    print(f"XY keyhole width at surface = {keyhole_width_um:.3f} um")
    print(f"XY keyhole surface intersections: x = {x_left:.3f} um, x = {x_right:.3f} um")
    xy_summary_lines.append(f"keyhole_width = {keyhole_width_um:.1f} um")
if meltpool_width is not None:
    x_left, x_right, meltpool_width_um = meltpool_width
    print(f"XY melt pool width at surface = {meltpool_width_um:.3f} um")
    print(f"XY melt pool surface intersections: x = {x_left:.3f} um, x = {x_right:.3f} um")
    xy_summary_lines.append(f"meltpool_width = {meltpool_width_um:.1f} um")

mark_combined_depths(
    axes[1],
    xy_depth,
    meltpool_xy_depth,
    SURFACE_Y_UM,
    xg,
    "x",
    extra_text_lines=xy_summary_lines,
    show_contour_positions=False,
)
if meltpool_xy_depth is not None:
    x_at_meltpool_depth, y_at_meltpool_depth, meltpool_depth_um = meltpool_xy_depth
    print(f"XY melt pool depth below surface = {meltpool_depth_um:.3f} um")
    print(f"XY melt pool deepest point: x = {x_at_meltpool_depth:.3f} um, y = {y_at_meltpool_depth:.3f} um")

xy_summary = pd.DataFrame([{
    "z_slice_um": z_plane * 1e6,
    "surface_y_um": SURFACE_Y_UM,
    "T_liq_K": T_LIQ,
    "keyhole_depth_um": depth_value(xy_depth),
    "keyhole_depth_x_um": depth_x_position(xy_depth),
    "keyhole_depth_y_um": depth_y_position(xy_depth),
    "meltpool_depth_um": depth_value(meltpool_xy_depth),
    "meltpool_depth_x_um": depth_x_position(meltpool_xy_depth),
    "meltpool_depth_y_um": depth_y_position(meltpool_xy_depth),
    "keyhole_width_um": width_value(keyhole_width),
    "keyhole_width_x_left_um": width_left_position(keyhole_width),
    "keyhole_width_x_right_um": width_right_position(keyhole_width),
    "meltpool_width_um": width_value(meltpool_width),
    "meltpool_width_x_left_um": width_left_position(meltpool_width),
    "meltpool_width_x_right_um": width_right_position(meltpool_width),
}])
xy_summary.to_csv(xy_summary_csv, index=False)
print(f"Saved XY summary CSV: {xy_summary_csv}")

fig.colorbar(pcm, ax=axes, label="alpha.metal")

legend_handles = [
    Line2D([0], [0], color="black", linewidth=2, label="alpha.metal = 0.5"),
    Line2D([0], [0], color="yellow", linewidth=2, label=f"T = {T_LIQ:.0f} K"),
    Line2D([0], [0], color="white", linestyle="--", linewidth=1.5, label="substrate surface"),
    Line2D([0], [0], color="black", linewidth=2.5, marker=r"$\leftrightarrow$", markersize=14,
           label="depth scale"),
    Line2D([0], [0], color="gold", linewidth=2.0, label="melt pool depth tick"),
    Line2D([0], [0], color="black", linewidth=3.0, marker="o", label="keyhole width"),
    Line2D([0], [0], color="gold", linewidth=3.0, marker="o", label="melt pool width"),
]
axes[1].legend(
    handles=legend_handles,
    loc="upper right",
    frameon=True,
    facecolor="white",
    edgecolor="black",
    framealpha=0.9,
)

# uncomment if you still want the old 180° rotated view
# plt.gca().invert_xaxis()
# plt.gca().invert_yaxis()

fig.savefig(figure_pdf, format="pdf", bbox_inches="tight", dpi=150)
plt.close(fig)
print(f"Saved figure PDF: {figure_pdf}")
