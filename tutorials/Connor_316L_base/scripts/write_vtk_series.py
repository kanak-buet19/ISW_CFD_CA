#!/usr/bin/env python3
"""Write a ParaView/VTK .vtk.series file for time-named legacy VTK files."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def vtk_time(path: Path) -> float:
    match = re.search(r"_([0-9.eE+-]+)\.vtk$", path.name)
    if not match:
        raise ValueError(f"Cannot parse time from {path.name}")
    return float(match.group(1))


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print("Usage: write_vtk_series.py VTK_DIR [OUTPUT_FILE]", file=sys.stderr)
        return 2

    vtk_dir = Path(sys.argv[1]).resolve()
    if len(sys.argv) == 3:
        series_path = Path(sys.argv[2]).resolve()
    else:
        series_path = vtk_dir / f"{vtk_dir.parent.name}.vtk.series"

    vtk_files = []
    for path in vtk_dir.glob("*.vtk"):
        try:
            vtk_files.append((vtk_time(path), path))
        except ValueError:
            continue

    vtk_files.sort(key=lambda item: item[0])

    payload = {
        "file-series-version": "1.0",
        "files": [
            {"name": path.name, "time": time_value}
            for time_value, path in vtk_files
        ],
    }

    series_path.parent.mkdir(parents=True, exist_ok=True)
    with series_path.open("w") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")

    print(f"Wrote {series_path} with {len(vtk_files)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
