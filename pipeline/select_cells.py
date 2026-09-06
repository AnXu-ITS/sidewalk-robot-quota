# -*- coding: utf-8 -*-
"""
select_cells.py — stratified selection of cells from the 7-city candidate pool.

Per city: 20 main + 4 buffer cells, stratified by width:
  narrow (<1.6 m): 7 | mid (1.6-2.4): 7 | wide (2.4-3.5): 4 | xwide (>=3.5): 2
Constraints: cell_length >= 48 m (full 50 m cells only, L=50 consistency),
max 2 cells per source feature, deterministic seed=42.

Type flags (P1b semantics): C=narrow (W<1.6), B=curve (sinuosity>=1.02),
D=unavailable from sidewalk inventories (0), A=straight otherwise.

Output: pipeline/cells/selected_cells.json (P1b cells.json schema minus q_p;
q_p is added later by annotate_flow.py).
"""
import ijson
import json
import math
import os
import random
from collections import Counter, defaultdict

CELLS_DIR = r"C:\Users\xuan1\Desktop\UOL学习\配送机器人workbench\pipeline\cells"
OUT = os.path.join(CELLS_DIR, "selected_cells.json")

CITIES = ["nyc", "amsterdam", "melbourne", "taipei", "newtaipei",
          "seattle", "taoyuan"]
CITY_CODE = {"nyc": "NYC", "amsterdam": "AMS", "melbourne": "MEL",
             "taipei": "TPE", "newtaipei": "NTP", "seattle": "SEA",
             "taoyuan": "TAO"}
CITY_CN = {"nyc": "纽约", "amsterdam": "阿姆斯特丹", "melbourne": "墨尔本",
           "taipei": "台北", "newtaipei": "新北", "seattle": "西雅图",
           "taoyuan": "桃园"}
N_MAIN = 20
N_BUFFER = 4
BINS = [("<1.6", 0, 1.6, 7), ("1.6-2.4", 1.6, 2.4, 7),
        ("2.4-3.5", 2.4, 3.5, 4), (">=3.5", 3.5, 1e9, 2)]


def hav(a, b):
    R = 6371000.0
    p1, p2 = math.radians(a[1]), math.radians(b[1])
    dp = p2 - p1
    dl = math.radians(b[0] - a[0])
    x = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(min(1.0, x)))


def turns(pts):
    """cumulative and max turn angles in degrees along a polyline."""
    cum = 0.0
    mx = 0.0
    for i in range(1, len(pts) - 1):
        v1 = [pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]]
        v2 = [pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]]
        n1 = math.hypot(v1[0], v1[1])
        n2 = math.hypot(v2[0], v2[1])
        if n1 < 1e-12 or n2 < 1e-12:
            continue
        c = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)))
        a = math.degrees(math.acos(c))
        cum += a
        mx = max(mx, a)
    return cum, mx


