#!/usr/bin/env python3

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image
from scipy import ndimage as ndi
from matplotlib.path import Path as MplPath


# -----------------------------
# SETTINGS
# -----------------------------
IMAGE_PATH = Path("/home/kanak/ISW_CFD_CA/tutorials/Connor_316L_base/exp_figure/exp_weld12_earth.png")
OUTPUT_OVERLAY = IMAGE_PATH.with_name("exp_weld12_earth_overlay.png")
OUTPUT_MASK = IMAGE_PATH.with_name("exp_weld12_earth_mask.png")
OUTPUT_CSV = IMAGE_PATH.with_name("exp_weld12_earth_summary.csv")
CONTOUR_CSV = IMAGE_PATH.with_name("exp_weld12_earth_contour_points.csv")

SCALE_BAR_UM = 250.0

# Crop limits as fractions of image size. These exclude the white border,
# bottom label, and scale-bar text from the melt-pool segmentation.
MELTPOOL_ROI = dict(x0=0.05, x1=0.96, y0=0.10, y1=0.88)
SCALE_BAR_ROI = dict(x0=0.68, x1=0.98, y0=0.78, y1=0.98)

# Surface/reference line in pixel coordinates. Leave this as None when the
# manual contour includes the full bead outline; the top of the mask is then
# used as the reference for depth.
SURFACE_Y_PX = None

# Automatic segmentation is unreliable on etched weld macrographs because the
# base metal texture can be as bright as the melt pool. By default, use a
# hand-tunable polygon around the fusion boundary.
USE_MANUAL_CONTOUR = True
DEFAULT_MANUAL_CONTOUR_PX = [
    (16, 92),
    (56, 105),
    (90, 105),
    (142, 91),
    (204, 103),
    (287, 104),
    (369, 96),
    (471, 96),
    (556, 104),
    (633, 103),
    (654, 109),
    (696, 105),
    (728, 95),
    (772, 108),
    (830, 108),
    (792, 131),
    (742, 150),
    (704, 159),
    (650, 198),
    (604, 267),
    (551, 355),
    (496, 405),
    (441, 423),
    (382, 420),
    (323, 395),
    (270, 344),
    (218, 257),
    (173, 185),
    (130, 158),
    (57, 151),
    (26, 118),
]

# Segmentation controls. Increase MIN_COMPONENT_AREA_PX if small artifacts are included.
MELTPOOL_DARK_THRESHOLD = 0.88
MELTPOOL_MIN_COMPONENT_AREA_PX = 8_000
MELTPOOL_CLOSE_ITERATIONS = 7
MELTPOOL_FILL_HOLES = True


def crop_bounds(width, height, roi):
    return (
        int(roi["x0"] * width),
        int(roi["x1"] * width),
        int(roi["y0"] * height),
        int(roi["y1"] * height),
    )


def load_gray(path):
    rgb = np.asarray(Image.open(path).convert("RGB"))
    gray = np.asarray(Image.fromarray(rgb).convert("L"), dtype=float) / 255.0
    return rgb, gray


def calibrate_scale_bar(gray):
    height, width = gray.shape
    x0, x1, y0, y1 = crop_bounds(width, height, SCALE_BAR_ROI)
    roi = gray[y0:y1, x0:x1]

    dark = roi < 0.18
    dark = ndi.binary_opening(dark, structure=np.ones((2, 6)))
    labels, n_labels = ndi.label(dark)

    best_label = None
    best_score = -np.inf
    for label_id in range(1, n_labels + 1):
        ys, xs = np.where(labels == label_id)
        if len(xs) == 0:
            continue
        comp_width = xs.max() - xs.min() + 1
        comp_height = ys.max() - ys.min() + 1
        area = len(xs)
        score = comp_width - 4.0 * comp_height + 0.02 * area
        if comp_width > 50 and comp_height < 25 and score > best_score:
            best_score = score
            best_label = label_id

    if best_label is None:
        raise RuntimeError("Could not detect the 250 um scale bar. Adjust SCALE_BAR_ROI or threshold.")

    ys, xs = np.where(labels == best_label)
    x_left = x0 + xs.min()
    x_right = x0 + xs.max()
    y_mid = y0 + 0.5 * (ys.min() + ys.max())
    scale_bar_px = x_right - x_left + 1
    um_per_px = SCALE_BAR_UM / scale_bar_px

    return {
        "scale_bar_px": scale_bar_px,
        "um_per_px": um_per_px,
        "x_left": x_left,
        "x_right": x_right,
        "y_mid": y_mid,
    }


