# -*- coding: utf-8 -*-
"""Sanity-check the extracted formal-cell local geometry before committing to the
expensive simulation: bounds, area vs L*W, centerline placement, width-variation
flags."""
import json
import os

import numpy as np
from shapely.geometry import shape

HERE = os.path.dirname(os.path.abspath(__file__))
G = json.load(open(os.path.join(HERE, "sites", "hk_formal_local_geometry.json"),
                   encoding="utf-8"))
import csv
rows = list(csv.DictReader(open(
    os.path.join(HERE, "sites", "HONG_KONG_FORMAL_SAMPLE_FREEZE.csv"),
    encoding="utf-8")))

print(f"{'cell':8s} {'W':>6s} {'L':>6s} {'area':>7s} {'L*W':>7s} "
      f"{'xmin':>6s} {'xmax':>6s} {'ymin':>6s} {'ymax':>6s} {'p10/W':>6s} flag")
for r in rows:
    cid = r["cell_id"]
    g = G[cid]
    poly = shape({"type": "Polygon", "coordinates": g["walkable_polygon_local"]["coordinates"]})
    cl = np.array(g["centerline_local"])
    W = float(r["W"]); L = float(r["L"])
    area = poly.area
    bx0, by0, bx1, by1 = poly.bounds
    # centerline start/end
    cl0, cl1 = cl[0], cl[-1]
    p10 = float(r["width_p10"])
    flags = []
    if bx0 < -0.5 or bx1 > L + 0.5:
        flags.append("x-range")
    if by0 < -W - 3 or by1 > W + 3:
        flags.append("y-range")
    if abs(cl0[0]) > 0.5 or abs(cl0[1]) > 1.0:
        flags.append("start-off")
    if abs(cl1[0] - L) > 1.0:
        flags.append("end-off")
    if area / (L * W) < 0.5:
        flags.append("area-low")
    if p10 / W < 0.5:
        flags.append("width-var")
    print(f"{cid:8s} {W:6.2f} {L:6.1f} {area:7.1f} {L*W:7.1f} "
          f"{bx0:6.1f} {bx1:6.1f} {by0:6.1f} {by1:6.1f} {p10/W:6.2f} "
          f"{','.join(flags) or 'ok'}")
