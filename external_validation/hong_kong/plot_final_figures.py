# -*- coding: utf-8 -*-
"""Generate final HK external-test figures (study area, candidate cells, width profiles)."""
import os

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Polygon as MplPolygon
from shapely.geometry import LineString

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "figures")
PROC = os.path.join(HERE, "data", "processed")
SITES = os.path.join(HERE, "sites")
os.makedirs(FIG, exist_ok=True)

STUDY_BOX = (836900, 826100, 838000, 827000)  # HK1980 EPSG:2326
CELLS = [
    ("HK-ST-01", "PG4019702R0312", 50.0),
    ("HK-ST-02", "PG4019703R0312", 50.0),
    ("HK-ST-03", "PG4019765R0312", 35.0),
]
COLORS = {"Footway": "#2c7fb8", "Carriageway": "#c994c7",
          "PTI-Footway": "#41b6c4", "TrafficIsland-Refuge": "#a1dab4",
          "Other": "#bbbbbb"}


def obb_axis(geom):
    r = geom.minimum_rotated_rectangle
    c = np.array(list(r.exterior.coords)[:4])
    v1, v2 = c[1] - c[0], c[2] - c[1]
    l1, l2 = np.hypot(*v1), np.hypot(*v2)
    if l1 >= l2:
        return l1, l2, v1 / l1, v2 / l2, c[0] + 0.5 * (v1 + v2)
    return l2, l1, v2 / l2, v1 / l1, c[0] + 0.5 * (v1 + v2)


def cross_sections(geom, center, u, v, length, step=0.5):
    prof = []
    s = -length / 2.0
    while s <= length / 2.0 + 1e-6:
        p = center + s * u
        seg = LineString([p - 3.0 * v, p + 3.0 * v])
        inter = geom.intersection(seg)
        w = inter.length if inter.geom_type == "LineString" else \
            (sum(part.length for part in inter.geoms)
             if hasattr(inter, "geoms") else 0.0)
        prof.append((s, w))
        s += step
    return prof


def main():
    clip = gpd.read_file(os.path.join(PROC, "hk_pavement_sha_tin_clip_hk1980.gpkg"))

    # ---- Figure 1: study area -------------------------------------------
    fig, ax = plt.subplots(figsize=(11, 8))
    x0, y0, x1, y1 = STUDY_BOX
    from shapely.geometry import box
    study = box(x0, y0, x1, y1)
    sub = clip[clip.geometry.intersects(study)]
    for label, color in COLORS.items():
        g = sub[sub["FEAT_TYPE"] == label]
        if len(g):
            g.plot(ax=ax, color=color, linewidth=0.2, alpha=0.85, label=label)
    cand = gpd.read_file(os.path.join(SITES, "hk_smoke_candidates.gpkg"))
    cand.to_crs("EPSG:2326").plot(ax=ax, facecolor="none", edgecolor="red",
                                  linewidth=2.2, label="candidate cells")
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal")
    ax.set_title("Sha Tin Town Centre — study box (HK1980 EPSG:2326)")
    ax.legend(loc="upper right", fontsize=7, framealpha=0.9)
    ax.set_xlabel("Easting (m)"); ax.set_ylabel("Northing (m)")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "hk_study_area.png"), dpi=150)
    plt.close(fig)

    # ---- Figure 2: candidate cells --------------------------------------
    fig, ax = plt.subplots(figsize=(11, 8))
    for label, color in COLORS.items():
        g = sub[sub["FEAT_TYPE"] == label]
        if len(g):
            g.plot(ax=ax, color=color, linewidth=0.2, alpha=0.8)
    gdf = gpd.read_file(os.path.join(SITES, "hk_smoke_candidates.gpkg")).to_crs("EPSG:2326")
    gdf = gdf.set_index("cell_id")
    # draw a zoomed window around the 3 cells
    b = gdf.geometry.total_bounds
    pad = 60
    ax.set_xlim(b[0] - pad, b[2] + pad)
    ax.set_ylim(b[1] - pad, b[3] + pad)
    for cid, _uid, _L in CELLS:
        g = gdf.loc[cid, "geometry"]
        xs, ys = g.exterior.xy
        ax.fill(xs, ys, facecolor="red", alpha=0.25, edgecolor="red", linewidth=1.5)
        cx, cy = g.centroid.x, g.centroid.y
        ax.text(cx, cy, f"{cid}\nW={gdf.loc[cid,'W']} m", ha="center",
                va="center", fontsize=8, color="darkred", fontweight="bold")
    ax.set_aspect("equal")
    ax.set_title("Candidate micro-cells (real footway polygons)")
    ax.set_xlabel("Easting (m)"); ax.set_ylabel("Northing (m)")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "hk_candidate_cells.png"), dpi=150)
    plt.close(fig)

    # ---- Figure 3: width profiles ---------------------------------------
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    gdf = gdf.reset_index().set_index("source_id")
    for ax_i, (cid, uid, L) in enumerate(CELLS):
        ax = axes[ax_i]
        geom = gdf.loc[uid, "geometry"]
        length, width, u, v, center = obb_axis(geom)
        prof = cross_sections(geom, center, u, v, L)
        ss = [s + L / 2.0 for s, _ in prof]   # s=0 at cell start
        ws = [w for _, w in prof]
        core = [(s, w) for s, w in zip(ss, ws) if L * 0.1 <= s <= L * 0.9]
        ax.plot(ss, ws, color="#2c7fb8", lw=1.2)
        ax.axvspan(L * 0.1, L * 0.9, color="green", alpha=0.08)
        med = float(np.median([w for _, w in core]))
        ax.axhline(med, color="red", ls="--", lw=1,
                   label=f"median={med:.2f} m")
        ax.axhline(1.6, color="orange", ls=":", lw=1, label="W_min=1.6 m")
        ax.set_title(f"{cid}  (L={L} m)")
        ax.set_xlabel("along-centerline s (m)")
        ax.set_ylabel("cross-section width (m)")
        ax.set_ylim(0, max(ws) * 1.2 + 0.2)
        ax.legend(fontsize=7)
    fig.suptitle("Perpendicular cross-section width profiles (NOT area/length)")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "hk_width_profiles.png"), dpi=150)
    plt.close(fig)
    print("wrote figures/hk_{study_area,candidate_cells,width_profiles}.png")


if __name__ == "__main__":
    main()