def load_manual_contour():
    if CONTOUR_CSV.exists():
        points = pd.read_csv(CONTOUR_CSV)[["x_px", "y_px"]].to_numpy(dtype=float)
        if len(points) >= 3:
            return [tuple(point) for point in points]
        raise RuntimeError(f"Contour file has fewer than 3 points: {CONTOUR_CSV}")
    return DEFAULT_MANUAL_CONTOUR_PX


def draw_manual_contour(rgb):
    fig, ax = plt.subplots(figsize=(12, 7), constrained_layout=True)
    ax.imshow(rgb)
    ax.set_title("Left-click contour points in order. Press Enter when done. Backspace removes last point.")
    ax.set_axis_off()

    points = []
    point_artist, = ax.plot([], [], "ko", markersize=4)
    line_artist, = ax.plot([], [], "k-", linewidth=1.5)

    def redraw_points():
        if points:
            xs, ys = zip(*points)
        else:
            xs, ys = [], []
        point_artist.set_data(xs, ys)
        line_artist.set_data(xs, ys)
        fig.canvas.draw_idle()

    def on_click(event):
        if event.inaxes != ax or event.button != 1 or event.xdata is None or event.ydata is None:
            return
        points.append((event.xdata, event.ydata))
        redraw_points()

    def on_key(event):
        if event.key in ("enter", "return"):
            plt.close(fig)
        elif event.key == "backspace" and points:
            points.pop()
            redraw_points()

    fig.canvas.mpl_connect("button_press_event", on_click)
    fig.canvas.mpl_connect("key_press_event", on_key)
    plt.show()

    plt.close(fig)

    if len(points) < 3:
        raise RuntimeError("Need at least 3 points to create a contour.")

    contour = [(round(x, 2), round(y, 2)) for x, y in points]
    pd.DataFrame(contour, columns=["x_px", "y_px"]).to_csv(CONTOUR_CSV, index=False)
    print(f"Saved contour points: {CONTOUR_CSV}")
    return contour


def segment_meltpool(gray, manual_contour_px):
    if USE_MANUAL_CONTOUR:
        height, width = gray.shape
        yy, xx = np.mgrid[:height, :width]
        points = np.column_stack([xx.ravel(), yy.ravel()])
        polygon = MplPath(manual_contour_px)
        return polygon.contains_points(points).reshape(gray.shape)

    height, width = gray.shape
    x0, x1, y0, y1 = crop_bounds(width, height, MELTPOOL_ROI)
    roi = gray[y0:y1, x0:x1]

    # The melt pool is usually brighter/less horizontally banded than the base.
    local_mean = ndi.uniform_filter(roi, size=35)
    local_std = np.sqrt(np.maximum(ndi.uniform_filter((roi - local_mean) ** 2, size=35), 1e-12))
    contrast_score = roi + 0.35 * local_std
    threshold = np.quantile(contrast_score, MELTPOOL_DARK_THRESHOLD)
    mask_roi = contrast_score >= threshold

    mask_roi = ndi.binary_closing(mask_roi, structure=np.ones((5, 5)), iterations=MELTPOOL_CLOSE_ITERATIONS)
    mask_roi = ndi.binary_opening(mask_roi, structure=np.ones((3, 3)), iterations=2)
    if MELTPOOL_FILL_HOLES:
        mask_roi = ndi.binary_fill_holes(mask_roi)

    labels, n_labels = ndi.label(mask_roi)
    if n_labels == 0:
        raise RuntimeError("No melt-pool component found. Adjust MELTPOOL_DARK_THRESHOLD.")

    best_label = None
    best_area = -1
    for label_id in range(1, n_labels + 1):
        area = np.sum(labels == label_id)
        if area > best_area and area >= MELTPOOL_MIN_COMPONENT_AREA_PX:
            best_area = area
            best_label = label_id

    if best_label is None:
        raise RuntimeError("No large melt-pool component found. Lower MELTPOOL_MIN_COMPONENT_AREA_PX.")

    mask_roi = labels == best_label
    mask = np.zeros_like(gray, dtype=bool)
    mask[y0:y1, x0:x1] = mask_roi
    return mask


