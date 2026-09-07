# -*- coding: utf-8 -*-
"""
HK external test — GIS step 2a: explore Sha Tin ground-level public footways,
compute oriented-bbox metrics, and produce a candidate shortlist for cell selection.

Widths here are ORIENTED-BBOX widths (a sorting/exploration proxy only — clearly
NOT the final "measured net width"; the final width uses medial-axis profiles).
"""
import os

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Polygon

HERE = os.path.dirname(os.path.abspath(__file__))
PROC = os.path.join(HERE, "data", "processed")
SITES = os.path.join(HERE, "sites")
os.makedirs(SITES, exist_ok=True)

# correct string labels (decoded in the GEOJSON)
FOOTWAY_LABELS = {"Footway", "Public Transport Interchange - Footway",
                  "Carpark - Footway"}
GROUND = "Ground level"


def oriented_bbox_metrics(geom):
    """Return (length_m, width_m, angle_deg, rect_geom) of the min rotated rect."""
    rect = geom.minimum_rotated_rectangle
    coords = list(rect.exterior.coords)[:4]
    pts = np.array(coords)
    # edge vectors
    v1 = pts[1] - pts[0]
    v2 = pts[2] - pts[1]
    l1, l2 = np.hypot(*v1), np.hypot(*v2)
    length = max(l1, l2)
    width = min(l1, l2)
    return length, width, rect


def main():
    clip = os.path.join(PROC, "hk_pavement_sha_tin_clip_hk1980.gpkg")
    gdf = gpd.read_file(clip)
    print("clip rows:", len(gdf), "CRS:", gdf.crs)

    fw = gdf[(gdf["FEAT_TYPE"].isin(FOOTWAY_LABELS))
             & (gdf["LVL"] == GROUND)].copy()
    print("ground-level public footway polygons:", len(fw))

    fw["area_m2"] = fw.geometry.area
    fw["perimeter_m"] = fw.geometry.length
    # oriented bbox metrics
    lw = fw.geometry.apply(oriented_bbox_metrics)
    fw["obb_length_m"] = lw.apply(lambda t: t[0])
    fw["obb_width_m"] = lw.apply(lambda t: t[1])

    # summary
    print("\n=== oriented-bbox width bins (ground footways) ===")
    bins = [0, 1.0, 1.6, 2.0, 2.4, 3.0, 4.0, 6.0, 100]
    labels = ["<1.0", "1.0-1.6", "1.6-2.0", "2.0-2.4", "2.4-3.0",
              "3.0-4.0", "4.0-6.0", ">=6.0"]
    fw["wbin"] = pd.cut(fw["obb_width_m"], bins=bins, labels=labels)
    print(fw["wbin"].value_counts().reindex(labels).to_string())

    print("\n=== length bins (obb_length_m) ===")
    lbins = [0, 10, 20, 30, 50, 100, 5000]
    llabels = ["<10", "10-20", "20-30", "30-50", "50-100", ">=100"]
    fw["lbin"] = pd.cut(fw["obb_length_m"], bins=lbins, labels=llabels)
    print(fw["lbin"].value_counts().reindex(llabels).to_string())

    # candidates: width in [1.0, 4.0] (footway-plausible) and length >= 15
    cand = fw[(fw["obb_width_m"] >= 1.0) & (fw["obb_width_m"] <= 4.5)
              & (fw["obb_length_m"] >= 15)].copy()
    cand = cand.sort_values("obb_length_m", ascending=False)
    print(f"\ncandidates (obb width 1.0-4.5 m, length >=15 m): {len(cand)}")

    cols = ["PG_UID", "FEAT_TYPE", "SUR_TYPE_1", "LVL", "area_m2",
            "obb_length_m", "obb_width_m", "Shape_Length", "Shape_Area"]
    print(cand[cols].head(40).to_string(index=False))

    # save shortlist
    cand_out = cand.drop(columns=["wbin", "lbin"])
    cand_out.to_file(os.path.join(SITES, "hk_footway_candidates_explore.gpkg"),
                     driver="GPKG", layer="footway_candidates")
    cand_out.drop(columns=["geometry"]).to_csv(
        os.path.join(SITES, "hk_footway_candidates_explore.csv"), index=False)
    print("\nwrote sites/hk_footway_candidates_explore.{gpkg,csv}")

    # overall bbox
    print("\nstudy envelope (HK1980):", tuple(round(v, 1) for v in fw.total_bounds))


if __name__ == "__main__":
    main()
