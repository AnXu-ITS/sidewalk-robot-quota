# -*- coding: utf-8 -*-
"""Section 3 — formal sample freeze: select ~32 cells across width/geometry,
extract real centerline + real polygon + width profile, write the frozen sample
CSV + local geometry + map + hash. Deterministic (no result-dependent pruning)."""
import hashlib
import json
import os

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from shapely.affinity import rotate, translate
from shapely.geometry import LineString, Polygon, box, mapping
from shapely.ops import unary_union

from hk_centerline import (extract_centerline, obb_axis, obb_cross_widths)

HERE = os.path.dirname(os.path.abspath(__file__))
PROC = os.path.join(HERE, "data", "processed")
SITES = os.path.join(HERE, "sites")
FIG = os.path.join(HERE, "figures")
os.makedirs(SITES, exist_ok=True)
os.makedirs(FIG, exist_ok=True)

L_TARGET = 50.0          # frozen corridor length
MIN_ARC = 35.0           # minimum extractable cell length (measure zone 15-35)
SOURCE_CRS = "EPSG:2326"
SOURCE_DATE = "2026-08-14"

# selection targets: (label, [lo, hi], n, in_domain_bool)
BINS = [
    ("ood_narrow", [1.2, 1.6], 4, False),
    ("narrow", [1.6, 2.0], 7, True),
    ("mid", [2.0, 2.4], 9, True),
    ("wide", [2.4, 3.0], 10, True),
    ("ood_wide", [3.0, 3.5], 2, False),
]


def gtype(rf):
    return "A" if rf >= 0.65 else ("B" if rf >= 0.40 else "C")