def measure_mask(mask, um_per_px):
    ys, xs = np.where(mask)
    if len(xs) == 0:
        raise RuntimeError("Empty melt-pool mask.")

    if SURFACE_Y_PX is not None:
        surface_y = SURFACE_Y_PX
    else:
        surface_y = ys.min()
    bottom_y = ys.max()

    if SURFACE_Y_PX is not None:
        surface_rows = np.where(mask[max(surface_y - 2, 0):surface_y + 3, :])[1]
        if len(surface_rows) >= 2:
            left_x = surface_rows.min()
            right_x = surface_rows.max()
        else:
            near_surface = np.abs(ys - surface_y) <= 5
            left_x = xs[near_surface].min()
            right_x = xs[near_surface].max()
    else:
        left_x = xs.min()
        right_x = xs.max()

    width_px = right_x - left_x
    depth_px = bottom_y - surface_y
    area_px2 = np.sum(mask)

    return {
        "surface_y_px": surface_y,
        "left_x_px": left_x,
        "right_x_px": right_x,
        "bottom_y_px": bottom_y,
        "width_px": width_px,
        "depth_px": depth_px,
        "area_px2": area_px2,
        "width_um": width_px * um_per_px,
        "depth_um": depth_px * um_per_px,
        "area_um2": area_px2 * um_per_px**2,
    }


def save_overlay(rgb, mask, scale_info, metrics):
    fig, ax = plt.subplots(figsize=(10, 6), constrained_layout=True)
    ax.imshow(rgb, cmap="gray")

    outline = mask ^ ndi.binary_erosion(mask)
    ys, xs = np.where(outline)
    ax.scatter(xs, ys, s=1, c="red", alpha=0.9, label="melt pool mask")

    ax.axhline(metrics["surface_y_px"], color="cyan", linewidth=1.5, linestyle="--", label="surface")
    ax.annotate(
        "",
        xy=(metrics["left_x_px"], metrics["surface_y_px"]),
        xytext=(metrics["right_x_px"], metrics["surface_y_px"]),
        arrowprops=dict(arrowstyle="<->", color="blue", linewidth=2.5),
    )
    x_mid = 0.5 * (metrics["left_x_px"] + metrics["right_x_px"])
    ax.annotate(
        "",
        xy=(x_mid, metrics["surface_y_px"]),
        xytext=(x_mid, metrics["bottom_y_px"]),
        arrowprops=dict(arrowstyle="<->", color="blue", linewidth=2.5),
    )

    ax.plot(
        [scale_info["x_left"], scale_info["x_right"]],
        [scale_info["y_mid"], scale_info["y_mid"]],
        color="lime",
        linewidth=3,
        label="detected scale bar",
    )

    ax.text(
        0.02,
        0.02,
        "\n".join([
            f"scale = {scale_info['um_per_px']:.4f} um/px",
            f"width = {metrics['width_um']:.1f} um",
            f"depth = {metrics['depth_um']:.1f} um",
            f"area = {metrics['area_um2']:.1f} um^2",
        ]),
        transform=ax.transAxes,
        color="black",
        bbox=dict(facecolor="white", edgecolor="black", alpha=0.85),
        va="bottom",
        ha="left",
    )

    ax.set_axis_off()
    ax.legend(loc="upper right", framealpha=0.85)
    fig.savefig(OUTPUT_OVERLAY, dpi=200)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Measure experimental melt-pool geometry.")
    parser.add_argument(
        "--draw",
        action="store_true",
        help="Open an interactive window to click contour points before measuring.",
    )
    args = parser.parse_args()

    rgb, gray = load_gray(IMAGE_PATH)
    manual_contour_px = draw_manual_contour(rgb) if args.draw else load_manual_contour()
    scale_info = calibrate_scale_bar(gray)
    mask = segment_meltpool(gray, manual_contour_px)
    metrics = measure_mask(mask, scale_info["um_per_px"])

    Image.fromarray((mask.astype(np.uint8) * 255)).save(OUTPUT_MASK)
    save_overlay(rgb, mask, scale_info, metrics)

    row = {**scale_info, **metrics}
    pd.DataFrame([row]).to_csv(OUTPUT_CSV, index=False)

    print(f"Saved overlay: {OUTPUT_OVERLAY}")
    print(f"Saved mask: {OUTPUT_MASK}")
    print(f"Saved CSV: {OUTPUT_CSV}")
    print(f"Width = {metrics['width_um']:.3f} um")
    print(f"Depth = {metrics['depth_um']:.3f} um")
    print(f"Area = {metrics['area_um2']:.3f} um^2")


if __name__ == "__main__":
    main()