def main():
    random.seed(42)
    all_sel = []
    report = []
    for city in CITIES:
        path = os.path.join(CELLS_DIR, f"cells_{city}.geojson")
        pool = defaultdict(list)  # bin -> list of features
        with open(path, "rb") as f:
            for feat in ijson.items(f, "features.item", use_float=True):
                pr = feat["properties"]
                g = feat.get("geometry")
                if g is None or pr.get("cell_length_m", 0) < 48:
                    continue
                wm = pr.get("width_m")
                if wm is None:
                    continue
                for bname, lo, hi, _ in BINS:
                    if lo <= wm < hi:
                        pool[bname].append((pr, g["coordinates"]))
                        break
        # dedupe by source feature: max 2 cells per source_id; per-bin quotas
        sel = []
        picked = Counter()
        used_src = Counter()
        QUOTA = {b: q for b, _, _, q in BINS}

        def try_pick(pr, coords, bname, spacing):
            if picked[bname] >= QUOTA[bname]:
                return False
            if used_src[pr.get("source_id")] >= 2:
                return False
            if spacing:
                lat0 = sum(p[1] for p in coords) / len(coords)
                lon0 = sum(p[0] for p in coords) / len(coords)
                if any(hav([lon0, lat0], [s["lon0"], s["lat0"]]) < spacing
                       for s in sel):
                    return False
            used_src[pr.get("source_id")] += 1
            lat0 = sum(p[1] for p in coords) / len(coords)
            lon0 = sum(p[0] for p in coords) / len(coords)
            picked[bname] += 1
            sel.append(dict(pr=pr, coords=coords, bin=bname,
                            lat0=lat0, lon0=lon0))
            return True

        for bname, lo, hi, quota in BINS:
            cand = pool[bname]
            random.shuffle(cand)
            for pr, coords in cand:
                if picked[bname] >= quota:
                    break
                try_pick(pr, coords, bname, spacing=100.0)
        # backfill any shortfall without the spacing constraint
        for bname, lo, hi, quota in BINS:
            if picked[bname] >= quota:
                continue
            cand = pool[bname]
            random.shuffle(cand)
            for pr, coords in cand:
                if picked[bname] >= quota:
                    break
                try_pick(pr, coords, bname, spacing=None)
        # main + buffer
        main = sel[:N_MAIN]
        buf = sel[N_MAIN:N_MAIN + N_BUFFER]
        for is_buf, group in ((False, main), (True, buf)):
            for s in group:
                pr, coords = s["pr"], s["coords"]
                cum, mx = turns(coords)
                sin = pr.get("sinuosity") or 1.0
                wm = pr.get("width_m")
                if wm < 1.6:
                    ctype, flags, ev = "C", (0, 0, 1, 0), "narrow_width"
                elif sin >= 1.02 or cum >= 30 or mx >= 20:
                    ctype, flags, ev = "B", (0, 1, 0, 0), f"curve(sin={sin})"
                else:
                    ctype, flags, ev = "A", (1, 0, 0, 0), "straight"
                mid = coords[len(coords) // 2]
                cell = {
                    "cell_id": f"{CITY_CODE[city]}-{pr['cell_id']}",
                    "city": city, "city_code": CITY_CODE[city],
                    "city_cn": CITY_CN[city],
                    "split": pr["split"],
                    "is_buffer": is_buf,
                    "width_bin": s["bin"],
                    "way_id": str(pr.get("source_id")),
                    "name": None,
                    "highway": None,
                    "type": ctype,
                    "type_a": flags[0], "type_b": flags[1],
                    "type_c": flags[2], "type_d": flags[3],
                    "context": None, "context_src": None,
                    "W_eff": wm, "W_lo": wm, "W_hi": wm,
                    "width_src": pr.get("width_source"),
                    "width_source_cn": None,
                    "q_p_peak": None, "q_p_off": None, "q_p_src": None,
                    "L": 50.0,
                    "centerline": coords,
                    "lat0": round(mid[1], 6), "lon0": round(mid[0], 6),
                    "sinuosity": sin,
                    "cum_turn_deg": round(cum, 1),
                    "max_turn_deg": round(mx, 1),
                    "n_barriers": 0, "n_crossings": 0,
                    "junc_deg_max": 0,
                    "evidence": ev,
                    "geom_approx": pr.get("geom_approx"),
                    "cell_length_m": pr.get("cell_length_m"),
                    "net_width_m": pr.get("net_width_m"),
                }
                all_sel.append(cell)
        got = Counter(x["bin"] for x in (main + buf))
        report.append(f"{city}: main={len(main)} buffer={len(buf)} "
                      f"bins={dict(got)}")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"cell_len": 50.0, "n": len(all_sel), "cells": all_sel},
                  f, ensure_ascii=False, indent=1)
    print("\n".join(report))
    by_city = Counter(c["city"] for c in all_sel)
    by_type = Counter(c["type"] for c in all_sel)
    print("total:", len(all_sel), "| cities:", dict(by_city))
    print("types:", dict(by_type))
    print("->", OUT)


if __name__ == "__main__":
    main()
