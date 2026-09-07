# -*- coding: utf-8 -*-
"""Section 3b — recompute candidate widths via perpendicular cross-sections
(along the OBB long axis, central 80%), which is the correct width for straight
AND mildly-curved footways (OBB short-axis overstates width for curves)."""
import os

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import LineString, box

HERE = os.path.dirname(os.path.abspath(__file__))
PROC = os.path.join(HERE, "data", "processed")
STUDY = (836900.0, 826100.0, 838000.0, 827000.0)


def obb_axis(geom):
    r = geom.minimum_rotated_rectangle
    c = np.array(list(r.exterior.coords)[:4])
    v1, v2 = c[1] - c[0], c[2] - c[1]
    l1, l2 = np.hypot(*v1), np.hypot(*v2)
    if l1 >= l2:
        return l1, l2, v1 / l1, v2 / l2, c[0] + 0.5 * (v1 + v2)
    return l2, l1, v2 / l2, v1 / l1, c[0] + 0.5 * (v1 + v2)


def cross_widths(geom, center, u, v, length, step=1.0):
    prof = []
    s = -length / 2.0
    while s <= length / 2.0 + 1e-6:
        p = center + s * u
        seg = LineString([p - 8.0 * v, p + 8.0 * v])
        inter = geom.intersection(seg)
        w = inter.length if inter.geom_type == "LineString" else \
            (sum(part.length for part in inter.geoms)
             if hasattr(inter, "geoms") else 0.0)
        prof.append((s, w))
        s += step
    return prof


def main():
    gdf = gpd.read_file(os.path.join(PROC, "hk_pavement_sha_tin_clip_hk1980.gpkg"))
    fw = gdf[(gdf["FEAT_TYPE"] == "Footway")
             & (gdf["LVL"] == "Ground level")].copy()
    use_study = os.environ.get("HK_STUDY_ONLY", "0") == "1"
    if use_study:
        sbox = box(*STUDY)
        fw = fw[fw.geometry.intersects(sbox)].copy()
    fw = fw[fw.geometry.area > 1.0]

    rows = []
    for _, r in fw.iterrows():
        g = r.geometry
        length, width, u, v, center = obb_axis(g)
        prof = cross_widths(g, center, u, v, length)
        core = [w for s, w in prof if abs(s) <= 0.4 * length]
        core = [w for w in core if w > 0.05]
        w_med = float(np.median(core)) if core else 0.0
        w_min = float(np.min(core)) if core else 0.0
        w_p10 = float(np.percentile(core, 10)) if core else 0.0
        rect_fill = g.area / (length * width)
        rows.append(dict(PG_UID=r["PG_UID"], obb_len=round(length, 2),
                         obb_wid=round(width, 2), rect_fill=round(rect_fill, 3),
                         cw_median=round(w_med, 3), cw_min=round(w_min, 3),
                         cw_p10=round(w_p10, 3)))
    df = pd.DataFrame(rows)

    print("footways:", len(df))
    print("\ncross-section median width distribution (central 80%):")
    bins = [0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.2, 2.4, 2.7, 3.0, 3.5, 99]
    df["wbin"] = pd.cut(df["cw_median"], bins)
    print(df.groupby("wbin", observed=True).size().to_string())

    # in-domain by cross-section width (not OBB width)
    indom = df[(df["cw_median"] >= 1.6) & (df["cw_median"] <= 3.0)
               & (df["obb_len"] >= 20) & (df["obb_len"] <= 80)]
    print("\nin-domain by cross-section width (1.6-3.0, len 20-80):",
          len(indom))
    print(indom.groupby(pd.cut(indom["rect_fill"],
                               [0, 0.4, 0.65, 1.01],
                               labels=["C", "B", "A"]), observed=True)
          .size().to_string())

    df.to_csv(os.path.join(HERE, "sites", "hk_formal_pool_cw.csv"), index=False)
    print("\nwrote sites/hk_formal_pool_cw.csv")


if __name__ == "__main__":
    main()
