#!/usr/bin/env python3
"""Create mid-X YZ slices from OpenFOAM legacy VTK output.

This script intentionally uses the Python VTK package instead of ParaView's
`paraview.simple` module, so it can be run with normal `python3`.
"""

import csv
import glob
import os
import sys

vtk = None


def fail(message):
    print(message, file=sys.stderr)
    sys.exit(1)


def load_vtk():
    global vtk
    try:
        import vtk as vtk_module
    except ImportError:
        fail(
            "Python package 'vtk' is required for slicing. Install it with "
            "`python3 -m pip install vtk` or load a Python environment that includes VTK."
        )
    vtk = vtk_module


FIELD_SPECS = [
    ("alpha.metal", "alpha.metal", (0.0, 1.0)),
    ("T", "T", (300.0, 1800.0)),
]


FIELD_UNITS = {
    "alpha.metal": "",
    "T": "K",
}


def add_scale_bar(renderer, bounds):
    y_len = bounds[3] - bounds[2]
    z_len = bounds[5] - bounds[4]
    target_len = 0.25 * max(y_len, z_len)
    nice_lengths = [2.0e-3, 1.0e-3, 5.0e-4, 2.0e-4, 1.0e-4, 5.0e-5]
    scale_len = next((length for length in nice_lengths if length <= target_len), nice_lengths[-1])

    points = vtk.vtkPoints()
    points.InsertNextPoint(325, 75, 0)
    points.InsertNextPoint(535, 75, 0)

    line = vtk.vtkLine()
    line.GetPointIds().SetId(0, 0)
    line.GetPointIds().SetId(1, 1)

    cells = vtk.vtkCellArray()
    cells.InsertNextCell(line)

    polyline = vtk.vtkPolyData()
    polyline.SetPoints(points)
    polyline.SetLines(cells)

    mapper = vtk.vtkPolyDataMapper2D()
    mapper.SetInputData(polyline)

    actor = vtk.vtkActor2D()
    actor.SetMapper(mapper)
    actor.GetProperty().SetColor(1.0, 1.0, 1.0)
    actor.GetProperty().SetLineWidth(5)
    renderer.AddActor2D(actor)

    label = vtk.vtkTextActor()
    label.SetInput(f"{scale_len * 1000:g} mm")
    label.SetPosition(395, 88)
    label.GetTextProperty().SetColor(1.0, 1.0, 1.0)
    label.GetTextProperty().SetFontSize(22)
    label.GetTextProperty().SetJustificationToCentered()
    renderer.AddActor2D(label)


def add_axis_legend(renderer):
    points = vtk.vtkPoints()
    points.InsertNextPoint(85, 60, 0)
    points.InsertNextPoint(210, 60, 0)
    points.InsertNextPoint(85, 60, 0)
    points.InsertNextPoint(85, 145, 0)

    cells = vtk.vtkCellArray()
    for first, second in ((0, 1), (2, 3)):
        line = vtk.vtkLine()
        line.GetPointIds().SetId(0, first)
        line.GetPointIds().SetId(1, second)
        cells.InsertNextCell(line)

    polyline = vtk.vtkPolyData()
    polyline.SetPoints(points)
    polyline.SetLines(cells)

    mapper = vtk.vtkPolyDataMapper2D()
    mapper.SetInputData(polyline)

    actor = vtk.vtkActor2D()
    actor.SetMapper(mapper)
    actor.GetProperty().SetColor(1.0, 1.0, 1.0)
    actor.GetProperty().SetLineWidth(4)
    renderer.AddActor2D(actor)

    for text, pos in (("Z", (220, 52)), ("Y", (78, 152))):
        label = vtk.vtkTextActor()
        label.SetInput(text)
        label.SetPosition(*pos)
        label.GetTextProperty().SetColor(1.0, 1.0, 1.0)
        label.GetTextProperty().SetFontSize(20)
        renderer.AddActor2D(label)


def find_vtk_file(case_dir, time_name):
    case_name = os.path.basename(case_dir.rstrip(os.sep))
    vtk_file = os.path.join(case_dir, "VTK", f"{case_name}_{time_name}.vtk")
    if os.path.exists(vtk_file):
        return vtk_file

    matches = glob.glob(os.path.join(case_dir, "VTK", f"*_{time_name}.vtk"))
    if matches:
        return matches[0]

    fail(f"Could not find VTK file for time {time_name}")


def read_dataset(vtk_file):
    reader = vtk.vtkGenericDataObjectReader()
    reader.SetFileName(vtk_file)
    reader.Update()

    output = reader.GetOutput()
    if output is None or output.GetNumberOfPoints() == 0:
        fail(f"No readable points found in {vtk_file}")

    return output


def make_slice(dataset):
    bounds = dataset.GetBounds()
    x_mid = 0.5 * (bounds[0] + bounds[1])
    y_mid = 0.5 * (bounds[2] + bounds[3])
    z_mid = 0.5 * (bounds[4] + bounds[5])

    # OpenFOAM fields are often cell-centered. Convert them to points first so
    # vtkCutter can interpolate field values onto the slice.
    cell_to_point = vtk.vtkCellDataToPointData()
    cell_to_point.SetInputData(dataset)
    cell_to_point.PassCellDataOn()
    cell_to_point.Update()

    plane = vtk.vtkPlane()
    plane.SetOrigin(x_mid, y_mid, z_mid)
    plane.SetNormal(1.0, 0.0, 0.0)

    cutter = vtk.vtkCutter()
    cutter.SetInputConnection(cell_to_point.GetOutputPort())
    cutter.SetCutFunction(plane)
    cutter.Update()

    geometry = vtk.vtkGeometryFilter()
    geometry.SetInputConnection(cutter.GetOutputPort())
    geometry.Update()

    return geometry.GetOutput(), bounds, (x_mid, y_mid, z_mid)


