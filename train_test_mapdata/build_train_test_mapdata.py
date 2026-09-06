# -*- coding: utf-8 -*-
"""
Build unified training/test map dataset from the 5newcities sources.

Train: NYC, Melbourne (footpaths + road segments Footway), Amsterdam (BGT width edges),
       Taipei, New Taipei.
Test:  Seattle (official full export), Taoyuan.

Unified properties added to every feature:
  city          : english city key
  city_cn       : chinese name
  split         : train | test
  width_m       : sidewalk width in meters (primary target)
  net_width_m   : net width in meters (Taiwan NLMA only)
  width_source  : measured_official | derived_bgt | derived_area_perimeter | derived_planimetric
  width_qc      : 0=ok, 1=outlier, 2=zero/unimproved, 3=missing
  layer         : melbourne footpaths | melbourne roadseg_footway
  suitable      : 1=robot-suitable, 0=not (steps / removed assets)
Original source properties are preserved.
"""
import ijson
import json
import math
import os
import time
from collections import Counter

SRC = r"C:\Users\xuan1\Desktop\UOL学习\配送机器人workbench\5newcities"
TW = r"C:\Users\xuan1\Desktop\UOL学习\配送机器人workbench\sidewalk-robot-quota-main\sidewalk-robot-quota-main\external_bjsh\official_nlma\SIDEWALK_1_202412_WGS84.geojson"
OUT = r"C:\Users\xuan1\Desktop\UOL学习\配送机器人workbench\train_test_mapdata"

os.makedirs(OUT, exist_ok=True)

STATS = {}  # city_key -> dict


def haversine_perimeter(coords):
    """Sum of per-ring perimeters in meters (lon/lat degrees)."""
    rings = []

    def walk(o):
        if not isinstance(o, list):
            return
        if o and isinstance(o[0], list) and o[0] and isinstance(o[0][0], (int, float)):
            rings.append(o)
            return
        for x in o:
            walk(x)

    walk(coords)
    R = 6371000.0
    total = 0.0
    for pts in rings:
        if len(pts) < 3:
            continue
        n = len(pts)
        for i in range(n):
            lon1, lat1 = pts[i][0], pts[i][1]
            lon2, lat2 = pts[(i + 1) % n][0], pts[(i + 1) % n][1]
            p1, p2 = math.radians(lat1), math.radians(lat2)
            dp = p2 - p1
            dl = math.radians(lon2 - lon1)
            a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
            total += 2 * R * math.asin(math.sqrt(a))
    return total if total > 0 else None


class GeoWriter:
    def __init__(self, path, name):
        self.f = open(path, "w", encoding="utf-8")
        self.f.write('{\n"type":"FeatureCollection",\n"name":"%s",\n' % name)
        self.f.write('"crs":{"type":"name","properties":{"name":"urn:ogc:def:crs:OGC:1.3:CRS84"}},\n')
        self.f.write('"features":[\n')
        self.first = True

    def write(self, feat):
        if not self.first:
            self.f.write(",\n")
        self.first = False
        self.f.write(json.dumps(feat, ensure_ascii=False, separators=(",", ":")))

    def close(self):
        self.f.write("\n]\n}\n")
        self.f.close()


def stat_rec():
    return {"n": 0, "written": 0, "hard_dropped": 0, "geom": Counter(), "widths": [], "qc": Counter(), "null_geom": 0, "null_width": 0}


def make_feat(geom, props):
    feat = {"type": "Feature", "properties": props, "geometry": geom}
    return feat


def collect(st, w, qc):
    if w is None:
        st["null_width"] += 1
    else:
        st["widths"].append(w)
    st["qc"][qc] += 1


