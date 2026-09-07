# -*- coding: utf-8 -*-
"""Verify S3 robot behaviour: spawn, walkable-area containment, exit, speed."""
import glob
import os
import xml.etree.ElementTree as ET

import numpy as np
from shapely.geometry import Point, shape

_HERE = os.path.dirname(os.path.abspath(__file__))
GEO = __import__("json").load(open(os.path.join(_HERE, "sites",
                                               "hk_cell_local_geometry.json"),
                                  encoding="utf-8"))
POLY = shape({"type": "Polygon",
              "coordinates": GEO["HK-ST-01"]["walkable_polygon_local"]["coordinates"]})

WARMUP = 100.0
MEASURE = 240.0


def main():
    dirs = sorted(glob.glob(os.path.join(_HERE, "scenarios", "HK-ST-01_qp20_qr2_s*")))
    print(f"checking {len(dirs)} S3 scenario dirs for robot behaviour\n")
    all_ok = True
    for d in dirs:
        pinfo = os.path.join(d, "personinfo.xml")
        pfcd = os.path.join(d, "personfcd.xml")
        robots = []
        root = ET.parse(pinfo).getroot()
        for pi in root:
            if pi.tag != "personinfo" or pi.get("type") != "robot":
                continue
            walk = pi.find("walk")
            arr = walk.get("arrival") if walk is not None else None
            robots.append(dict(depart=float(pi.get("depart")),
                               arrival=float(arr) if arr is not None else -1.0))
        n_rob = len(robots)
        n_complete = sum(1 for r in robots if r["arrival"] >= 0)
        # robot positions/speeds from personfcd
        xs, ys, sp = [], [], []
        outside = 0
        for _, ts in ET.iterparse(pfcd, events=("end",)):
            if ts.tag != "timestep":
                continue
            t = float(ts.get("time"))
            for v in ts.iter("person"):
                if v.get("type") != "robot":
                    continue
                if WARMUP <= t < WARMUP + MEASURE:
                    x, y = float(v.get("x")), float(v.get("y"))
                    xs.append(x); ys.append(y); sp.append(float(v.get("speed")))
                    if not POLY.contains(Point(x, y)):
                        outside += 1
            ts.clear()
        mean_sp = float(np.mean(sp)) if sp else 0.0
        ok = n_rob >= 2 and n_complete == n_rob and outside == 0 and \
            mean_sp > 0.5
        all_ok = all_ok and ok
        print(f"{os.path.basename(d)}: robots={n_rob} completed={n_complete} "
              f"fcd_points={len(xs)} outside_walkable={outside} "
              f"robot_mean_speed={mean_sp:.3f} -> {'OK' if ok else 'FAIL'}")
    print(f"\nS3 robot-behaviour overall: {'PASS' if all_ok else 'FAIL'}")


if __name__ == "__main__":
    main()
