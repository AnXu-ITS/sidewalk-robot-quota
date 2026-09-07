# -*- coding: utf-8 -*-
"""
HK external test — extract final micro-cells from real footway polygons.

For each selected cell:
  * oriented bbox -> long-axis direction -> straight centerline of length L
  * the REAL footway polygon is clipped to the [0, L] segment and exported in
    LOCAL metric coordinates (centerline along +x, start at origin) for SUMO,
    plus HK1980 and WGS84 for mapping.
  * width re-measured on the clipped segment via perpendicular cross-sections
    (width_min / width_median / width_p10), NOT area/length.

Outputs sites/hk_smoke_candidates.{gpkg,csv} + per-cell local geometry.
"""
import json
import math
import os

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Transformer
from shapely import affinity
from shapely.geometry import LineString, Polygon, box, mapping

HERE = os.path.dirname(os.path.abspath(__file__))
PROC = os.path.join(HERE, "data", "processed")
SITES = os.path.join(HERE, "sites")
os.makedirs(SITES, exist_ok=True)

TO_WGS84 = Transformer.from_crs("EPSG:2326", "EPSG:4326", always_xy=True)

# selected cells: (cell_id, PG_UID, L)
CELLS = [
    ("HK-ST-01", "PG4019702R0312", 50.0),  # straight, W~2.33
    ("HK-ST-02", "PG4019703R0312", 50.0),  # straight wider, W~2.65
    ("HK-ST-03", "PG4019765R0312", 35.0),  # complex (diagnostic, OOD)
]

# dataset metadata (from CSDI)
SOURCE_DATE = "2026-08-14"  # INV_PG modified_dt
SOURCE_CRS = "EPSG:2326"


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
        seg = LineString([p - (3.0) * v, p + (3.0) * v])
        inter = geom.intersection(seg)
        w = inter.length if inter.geom_type == "LineString" else \
            (sum(part.length for part in inter.geoms)
             if hasattr(inter, "geoms") else 0.0)
        prof.append((s, w))
        s += step
    return prof


def clip_to_segment(geom, center, u, length):
    """Clip polygon to a band of length L centered on `center` along u."""
    half = length / 2.0
    # rotate polygon so u -> +x, center -> origin, then cut [-half, half] in x
    ang = math.degrees(math.atan2(u[1], u[0]))
    g2 = affinity.translate(geom, -center[0], -center[1])
    g2 = affinity.rotate(g2, -ang, origin=(0, 0))
    band = box(-half, -100, half, 100)
    g3 = g2.intersection(band)
    return g3, ang


def main():
    clip = os.path.join(PROC, "hk_pavement_sha_tin_clip_hk1980.gpkg")
    gdf = gpd.read_file(clip)
    gdf = gdf.set_index("PG_UID")

    recs = []
    local_geoms = {}
    for cell_id, uid, L in CELLS:
        geom = gdf.loc[uid, "geometry"]
        length, width, u, v, center = obb_axis(geom)
        # centerline endpoints in HK1980
        p_start = center - u * (L / 2.0)
        p_end = center + u * (L / 2.0)
        # local coordinates: start at origin, along +x
        local_cl = [(0.0, 0.0), (L, 0.0)]
        # clipped real polygon in local coords (aligned to +x)
        clipped, ang = clip_to_segment(geom, center, u, L)
        # local polygon: start point -> origin
        local_poly = affinity.translate(clipped, L / 2.0, 0.0)
        # width profile on the clipped segment (in HK1980, before local shift)
        prof = cross_sections(geom, center, u, v, L)
        ws = np.array([w for _, w in prof])
        core = [w for s, w in prof if abs(s) <= 0.4 * L]
        ws_core = np.array([w for w in core if w > 0])
        w_min = float(ws_core.min()) if len(ws_core) else float("nan")
        w_med = float(np.median(ws_core)) if len(ws_core) else float("nan")
        w_p10 = float(np.percentile(ws_core, 10)) if len(ws_core) else float("nan")
        # sinuosity (straight centerline -> ~1.0; complex flag set separately)
        rect_fill = geom.area / (length * width)
        sinuosity = 1.0 if rect_fill >= 0.65 else round(length / math.hypot(
            *(np.array(p_end) - np.array(p_start))), 4)

        # WGS84 for mapping
        lon0, lat0 = TO_WGS84.transform(*p_start)
        lon1, lat1 = TO_WGS84.transform(*p_end)

        geometry_type = ("A" if rect_fill >= 0.65 else
                         "B" if rect_fill >= 0.40 else "C")
        app_status = ("in-domain" if (geometry_type in ("A", "B")
                                      and 1.6 <= w_med <= 3.0)
                      else "OOD/fallback")

        recs.append(dict(
            cell_id=cell_id, source_id=uid, city="hongkong", W=round(w_med, 3),
            L=L, qp=None, x=None,
            width_min=round(w_min, 3), width_median=round(w_med, 3),
            width_p10=round(w_p10, 3),
            width_method="perpendicular-cross-section (centerline normal)",
            geometry_type=geometry_type, sinuosity=sinuosity,
            rect_fill=round(rect_fill, 3),
            source_crs=SOURCE_CRS, source_date=SOURCE_DATE,
            applicability_status=app_status,
            x_hk1980=round(float(p_start[0]), 3),
            y_hk1980=round(float(p_start[1]), 3),
            lon0=round(lon0, 6), lat0=round(lat0, 6),
            lon1=round(lon1, 6), lat1=round(lat1, 6),
            centerline_local=json.dumps(local_cl),
        ))
        local_geoms[cell_id] = dict(
            centerline_local=local_cl,
            walkable_polygon_local=mapping(local_poly),
            centerline_hk1980=[list(p_start), list(p_end)],
            walkable_polygon_hk1980=mapping(geom),
            cell_polygon_hk1980=mapping(clipped),
        )

    recdf = pd.DataFrame(recs)
    # geometry for the gpkg = the clipped cell polygon in HK1980
    geom_col = [None] * len(recs)
    for i, r in recdf.iterrows():
        uid = r["source_id"]
        g = gdf.loc[uid, "geometry"]
        length, width, u, v, center = obb_axis(g)
        clipped, _ = clip_to_segment(g, center, u, r["L"])
        geom_col[i] = clipped
    gpd.GeoDataFrame(recdf, geometry=geom_col, crs="EPSG:2326").to_file(
        os.path.join(SITES, "hk_smoke_candidates.gpkg"), driver="GPKG",
        layer="candidate_cells")
    recdf.to_csv(os.path.join(SITES, "hk_smoke_candidates.csv"), index=False)

    with open(os.path.join(SITES, "hk_cell_local_geometry.json"), "w",
              encoding="utf-8") as f:
        json.dump(local_geoms, f, indent=2, ensure_ascii=False)

    print(recdf[["cell_id", "source_id", "W", "L", "width_min",
                 "width_median", "geometry_type", "sinuosity",
                 "applicability_status"]].to_string(index=False))
    print("\nwrote sites/hk_smoke_candidates.{gpkg,csv} and "
          "hk_cell_local_geometry.json")


if __name__ == "__main__":
    main()
