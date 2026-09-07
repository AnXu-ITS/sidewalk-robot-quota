# -*- coding: utf-8 -*-
"""
HK external test — GIS step 2b: select micro-cells + measure widths.

Method (documented):
  * Cells are extracted from real ground-level public footway polygons
    (CSDI INV_PG, FEAT_TYPE in {Footway, PTI-Footway, Carpark-Footway},
     LVL="Ground level").
  * Oriented minimum-rotated-rectangle gives the travel direction (long axis)
    and a straightness proxy rect_fill = polygon.area / (obb_len * obb_wid).
  * WIDTH is measured by PERPENDICULAR CROSS-SECTIONS along the long axis
    (centre-line normal profiles), NOT by area/length. width_min is the
    minimum cross-section over the central 80% of the segment (ends excluded),
    width_median the median.
  * sinuosity is computed from a raster medial-axis length / end-to-end distance.

Outputs: sites/hk_smoke_candidates.{gpkg,csv} and per-cell width profiles.
"""
import os

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.ndimage import distance_transform_edt
from shapely.geometry import LineString, Point, box

HERE = os.path.dirname(os.path.abspath(__file__))
PROC = os.path.join(HERE, "data", "processed")
SITES = os.path.join(HERE, "sites")
os.makedirs(SITES, exist_ok=True)

FOOTWAY_LABELS = {"Footway", "Public Transport Interchange - Footway",
                  "Carpark - Footway"}
GROUND = "Ground level"
STUDY = (836900.0, 826100.0, 838000.0, 827000.0)  # ~1.1km x 0.9km town centre


def obb(geom):
    """oriented bbox -> (length, width, center, u_axis, v_axis)."""
    r = geom.minimum_rotated_rectangle
    c = np.array(list(r.exterior.coords)[:4])
    v1, v2 = c[1] - c[0], c[2] - c[1]
    l1, l2 = np.hypot(*v1), np.hypot(*v2)
    if l1 >= l2:
        length, width = l1, l2
        u = v1 / l1
        v = v2 / l2
    else:
        length, width = l2, l1
        u = v2 / l2
        v = v1 / l1
    center = c[0] + 0.5 * (v1 + v2)
    return length, width, center, u, v


def cross_section_widths(geom, center, u, v, length, half_margin, step=0.5):
    """Width profile by perpendicular cross-sections along the long axis."""
    prof = []
    s = -length / 2.0
    while s <= length / 2.0 + 1e-6:
        p = center + s * u
        seg = LineString([p - (half_margin + 0.5) * v,
                          p + (half_margin + 0.5) * v])
        inter = geom.intersection(seg)
        w = inter.length if inter.geom_type == "LineString" else \
            (sum(part.length for part in inter.geoms)
             if hasattr(inter, "geoms") else 0.0)
        prof.append((s, w))
        s += step
    return prof


def medial_axis_sinuosity(geom, res=0.2):
    """Raster medial-axis length / end-to-end distance via EDT ridge."""
    minx, miny, maxx, maxy = geom.bounds
    nx = int(np.ceil((maxx - minx) / res)) + 2
    ny = int(np.ceil((maxy - miny) / res)) + 2
    # rasterize interior
    xs = np.linspace(minx - res, maxx + res, nx)
    ys = np.linspace(miny - res, maxy + res, ny)
    xx, yy = np.meshgrid(xs, ys)
    mask = np.zeros((ny, nx), dtype=bool)
    for i in range(ny):
        for j in range(nx):
            if geom.contains(Point(xx[i, j], yy[i, j])):
                mask[i, j] = True
    if mask.sum() < 10:
        return np.nan
    edt = distance_transform_edt(mask) * res
    # ridge: local max along the short axis is approximated by pixels whose EDT
    # is >= all 8 neighbours (skeleton ridge of the distance field)
    from scipy.ndimage import maximum_filter
    ridge = (edt >= maximum_filter(edt, size=3)) & mask
    # medial-axis length ~ number of ridge pixels * res (approx)
    return float(ridge.sum() * res)


def main():
    gdf = gpd.read_file(os.path.join(PROC, "hk_pavement_sha_tin_clip_hk1980.gpkg"))
    fw = gdf[(gdf["FEAT_TYPE"].isin(FOOTWAY_LABELS))
             & (gdf["LVL"] == GROUND)].copy()
    # restrict to study box
    sbox = box(*STUDY)
    fw = fw[fw.geometry.intersects(sbox)].copy()
    fw = fw[fw.geometry.area > 0]
    print("ground public footways intersecting study box:", len(fw))

    rows = []
    for _, r in fw.iterrows():
        g = r.geometry
        length, width, center, u, v = obb(g)
        area = g.area
        rect_fill = area / (length * width) if length * width > 0 else np.nan
        rows.append(dict(PG_UID=r["PG_UID"], FEAT_TYPE=r["FEAT_TYPE"],
                         SUR_TYPE_1=r["SUR_TYPE_1"], area_m2=area,
                         obb_length_m=length, obb_width_m=width,
                         rect_fill=rect_fill, cx=center[0], cy=center[1],
                         ux=u[0], uy=u[1], geometry=g))
    df = gpd.GeoDataFrame(rows, crs=fw.crs)

    # ---- classify straightness ------------------------------------------
    df["straight_flag"] = np.where(df["rect_fill"] >= 0.65, "straight",
                            np.where(df["rect_fill"] >= 0.40, "mild_curve",
                                     "complex"))

    # ---- candidates in-domain (obb width 1.6-3.0, length 20-80) ----------
    in_domain = df[(df["obb_width_m"] >= 1.6) & (df["obb_width_m"] <= 3.0)
                   & (df["obb_length_m"] >= 20) & (df["obb_length_m"] <= 80)]
    print("\nstraightness counts (study box):")
    print(df["straight_flag"].value_counts().to_string())
    print("\nin-domain-width candidates (obb width 1.6-3.0, len 20-80):",
          len(in_domain))
    print(in_domain[["PG_UID", "FEAT_TYPE", "obb_length_m", "obb_width_m",
                     "rect_fill", "straight_flag", "cx", "cy"]]
          .sort_values("rect_fill", ascending=False).head(30).to_string(index=False))

    # ---- width profiles for in-domain candidates --------------------------
    prof_rows = []
    for _, r in in_domain.iterrows():
        g = r.geometry
        length, width, center, u, v = obb(g)
        prof = cross_section_widths(g, center, u, v, length, width)
        ws = np.array([w for _, w in prof])
        core = [w for s, w in prof if abs(s) <= 0.4 * length]
        prof_rows.append(dict(
            PG_UID=r["PG_UID"], obb_length_m=length, obb_width_m=width,
            rect_fill=r["rect_fill"], straight_flag=r["straight_flag"],
            width_min_all=float(np.min(ws[ws > 0]) if (ws > 0).any() else np.nan),
            width_median=float(np.median(ws[ws > 0]) if (ws > 0).any() else np.nan),
            width_min_core=float(np.min(core) if core else np.nan),
            width_p10=float(np.percentile(ws[ws > 0], 10) if (ws > 0).any() else np.nan),
            n_sections=int(len(ws)),
        ))
    pdf = pd.DataFrame(prof_rows)
    pdf = pdf.sort_values("rect_fill", ascending=False)
    print("\nwidth profiles (in-domain candidates):")
    print(pdf.to_string(index=False))
    pdf.to_csv(os.path.join(SITES, "hk_smoke_candidates_width.csv"), index=False)
    print("\nwrote sites/hk_smoke_candidates_width.csv")


if __name__ == "__main__":
    main()
