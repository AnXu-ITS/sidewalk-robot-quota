# -*- coding: utf-8 -*-
"""
project_cells.py — project cell centerlines from lon/lat to local meters.

The SUMO driver expects centerline coordinates in METERS (measure zone is
[15, 35] m along the polyline). Equirectangular projection relative to the
cell's first point is accurate to ~mm at 50 m scale.
Original lon/lat geometry is kept as centerline_ll.
"""
import json
import math
import os

CELLS = r"C:\Users\xuan1\Desktop\UOL学习\配送机器人workbench\pipeline\cells\selected_cells.json"


def project(coords):
    lon0, lat0 = coords[0]
    kx = 111320.0 * math.cos(math.radians(lat0))
    ky = 110540.0
    return [[(c[0] - lon0) * kx, (c[1] - lat0) * ky] for c in coords]


def main():
    with open(CELLS, encoding="utf-8") as f:
        data = json.load(f)
    for c in data["cells"]:
        ll = c["centerline"]
        if len(ll) < 2:
            raise RuntimeError(f"{c['cell_id']}: degenerate centerline")
        c["centerline_ll"] = ll
        c["centerline"] = [[round(x, 3), round(y, 3)]
                           for x, y in project(ll)]
    with open(CELLS, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    n = len(data["cells"])
    lens = [math.hypot(c["centerline"][-1][0] - c["centerline"][0][0],
                       c["centerline"][-1][1] - c["centerline"][0][1])
            for c in data["cells"]]
    print(f"projected {n} cells; chord lengths min={min(lens):.1f} "
          f"max={max(lens):.1f} m -> {CELLS}")


if __name__ == "__main__":
    main()