def get_array(polydata, field_name):
    point_data = polydata.GetPointData()
    cell_data = polydata.GetCellData()
    return point_data.GetArray(field_name) or cell_data.GetArray(field_name)


def write_slice_vtp(polydata, path):
    writer = vtk.vtkXMLPolyDataWriter()
    writer.SetFileName(path)
    writer.SetInputData(polydata)
    writer.Write()


def write_field_csv(polydata, field_name, path):
    values = get_array(polydata, field_name)
    if values is None:
        print(f"Warning: field '{field_name}' not found; skipping CSV", file=sys.stderr)
        return False

    with open(path, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["x", "y", "z", field_name])
        for point_id in range(polydata.GetNumberOfPoints()):
            x, y, z = polydata.GetPoint(point_id)
            writer.writerow([x, y, z, values.GetTuple1(point_id)])

    return True


def render_field_png(polydata, field_name, value_range, bounds, center, path):
    values = get_array(polydata, field_name)
    if values is None:
        print(f"Warning: field '{field_name}' not found; skipping PNG", file=sys.stderr)
        return False

    polydata.GetPointData().SetActiveScalars(field_name)

    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputData(polydata)
    mapper.SetScalarModeToUsePointFieldData()
    mapper.SelectColorArray(field_name)
    mapper.SetScalarRange(value_range[0], value_range[1])

    actor = vtk.vtkActor()
    actor.SetMapper(mapper)

    renderer = vtk.vtkRenderer()
    renderer.SetBackground(0.30, 0.33, 0.43)
    renderer.AddActor(actor)

    scalar_bar = vtk.vtkScalarBarActor()
    scalar_bar.SetLookupTable(mapper.GetLookupTable())
    scalar_bar.SetTitle(field_name if not FIELD_UNITS.get(field_name) else f"{field_name} [{FIELD_UNITS[field_name]}]")
    scalar_bar.SetNumberOfLabels(5)
    scalar_bar.SetWidth(0.08)
    scalar_bar.SetHeight(0.55)
    scalar_bar.SetPosition(0.88, 0.22)
    scalar_bar.GetTitleTextProperty().SetColor(1.0, 1.0, 1.0)
    scalar_bar.GetTitleTextProperty().SetFontSize(16)
    scalar_bar.GetLabelTextProperty().SetColor(1.0, 1.0, 1.0)
    scalar_bar.GetLabelTextProperty().SetFontSize(13)
    renderer.AddActor2D(scalar_bar)

    add_scale_bar(renderer, bounds)
    add_axis_legend(renderer)

    window = vtk.vtkRenderWindow()
    window.SetOffScreenRendering(1)
    window.SetSize(1400, 900)
    window.AddRenderer(renderer)

    y_len = max(bounds[3] - bounds[2], 1e-12)
    z_len = max(bounds[5] - bounds[4], 1e-12)
    length = max(y_len, z_len)
    x_mid, y_mid, z_mid = center

    camera = renderer.GetActiveCamera()
    camera.SetFocalPoint(x_mid, y_mid, z_mid)
    camera.SetPosition(x_mid + length * 3.0, y_mid, z_mid)
    camera.SetViewUp(0.0, -1.0, 0.0)
    camera.ParallelProjectionOn()
    camera.SetParallelScale(0.55 * length)

    window.Render()

    image = vtk.vtkWindowToImageFilter()
    image.SetInput(window)
    image.Update()

    writer = vtk.vtkPNGWriter()
    writer.SetFileName(path)
    writer.SetInputConnection(image.GetOutputPort())
    writer.Write()
    return True


def main():
    if len(sys.argv) != 4:
        fail("Usage: make_yz_slices.py CASE_DIR TIME OUTPUT_DIR")

    load_vtk()

    case_dir = os.path.abspath(sys.argv[1])
    time_name = sys.argv[2]
    output_dir = os.path.abspath(sys.argv[3])
    safe_time = time_name.replace("/", "_")

    vtk_file = find_vtk_file(case_dir, time_name)
    dataset = read_dataset(vtk_file)
    slice_data, bounds, center = make_slice(dataset)

    if slice_data.GetNumberOfPoints() == 0:
        fail(f"Mid-X slice for time {time_name} is empty")

    os.makedirs(output_dir, exist_ok=True)
    write_slice_vtp(slice_data, os.path.join(output_dir, f"yz_slice_{safe_time}.vtp"))

    for field_name, folder, value_range in FIELD_SPECS:
        field_dir = os.path.join(output_dir, folder)
        os.makedirs(field_dir, exist_ok=True)
        write_field_csv(slice_data, field_name, os.path.join(field_dir, f"{field_name}_{safe_time}.csv"))
        render_field_png(
            slice_data,
            field_name,
            value_range,
            bounds,
            center,
            os.path.join(field_dir, f"{field_name}_{safe_time}.png"),
        )


if __name__ == "__main__":
    main()
