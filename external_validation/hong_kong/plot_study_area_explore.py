# -*- coding: utf-8 -*-
"""Plot an overview of Sha Tin ground-level public footways (exploration)."""
import os

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))
PROC = os.path.join(HERE, "data", "processed")
FIG = os.path.join(HERE, "figures")
os.makedirs(FIG, exist_ok=True)

FOOTWAY_LABELS = {"Footway", "Public Transport Interchange - Footway",
                  "Carpark - Footway"}
GROUND = "Ground level"


def obb_width(geom):
    r = geom.minimum_rotated_rectangle
    c = list(r.exterior.coords)[:4]
    import numpy as np
    pts = np.array(c)
    v1, v2 = pts[1] - pts[0], pts[2] - pts[1]
    return min(np.hypot(*v1), np.hypot(*v2))


def main():
    gdf = gpd.read_file(os.path.join(PROC, "hk_pavement_sha_tin_clip_hk1980.gpkg"))
    fw = gdf[(gdf["FEAT_TYPE"].isin(FOOTWAY_LABELS))
             & (gdf["LVL"] == GROUND)].copy()
    carr = gdf[gdf["FEAT_TYPE"] == "Carriageway"]
    fw["obb_w"] = fw.geometry.apply(obb_width)

    fig, ax = plt.subplots(figsize=(14, 12))
    # context: carriageways in light grey
    carr.plot(ax=ax, color="#d9d9d9", edgecolor="none", label="Carriageway")
    # footways coloured by width
    fw.plot(ax=ax, column="obb_w", cmap="viridis", legend=True,
            legend_kwds={"label": "oriented-bbox width (m)"},
            edgecolor="black", linewidth=0.3, alpha=0.9)
    # candidate study box ~800m
    study = (837000, 826200, 837800, 827000)
    ax.add_patch(Rectangle((study[0], study[1]), study[2] - study[0],
                           study[3] - study[1], fill=False,
                           edgecolor="red", linewidth=2, linestyle="--",
                           label="~800 m study box (candidate)"))
    ax.set_xlim(836000, 839100)
    ax.set_ylim(825300, 828300)
    ax.set_aspect("equal")
    ax.set_title("Sha Tin Town Centre — ground-level public footways (CSDI INV_PG)")
    ax.legend(loc="upper right")
    out = os.path.join(FIG, "hk_study_area_explore.png")
    plt.tight_layout()
    plt.savefig(out, dpi=110)
    print("wrote", out)


if __name__ == "__main__":
    main()