def finish_city(key, st, fname, name):
    w = sorted(st["widths"])
    m = len(w)
    q = {
        "n_features": st["written"],
        "geometry_types": dict(st["geom"]),
        "null_geometry": st["null_geom"],
        "null_width": st["null_width"],
        "width_n": m,
        "width_min": round(w[0], 3) if m else None,
        "width_p25": round(w[m // 4], 3) if m else None,
        "width_med": round(w[m // 2], 3) if m else None,
        "width_p75": round(w[3 * m // 4], 3) if m else None,
        "width_p90": round(w[9 * m // 10], 3) if m else None,
        "width_max": round(w[-1], 3) if m else None,
        "width_qc": dict(st["qc"]),
        "hard_dropped": st["hard_dropped"],
    }
    STATS[key] = q
    print(f"[{key}] {fname}: {json.dumps(q, ensure_ascii=False)}", flush=True)


# ---------------------------------------------------------------- NYC (train)
def do_nyc():
    key = "nyc"
    st = stat_rec()
    w = GeoWriter(os.path.join(OUT, "train_nyc.geojson"), "train_nyc")
    with open(os.path.join(SRC, "nyc_sidewalkwidths.geojson"), "rb") as f:
        for feat in ijson.items(f, "features.item", use_float=True):
            pr = dict(feat.get("properties") or {})
            g = feat.get("geometry")
            st["n"] += 1
            if g is None:
                st["null_geom"] += 1
                continue
            st["geom"][g.get("type")] += 1
            ft = pr.get("width")
            if ft is None:
                wm, qc = None, 3
            else:
                wm = round(ft * 0.3048, 3)
                qc = 1 if (ft > 60 or ft < 0.5) else 0
            collect(st, wm, qc)
            pr.update(city="nyc", city_cn="纽约", split="train",
                      width_m=wm, net_width_m=None,
                      width_source="derived_planimetric", width_qc=qc,
                      suitable=1, layer=None)
            st["written"] += 1
            w.write(make_feat(g, pr))
    w.close()
    finish_city(key, st, "train_nyc.geojson", "train_nyc")


# ---------------------------------------------------------------- Seattle (test)
def do_seattle():
    key = "seattle"
    st = stat_rec()
    w = GeoWriter(os.path.join(OUT, "test_seattle.geojson"), "test_seattle")
    skipped_status = Counter()
    with open(os.path.join(SRC, "seattle_sdot_sidewalks.geojson"), "rb") as f:
        for feat in ijson.items(f, "features.item", use_float=True):
            pr = dict(feat.get("properties") or {})
            st["n"] += 1
            status = pr.get("CURRENT_STATUS")
            if status not in ("INSVC", "PLNRECON"):
                skipped_status[str(status)] += 1
                continue
            g = feat.get("geometry")
            if g is None:
                st["null_geom"] += 1
                continue
            st["geom"][g.get("type")] += 1
            sw = pr.get("SW_WIDTH")
            fw_ = pr.get("FILLERWID")
            if sw is None:
                wm, qc = None, 3
            else:
                wm = round(sw * 0.0254, 3)
                qc = 2 if sw == 0 else (1 if sw > 240 else 0)
            filler = round(fw_ * 0.0254, 3) if isinstance(fw_, (int, float)) else None
            collect(st, wm, qc)
            pr.update(city="seattle", city_cn="西雅图", split="test",
                      width_m=wm, net_width_m=None,
                      width_source="measured_official", width_qc=qc,
                      filler_width_m=filler, suitable=1, layer=None)
            st["written"] += 1
            w.write(make_feat(g, pr))
    w.close()
    print(f"[seattle] skipped by CURRENT_STATUS: {dict(skipped_status)}", flush=True)
    finish_city(key, st, "test_seattle.geojson", "test_seattle")


# ---------------------------------------------------------------- Amsterdam (train)
AMS_KEEP = {"bgt_voetpad", "bgt_voetpad op trap", "bgt_voetgangersgebied", "bgt_inrit"}


def do_amsterdam():
    key = "amsterdam"
    st = stat_rec()
    w = GeoWriter(os.path.join(OUT, "train_amsterdam.geojson"), "train_amsterdam")
    skipped = Counter()
    with open(os.path.join(SRC, "amsterdam_loopfietsnetwerk_edges.geojson"), "rb") as f:
        for feat in ijson.items(f, "features.item", use_float=True):
            pr = dict(feat.get("properties") or {})
            st["n"] += 1
            klasse = pr.get("wegklasse")
            ww = pr.get("gewogenGemiddeldeBreedte")
            if klasse not in AMS_KEEP or ww is None or ww <= 0:
                skipped[str((klasse, ww is None))] += 1
                continue
            g = feat.get("geometry")
            if g is None:
                st["null_geom"] += 1
                continue
            st["geom"][g.get("type")] += 1
            wm = round(float(ww), 3)
            collect(st, wm, 1 if (wm > 12 or wm < 0.5) else 0)
            pr.update(city="amsterdam", city_cn="阿姆斯特丹", split="train",
                      width_m=wm, net_width_m=None,
                      width_source="derived_bgt", width_qc=(1 if (wm > 12 or wm < 0.5) else 0),
                      suitable=(0 if "op trap" in klasse else 1), layer=None)
            st["written"] += 1
            w.write(make_feat(g, pr))
    w.close()
    print(f"[amsterdam] skipped edges: {dict(skipped)}", flush=True)
    finish_city(key, st, "train_amsterdam.geojson", "train_amsterdam")


# ---------------------------------------------------------------- Melbourne (train, two layers)
def do_melbourne():
    key = "melbourne"
    st = stat_rec()
    w = GeoWriter(os.path.join(OUT, "train_melbourne.geojson"), "train_melbourne")

    # layer 1: footpaths polygons
    with open(os.path.join(SRC, "melbourne_footpaths.geojson"), "rb") as f:
        for feat in ijson.items(f, "features.item", use_float=True):
            pr = dict(feat.get("properties") or {})
            at = pr.get("asset_type")
            if at not in ("Road Footway", "Road Fotway"):
                continue
            st["n"] += 1
            g = feat.get("geometry")
            if g is None:
                st["null_geom"] += 1
                continue
            st["geom"][g.get("type")] += 1
            area = pr.get("shape_star")
            per = haversine_perimeter(g.get("coordinates")) if g.get("coordinates") else None
            if area is None or per is None:
                wm, qc = None, 3
            else:
                wm = round(2 * float(area) / per, 3)
                qc = 1 if (wm < 0.2 or wm > 10) else 0
            collect(st, wm, qc)
            pr.update(city="melbourne", city_cn="墨尔本", split="train",
                      width_m=wm, net_width_m=None,
                      width_source="derived_area_perimeter", width_qc=qc,
                      suitable=1, layer="footpaths")
            st["written"] += 1
            w.write(make_feat(g, pr))

    # layer 2: road segments Footway
    with open(os.path.join(SRC, "melbourne_road_segments_surface_type.geojson"), "rb") as f:
        for feat in ijson.items(f, "features.item", use_float=True):
            pr = dict(feat.get("properties") or {})
            if pr.get("type") != "Footway":
                continue
            st["n"] += 1
            g = feat.get("geometry")
            if g is None:
                st["null_geom"] += 1
                continue
            st["geom"][g.get("type")] += 1
            area = pr.get("area_sqm")
            per = haversine_perimeter(g.get("coordinates")) if g.get("coordinates") else None
            if area is None or per is None:
                wm, qc = None, 3
            else:
                wm = round(2 * float(area) / per, 3)
                qc = 1 if (wm < 0.2 or wm > 10) else 0
            collect(st, wm, qc)
            pr.update(city="melbourne", city_cn="墨尔本", split="train",
                      width_m=wm, net_width_m=None,
                      width_source="derived_area_perimeter", width_qc=qc,
                      suitable=1, layer="roadseg_footway")
            st["written"] += 1
            w.write(make_feat(g, pr))
    w.close()
    finish_city(key, st, "train_melbourne.geojson", "train_melbourne")


# ---------------------------------------------------------------- Taiwan NLMA (3 cities)
TW_MAP = {
    "台北市": ("taipei", "台北", "train", "train_taipei.geojson"),
    "新北市": ("newtaipei", "新北", "train", "train_newtaipei.geojson"),
    "桃園市": ("taoyuan", "桃园", "test", "test_taoyuan.geojson"),
}


def do_taiwan():
    stats = {}
    writers = {}
    for cy, (key, ccn, split, fname) in TW_MAP.items():
        stats[key] = stat_rec()
        writers[key] = GeoWriter(os.path.join(OUT, fname), fname[:-8])
    with open(TW, "rb") as f:
        for feat in ijson.items(f, "features.item", use_float=True):
            pr = dict(feat.get("properties") or {})
            cy = pr.get("COUNTY_NA")
            if cy not in TW_MAP:
                continue
            key, ccn, split, _ = TW_MAP[cy]
            st = stats[key]
            st["n"] += 1
            wth = pr.get("SW_WTH")
            sww = pr.get("SWW_WTH")
            if wth is not None and float(wth) > 60:
                st["hard_dropped"] += 1
                continue
            g = feat.get("geometry")
            if g is None:
                st["null_geom"] += 1
                continue
            st["geom"][g.get("type")] += 1
            wm = round(float(wth), 3) if wth is not None else None
            nm = round(float(sww), 3) if sww is not None else None
            qc = 3 if wm is None else (1 if wm > 8 else 0)
            collect(st, wm, qc)
            pr.update(city=key, city_cn=ccn, split=split,
                      width_m=wm, net_width_m=nm,
                      width_source="measured_official", width_qc=qc,
                      suitable=1, layer=None)
            st["written"] += 1
            writers[key].write(make_feat(g, pr))
    for cy, (key, ccn, split, fname) in TW_MAP.items():
        writers[key].close()
        finish_city(key, stats[key], fname, fname[:-8])


# ---------------------------------------------------------------- combined files
def combine(keys, out_name):
    w = GeoWriter(os.path.join(OUT, out_name), out_name[:-8])
    for key in keys:
        fname = {"nyc": "train_nyc.geojson", "amsterdam": "train_amsterdam.geojson",
                 "melbourne": "train_melbourne.geojson", "taipei": "train_taipei.geojson",
                 "newtaipei": "train_newtaipei.geojson", "seattle": "test_seattle.geojson",
                 "taoyuan": "test_taoyuan.geojson"}[key]
        with open(os.path.join(OUT, fname), "rb") as f:
            for feat in ijson.items(f, "features.item", use_float=True):
                w.write(feat)
    w.close()


def main():
    t0 = time.time()
    do_nyc()
    do_seattle()
    do_amsterdam()
    do_melbourne()
    do_taiwan()
    combine(["nyc", "amsterdam", "melbourne", "taipei", "newtaipei"], "train_all.geojson")
    combine(["seattle", "taoyuan"], "test_all.geojson")

    # manifest.csv
    with open(os.path.join(OUT, "manifest.csv"), "w", encoding="utf-8") as f:
        f.write("city,file,split,geometry,n_features,null_width,width_n,min,p25,med,p75,p90,max,qc_ok,qc_outlier,qc_zero,qc_missing\n")
        for key, q in STATS.items():
            fname = {"nyc": "train_nyc.geojson", "amsterdam": "train_amsterdam.geojson",
                     "melbourne": "train_melbourne.geojson", "taipei": "train_taipei.geojson",
                     "newtaipei": "train_newtaipei.geojson", "seattle": "test_seattle.geojson",
                     "taoyuan": "test_taoyuan.geojson"}[key]
            f.write(f"{key},{fname},{'train' if key in ('nyc','amsterdam','melbourne','taipei','newtaipei') else 'test'},"
                    f"{q['geometry_types']},{q['n_features']},{q['null_width']},{q['width_n']},"
                    f"{q['width_min']},{q['width_p25']},{q['width_med']},{q['width_p75']},{q['width_p90']},{q['width_max']},"
                    f"{q['width_qc'].get(0,0)},{q['width_qc'].get(1,0)},{q['width_qc'].get(2,0)},{q['width_qc'].get(3,0)}\n")
    print(f"ALL DONE in {time.time()-t0:.0f}s -> {OUT}")


if __name__ == "__main__":
    main()
