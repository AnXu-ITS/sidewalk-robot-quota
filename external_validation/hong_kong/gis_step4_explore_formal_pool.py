# -*- coding: utf-8 -*-
"""Section 3 — explore the formal-sample candidate pool (Sha Tin ground public
footways): width / length / geometry-type distribution to guide the 30-50 cell
sample freeze."""
import os

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box

HERE = os.path.dirname(os.path.abspath(__file__))
PROC = os.path.join(HERE, "data", "processed")

STUDY = (836900.0, 826100.0, 838000.0, 827000.0)


def obb(geom):
    r = geom.minimum_rotated_rectangle
    c = np.array(list(r.exterior.coords)[:4])
    v1, v2 = c[1] - c[0], c[2] - c[1]
    l1, l2 = np.hypot(*v1), np.hypot(*v2)
    if l1 >= l2:
        return l1, l2
    return l2, l1


def main():
    gdf = gpd.read_file(os.path.join(PROC, "hk_pavement_sha_tin_clip_hk1980.gpkg"))
    fw = gdf[(gdf["FEAT_TYPE"] == "Footway")
             & (gdf["LVL"] == "Ground level")].copy()
    sbox = box(*STUDY)
    fw = fw[fw.geometry.intersects(sbox)].copy()
    fw = fw[fw.geometry.area > 1.0]  # drop slivers

    # OBB metrics
    lens, wids, rects = [], [], []
    for g in fw.geometry:
        l, w = obb(g)
        lens.append(l); wids.append(w); rects.append(g.area / (l * w))
    fw["obb_len"] = lens
    fw["obb_wid"] = wids
    fw["rect_fill"] = rects

    print("ground public Footway (study box, area>1m2):", len(fw))
    print("\nOBB width distribution:")
    bins = [0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.2, 2.4, 2.7, 3.0, 3.5, 4.0, 99]
    fw["wbin"] = pd.cut(fw["obb_wid"], bins)
    print(fw.groupby("wbin", observed=True).size().to_string())

    print("\nOBB length distribution:")
    lbins = [0, 15, 20, 25, 30, 40, 50, 60, 80, 120, 999]
    fw["lbin"] = pd.cut(fw["obb_len"], lbins)
    print(fw.groupby("lbin", observed=True).size().to_string())

    print("\nrect_fill (geometry type proxy) distribution:")
    def gtype(rf):
        return "A" if rf >= 0.65 else ("B" if rf >= 0.40 else "C")
    fw["gtype"] = fw["rect_fill"].apply(gtype)
    print(fw.groupby("gtype").size().to_string())

    # in-domain candidates: W in [1.6,3.0], L in [20,80]
    indom = fw[(fw["obb_wid"] >= 1.6) & (fw["obb_wid"] <= 3.0)
               & (fw["obb_len"] >= 20) & (fw["obb_len"] <= 80)]
    print("\nin-domain candidates (W 1.6-3.0, L 20-80):", len(indom),
          "| by gtype:")
    print(indom.groupby("gtype").size().to_string())

    fw.to_csv(os.path.join(HERE, "sites", "hk_formal_pool_explore.csv"),
              index=False)
    print("\nwrote sites/hk_formal_pool_explore.csv")


if __name__ == "__main__":
    main()