def main():
    gdf = gpd.read_file(os.path.join(PROC, "hk_pavement_sha_tin_clip_hk1980.gpkg"))
    pool = pd.read_csv(os.path.join(SITES, "hk_formal_pool_cw.csv"))
    pool = pool[pool["obb_len"] >= MIN_ARC].copy()
    pool["gtype"] = pool["rect_fill"].apply(gtype)

    selected = []
    for label, (lo, hi), n, indom in BINS:
        sub = pool[(pool["cw_median"] >= lo) & (pool["cw_median"] < hi)].copy()
        # deterministic stratified sample: sort by width, spread across gtype
        sub = sub.sort_values(["cw_median", "rect_fill"], ascending=[True, False])
        if len(sub) == 0:
            print(f"[{label}] empty bin")
            continue
        # interleave gtypes: take a balanced mix (deterministic)
        a = list(sub[sub.gtype == "A"].to_dict("records"))
        b = list(sub[sub.gtype == "B"].to_dict("records"))
        c = list(sub[sub.gtype == "C"].to_dict("records"))
        picks = []
        while len(picks) < n and (a or b or c):
            for grp in (a, b, c):
                if grp and len(picks) < n:
                    picks.append(grp.pop(0))
        for r in picks:
            selected.append(dict(PG_UID=r["PG_UID"], label=label,
                                 in_domain=indom, rect_fill=r["rect_fill"]))
        print(f"[{label}] target {n}, got {len(picks)} "
              f"(A={sum(1 for p in picks if p['gtype']=='A')}, "
              f"B={sum(1 for p in picks if p['gtype']=='B')}, "
              f"C={sum(1 for p in picks if p['gtype']=='C')})")

    # dedup by PG_UID (a long footway should not appear twice)
    seen = set()
    sel_uniq = []
    for s in selected:
        if s["PG_UID"] not in seen:
            seen.add(s["PG_UID"])
            sel_uniq.append(s)
    print("\ntotal selected cells:", len(sel_uniq))

    # ---- extract each cell ----
    recs = []
    local_geoms = {}
    idx = gdf.set_index("PG_UID")
    for i, s in enumerate(sel_uniq, 1):
        uid = s["PG_UID"]
        geom = idx.loc[uid, "geometry"]
        length, obb_w, u, v, center = obb_axis(geom)
        # sinuosity + turn metrics from the midpoint centerline (gate inputs)
        cl, arc, chord = extract_centerline(geom, step=0.5)
        sinuosity = arc / chord if chord > 0 else 1.0
        cla = np.array(cl)
        dxy = np.diff(cla, axis=0)
        angs = np.degrees(np.arctan2(dxy[:, 1], dxy[:, 0]))
        dangs = np.abs(np.diff(angs))
        dangs = np.minimum(dangs, 360.0 - dangs)
        max_turn = float(np.max(dangs)) if len(dangs) else 0.0
        cum_turn = float(np.sum(dangs)) if len(dangs) else 0.0
        # segment along the OBB long axis (central L_TARGET or full if shorter)
        L_seg = min(L_TARGET, length)
        s0, s1 = -L_seg / 2.0, L_seg / 2.0
        # width profile perpendicular to u over the segment
        prof_s, prof_w = obb_cross_widths(geom, step=0.5)
        segw = [w for ss, w in zip(prof_s, prof_w)
                if s0 <= ss <= s1 and w > 0.05]
        W_med = float(np.median(segw)) if segw else 0.0
        W_p10 = float(np.percentile(segw, 10)) if segw else 0.0
        # clip the REAL polygon to a straight band around the axis
        band_half = max(W_med + 1.5, 2.5)
        rect = Polygon([
            center + s0 * u - band_half * v,
            center + s1 * u - band_half * v,
            center + s1 * u + band_half * v,
            center + s0 * u + band_half * v,
        ])
        cell_poly = geom.intersection(rect)
        if cell_poly.is_empty or cell_poly.area < 5.0:
            print(f"  [skip {uid}] clip empty")
            continue
        # keep the largest polygon part (drop stray spurs)
        if cell_poly.geom_type == "MultiPolygon":
            cell_poly = max(cell_poly.geoms, key=lambda g: g.area)
        # local transform: axis start -> origin, u -> +x (straight OBB axis).
        # NOTE: for tapered/wedge footways the OBB axis deviates from the true
        # cross-section centre at the ends; such cells are detected by the
        # spawn-integrity check (inflow==0 / inflow<<expected) and excluded from
        # the sweep with a documented geometry-method finding (see fix history).
        ang = float(np.degrees(np.arctan2(u[1], u[0])))
        p0 = center + s0 * u
        cell_local = rotate(translate(cell_poly, -p0[0], -p0[1]), -ang,
                            origin=(0, 0))
        cl_local = [[0.0, 0.0], [round(L_seg, 2), 0.0]]
        # frozen applicability gate (geometry-level; x/qp gate applied per combo)
        rf2 = float(s.get("rect_fill", 0.0))
        gt = gtype(rf2)
        W_ok = (1.6 <= W_med <= 3.0)
        type_ok = gt in ("A", "B")
        sinu_ok = (gt != "B") or (sinuosity <= 1.05)
        geom_applicable = bool(W_ok and type_ok and sinu_ok)
        if W_med < 1.6:
            wlabel = "narrow_OOD"
        elif W_med <= 2.0:
            wlabel = "narrow"
        elif W_med <= 2.4:
            wlabel = "mid"
        elif W_med <= 3.0:
            wlabel = "wide"
        else:
            wlabel = "wide_OOD"
        cell_id = f"HK-ST-{i:02d}"
        recs.append(dict(
            cell_id=cell_id, source_id=uid, city="hongkong",
            W=round(W_med, 3), L=round(L_seg, 2),
            width_p10=round(W_p10, 3), width_median=round(W_med, 3),
            width_method="perpendicular-cross-section (OBB long axis)",
            geometry_type=gt, sinuosity=round(sinuosity, 4),
            max_turn_deg=round(max_turn, 2), cum_turn_deg=round(cum_turn, 2),
            rect_fill=round(rf2, 3), source_crs=SOURCE_CRS,
            source_date=SOURCE_DATE, label=wlabel,
            W_in_domain=bool(W_ok),
            applicability_status=("in-domain" if geom_applicable
                                  else "OOD/fallback"),
            arc_len=round(arc, 2), chord_len=round(chord, 2),
        ))
        local_geoms[cell_id] = dict(
            source_id=uid, L=round(L_seg, 2), centerline_local=cl_local,
            walkable_polygon_local=mapping(cell_local),
        )

    recdf = pd.DataFrame(recs)
    recdf.to_csv(os.path.join(SITES, "HONG_KONG_FORMAL_SAMPLE_FREEZE.csv"),
                 index=False)
    with open(os.path.join(SITES, "hk_formal_local_geometry.json"), "w",
              encoding="utf-8") as f:
        json.dump(local_geoms, f, indent=2, ensure_ascii=False)

    # hash the freeze CSV
    h = hashlib.sha256()
    with open(os.path.join(SITES, "HONG_KONG_FORMAL_SAMPLE_FREEZE.csv"), "rb") as f:
        h.update(f.read())
    freeze_sha = h.hexdigest().upper()

    print("\n=== sample summary ===")
    print(recdf.groupby(["label", "geometry_type"]).size().to_string())
    print("\nW distribution by label:")
    print(recdf.groupby("label")["W"].agg(["count", "min", "median", "max"]).to_string())
    print("\nfreeze CSV SHA-256:", freeze_sha)

    # ---- sample map ----
    fig, ax = plt.subplots(figsize=(11, 8))
    clip_g = gpd.read_file(os.path.join(PROC, "hk_pavement_sha_tin_clip_hk1980.gpkg"))
    clip_g[clip_g["FEAT_TYPE"] == "Footway"].plot(ax=ax, color="#cccccc", linewidth=0.1)
    sel_uids = [r["source_id"] for r in recdf.to_dict("records")]
    sel_g = gdf[gdf["PG_UID"].isin(sel_uids)]
    sel_g.plot(ax=ax, facecolor="red", alpha=0.35, edgecolor="red", linewidth=0.6)
    ax.set_aspect("equal")
    ax.set_title(f"HK formal external-test sample ({len(recdf)} cells)")
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "hk_formal_sample_map.png"), dpi=150)
    plt.close(fig)

    with open(os.path.join(SITES, "hk_formal_sample_freeze_meta.json"), "w",
              encoding="utf-8") as f:
        json.dump(dict(n_cells=len(recdf), freeze_csv_sha256=freeze_sha,
                       target=sum(b[2] for b in BINS),
                       bins=[dict(label=b[0], lo=b[1][0], hi=b[1][1],
                                  target=b[2], in_domain=b[3]) for b in BINS]),
                  f, indent=2, ensure_ascii=False)
    print("wrote HONG_KONG_FORMAL_SAMPLE_FREEZE.csv, hk_formal_local_geometry.json, "
          "hk_formal_sample_map.png")


if __name__ == "__main__":
    main()
