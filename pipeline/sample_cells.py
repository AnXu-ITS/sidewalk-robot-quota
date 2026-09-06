# -*- coding: utf-8 -*-
"""
sample_cells.py — 7-city real sidewalk cell candidate sampler.

Converts train_test_mapdata into ~50 m cell candidates (centerline polylines +
real width) for the quota ground-truth simulation.

Line cities  (NYC / Amsterdam / Seattle): split each line into 50 m cells along
             the geometry (exact geometry), tail kept if >= 40 m.
Polygon cities (Melbourne / Taipei / New Taipei / Taoyuan): take the longest
             chord of the convex hull as a provisional cell axis, split into
             50 m cells. Marked geom_approx='chord' (candidate-level geometry;
             final cell geometry should be refined from the polygon itself).

Filters: width_qc == 0 AND suitable == 1 AND width_m not null AND geometry ok.

Outputs (pipeline/cells/):
  cells_<city>.geojson            cell candidates (LineString)
  cells_candidates_summary.csv    per-city coverage vs width strata
"""
import ijson
import json
import math
import os
import time
from collections import Counter, defaultdict

MAP = r"C:\Users\xuan1\Desktop\UOL学习\配送机器人workbench\train_test_mapdata"
OUT = r"C:\Users\xuan1\Desktop\UOL学习\配送机器人workbench\pipeline\cells"
os.makedirs(OUT, exist_ok=True)

CELL_LEN = 50.0      # m, matches SIM["L"]
MIN_TAIL = 40.0      # m, minimum cell length to keep

LINE_CITIES = {
    "nyc": ("train_nyc.geojson", "train"),
    "amsterdam": ("train_amsterdam.geojson", "train"),
    "seattle": ("test_seattle.geojson", "test"),
}
POLY_CITIES = {
    "melbourne": ("train_melbourne.geojson", "train"),
    "taipei": ("train_taipei.geojson", "train"),
    "newtaipei": ("train_newtaipei.geojson", "train"),
    "taoyuan": ("test_taoyuan.geojson", "test"),
}
CN = {"nyc": "纽约", "amsterdam": "阿姆斯特丹", "seattle": "西雅图",
      "melbourne": "墨尔本", "taipei": "台北", "newtaipei": "新北", "taoyuan": "桃园"}


def hav(a, b):
    R = 6371000.0
    p1, p2 = math.radians(a[1]), math.radians(b[1])
    dp = p2 - p1
    dl = math.radians(b[0] - a[0])
    x = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(min(1.0, x)))


def cumdist(pts):
    d = [0.0]
    for i in range(1, len(pts)):
        d.append(d[-1] + hav(pts[i - 1], pts[i]))
    return d


def interp(pts, d, t):
    """Point at distance t along polyline pts (cumulative distances d)."""
    for i in range(len(d) - 1):
        if d[i + 1] >= t:
            if d[i + 1] - d[i] < 1e-12:
                return pts[i]
            f = (t - d[i]) / (d[i + 1] - d[i])
            return [pts[i][0] + f * (pts[i + 1][0] - pts[i][0]),
                    pts[i][1] + f * (pts[i + 1][1] - pts[i][1])]
    return pts[-1]


def slice_polyline(pts, d, t0, t1):
    """Sub-polyline from t0 to t1."""
    sub = [interp(pts, d, t0)]
    for i in range(1, len(pts)):
        if t0 < d[i] < t1:
            sub.append(pts[i])
    sub.append(interp(pts, d, t1))
    return sub


def split_line(pts, cell=CELL_LEN, min_tail=MIN_TAIL):
    """Split a polyline into EXACTLY `cell` m cells; short tails are dropped
    (the SUMO driver uses fixed L=50, so cell length must be exactly 50 m)."""
    d = cumdist(pts)
    total = d[-1]
    n = int(total // cell)
    cells = []
    for i in range(n):
        t0 = i * cell
        t1 = t0 + cell
        cells.append((slice_polyline(pts, d, t0, t1), t1 - t0))
    return cells


def hull_diameter(rings_pts):
    """Longest vertex pair of the convex hull (lon/lat), as (p1, p2, dist)."""
    try:
        from scipy.spatial import ConvexHull
    except ImportError:
        ConvexHull = None
    pts = []
    for ring in rings_pts:
        pts.extend(ring)
    if len(pts) < 3:
        return None
    hull_pts = pts
    if ConvexHull is not None:
        try:
            h = ConvexHull(pts)
            hull_pts = [pts[i] for i in h.vertices]
        except Exception:
            hull_pts = pts
    if len(hull_pts) > 500:  # stride-sample to cap O(n^2)
        step = len(hull_pts) // 500 + 1
        hull_pts = hull_pts[::step]
    best = None
    n = len(hull_pts)
    for i in range(n):
        for j in range(i + 1, n):
            dd = hav(hull_pts[i], hull_pts[j])
            if best is None or dd > best[2]:
                best = (hull_pts[i], hull_pts[j], dd)
    return best


def rings_of(coords):
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
    return rings


class CellWriter:
    def __init__(self, path):
        self.f = open(path, "w", encoding="utf-8")
        self.f.write('{"type":"FeatureCollection","crs":{"type":"name","properties":'
                     '{"name":"urn:ogc:def:crs:OGC:1.3:CRS84"}},"features":[\n')
        self.first = True
        self.n = 0

    def write(self, props, sub):
        feat = {"type": "Feature", "properties": props,
                "geometry": {"type": "LineString", "coordinates": sub}}
        if not self.first:
            self.f.write(",\n")
        self.first = False
        self.n += 1
        self.f.write(json.dumps(feat, ensure_ascii=False, separators=(",", ":")))

    def close(self):
        self.f.write("\n]}\n")
        self.f.close()


def chord_of(sub):
    return hav(sub[0], sub[-1]) if len(sub) >= 2 else 0.0


def ok_feature(pr):
    return (pr.get("width_qc") == 0 and pr.get("suitable") == 1
            and pr.get("width_m") is not None)


def process_line_city(city, fname, split, summary):
    src = os.path.join(MAP, fname)
    w = CellWriter(os.path.join(OUT, f"cells_{city}.geojson"))
    n_src = 0
    n_cells = 0
    km = 0.0
    bins = Counter()
    t0 = time.time()
    with open(src, "rb") as f:
        for feat in ijson.items(f, "features.item", use_float=True):
            pr = feat.get("properties") or {}
            if not ok_feature(pr):
                continue
            g = feat.get("geometry")
            if g is None:
                continue
            n_src += 1
            src_id = pr.get("OBJECTID") or pr.get("objectid") or pr.get("id")
            lines = []
            if g.get("type") == "LineString":
                lines = [g["coordinates"]]
            elif g.get("type") == "MultiLineString":
                lines = g["coordinates"]
            else:
                continue
            for li, line in enumerate(lines):
                if len(line) < 2:
                    continue
                for si, (sub, ln) in enumerate(split_line(line)):
                    cid = f"{city}-{src_id}-{li}-{si}"
                    chord = chord_of(sub)
                    sin = round(ln / chord, 4) if chord > 0 else None
                    props = {
                        "city": city, "city_cn": CN[city], "split": split,
                        "cell_id": cid, "width_m": pr.get("width_m"),
                        "net_width_m": pr.get("net_width_m"),
                        "width_source": pr.get("width_source"),
                        "layer": pr.get("layer"), "source_id": src_id,
                        "orig_geom": g.get("type"),
                        "cell_length_m": round(ln, 2),
                        "sinuosity": sin, "geom_approx": "exact",
                    }
                    w.write(props, sub)
                    n_cells += 1
                    km += ln
                    wm = pr.get("width_m")
                    if wm < 1.6:
                        bins["<1.6"] += 1
                    elif wm < 2.4:
                        bins["1.6-2.4"] += 1
                    elif wm < 3.5:
                        bins["2.4-3.5"] += 1
                    else:
                        bins[">=3.5"] += 1
    w.close()
    summary[city] = dict(split=split, approx="exact", n_cells=n_cells,
                         n_src=n_src, km=round(km / 1000, 2), bins=dict(bins))
    print(f"[{city}] src={n_src} cells={n_cells} km={km/1000:.1f} "
          f"bins={dict(bins)} {time.time()-t0:.0f}s", flush=True)


def process_poly_city(city, fname, split, summary):
    src = os.path.join(MAP, fname)
    w = CellWriter(os.path.join(OUT, f"cells_{city}.geojson"))
    n_src = 0
    n_skip_small = 0
    n_cells = 0
    km = 0.0
    bins = Counter()
    feat_i = 0
    t0 = time.time()
    with open(src, "rb") as f:
        for feat in ijson.items(f, "features.item", use_float=True):
            feat_i += 1
            pr = feat.get("properties") or {}
            if not ok_feature(pr):
                continue
            g = feat.get("geometry")
            if g is None:
                continue
            n_src += 1
            src_id = pr.get("OBJECTID") or pr.get("objectid") or pr.get("id") \
                or pr.get("ext_id") or pr.get("assetno") or f"idx{feat_i}"
            rings = rings_of(g.get("coordinates"))
            dia = hull_diameter(rings)
            if dia is None or dia[2] < MIN_TAIL:
                n_skip_small += 1
                continue
            p1, p2, _ = dia
            for si, (sub, ln) in enumerate(split_line([p1, p2])):
                cid = f"{city}-{src_id}-0-{si}"
                props = {
                    "city": city, "city_cn": CN[city], "split": split,
                    "cell_id": cid, "width_m": pr.get("width_m"),
                    "net_width_m": pr.get("net_width_m"),
                    "width_source": pr.get("width_source"),
                    "layer": pr.get("layer"), "source_id": src_id,
                    "orig_geom": g.get("type"),
                    "cell_length_m": round(ln, 2),
                    "sinuosity": 1.0, "geom_approx": "chord",
                }
                w.write(props, sub)
                n_cells += 1
                km += ln
                wm = pr.get("width_m")
                if wm < 1.6:
                    bins["<1.6"] += 1
                elif wm < 2.4:
                    bins["1.6-2.4"] += 1
                elif wm < 3.5:
                    bins["2.4-3.5"] += 1
                else:
                    bins[">=3.5"] += 1
    w.close()
    summary[city] = dict(split=split, approx="chord", n_cells=n_cells,
                         n_src=n_src, n_skip_small=n_skip_small,
                         km=round(km / 1000, 2), bins=dict(bins))
    print(f"[{city}] src={n_src} skip_small={n_skip_small} cells={n_cells} "
          f"km={km/1000:.1f} bins={dict(bins)} {time.time()-t0:.0f}s", flush=True)


# ---------------------------------------------------------------- Amsterdam chained
def process_amsterdam_chained(summary):
    """Amsterdam BGT edges are tiny (~1.4 m avg): chain consecutive edges via
    startNodeId/endNodeId (prefer straight continuation, turn <= 60 deg) into
    >= 40 m paths, then split into 50 m cells. Cell width = length-weighted
    mean of member edges. geom_approx = 'chained'."""
    city = "amsterdam"
    src = os.path.join(MAP, "train_amsterdam.geojson")
    edges = []
    adj = defaultdict(list)
    t0 = time.time()
    with open(src, "rb") as f:
        for feat in ijson.items(f, "features.item", use_float=True):
            pr = feat.get("properties") or {}
            if not ok_feature(pr):
                continue
            g = feat.get("geometry")
            if g is None:
                continue
            pts = g.get("coordinates")
            if not isinstance(pts, list) or len(pts) < 2:
                continue
            eid = len(edges)
            edges.append((pr, pts))
            a = pr.get("startNodeId")
            b = pr.get("endNodeId")
            if a is not None:
                adj[a].append(eid)
            if b is not None:
                adj[b].append(eid)
    print(f"[amsterdam] loaded {len(edges)} edges, {len(adj)} nodes, "
          f"{time.time()-t0:.0f}s", flush=True)

    used = [False] * len(edges)

    def dir_in(pts):
        return [pts[-1][0] - pts[-2][0], pts[-1][1] - pts[-2][1]]

    def dir_out(pts):
        return [pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]]

    def turn_angle(v1, v2):
        # angle between vectors in degrees
        n1 = math.hypot(v1[0], v1[1])
        n2 = math.hypot(v2[0], v2[1])
        if n1 < 1e-12 or n2 < 1e-12:
            return 180.0
        c = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)))
        return math.degrees(math.acos(c))

    def best_continuation(eid, rev, at_tail):
        """Pick unused neighbor with smallest turn angle; returns (nid, nrev)
        or None if no candidate with turn <= 60 deg. nrev=True means the
        candidate's points must be reversed to connect at the shared node."""
        pr, pts = edges[eid]
        if at_tail:
            node = (pr.get("endNodeId") if not rev else pr.get("startNodeId"))
        else:
            node = (pr.get("startNodeId") if not rev else pr.get("endNodeId"))
        cands = adj.get(node, [])
        best = None
        best_ang = 61.0
        for nid in cands:
            if nid == eid or used[nid]:
                continue
            npr, npts = edges[nid]
            if at_tail:
                v_cur = dir_in(pts) if not rev else [-dir_out(pts)[0], -dir_out(pts)[1]]
                if npr.get("startNodeId") == node:
                    v_new = dir_out(npts)
                    nrev = False
                elif npr.get("endNodeId") == node:
                    v_new = [-dir_in(npts)[0], -dir_in(npts)[1]]
                    nrev = True
                else:
                    continue
            else:
                v_cur = [-dir_out(pts)[0], -dir_out(pts)[1]] if not rev else dir_in(pts)
                if npr.get("endNodeId") == node:
                    v_new = dir_in(npts)
                    nrev = False
                elif npr.get("startNodeId") == node:
                    v_new = [-dir_out(npts)[0], -dir_out(npts)[1]]
                    nrev = True
                else:
                    continue
            ang = turn_angle(v_cur, v_new)
            if ang < best_ang:
                best_ang = ang
                best = (nid, nrev)
        return best if best_ang <= 60.0 else None

    MAX_PATH = 500.0  # m cap to bound chaining

    def path_len(idx):
        return sum(hav(edges[i][1][k - 1], edges[i][1][k])
                   for i in idx for k in range(1, len(edges[i][1])))

    w = CellWriter(os.path.join(OUT, f"cells_{city}.geojson"))
    n_cells = 0
    n_paths = 0
    km = 0.0
    bins = Counter()
    for e0 in range(len(edges)):
        if used[e0]:
            continue
        chain = [(e0, False)]
        used[e0] = True
        # extend tail then head
        while True:
            nxt = best_continuation(chain[-1][0], chain[-1][1], at_tail=True)
            if nxt is None or path_len([c[0] for c in chain]) >= MAX_PATH:
                break
            chain.append(nxt)
            used[nxt[0]] = True
        while True:
            nxt = best_continuation(chain[0][0], chain[0][1], at_tail=False)
            if nxt is None or path_len([c[0] for c in chain]) >= MAX_PATH:
                break
            chain.insert(0, nxt)
            used[nxt[0]] = True
        if path_len([c[0] for c in chain]) < MIN_TAIL:
            continue
        n_paths += 1
        # concatenate points with per point-pair width bookkeeping (seg_w[i] is
        # the width of segment pts[i]->pts[i+1]; pair count == len(pts)-1)
        pts = []
        seg_w = []
        for eid, rev in chain:
            pr, epts = edges[eid]
            if rev:
                epts = list(reversed(epts))
            wm = pr.get("width_m")
            if not pts:
                pts.extend(epts)
                for k in range(len(epts) - 1):
                    seg_w.append(wm)
            else:
                start = len(pts)
                if epts[0] == pts[-1]:
                    epts = epts[1:]
                pts.extend(epts)
                # pairs from (start-1) [bridge pair] through the new points
                for k in range(start - 1, len(pts) - 1):
                    seg_w.append(wm)
        d = cumdist(pts)
        total = d[-1]
        n_cells_full = int(total // CELL_LEN)
        for ci in range(n_cells_full):
            tpos = ci * CELL_LEN
            t1 = tpos + CELL_LEN
            sub = slice_polyline(pts, d, tpos, t1)
            ln = t1 - tpos
            # length-weighted mean width over [tpos, t1]
            wsum = 0.0
            wlen = 0.0
            for k in range(len(seg_w)):
                ov = max(0.0, min(t1, d[k + 1]) - max(tpos, d[k]))
                if ov > 0 and seg_w[k] is not None:
                    wsum += seg_w[k] * ov
                    wlen += ov
            if wlen <= 0:
                tpos = t1
                continue
            wm_cell = round(wsum / wlen, 3)
            chord = chord_of(sub)
            sin = round(ln / chord, 4) if chord > 0 else None
            src_id = edges[chain[0][0]][0].get("id")
            props = {
                "city": city, "city_cn": CN[city], "split": "train",
                "cell_id": f"{city}-chain-{e0}-{tpos:.0f}", "width_m": wm_cell,
                "net_width_m": None,
                "width_source": edges[chain[0][0]][0].get("width_source"),
                "layer": None, "source_id": src_id,
                "orig_geom": "chained-LineString",
                "cell_length_m": round(ln, 2),
                "sinuosity": sin, "geom_approx": "chained",
            }
            w.write(props, sub)
            n_cells += 1
            km += ln
            if wm_cell < 1.6:
                bins["<1.6"] += 1
            elif wm_cell < 2.4:
                bins["1.6-2.4"] += 1
            elif wm_cell < 3.5:
                bins["2.4-3.5"] += 1
            else:
                bins[">=3.5"] += 1
    w.close()
    summary[city] = dict(split="train", approx="chained", n_cells=n_cells,
                         n_src=len(edges), n_paths=n_paths,
                         km=round(km / 1000, 2), bins=dict(bins))
    print(f"[amsterdam] paths={n_paths} cells={n_cells} km={km/1000:.1f} "
          f"bins={dict(bins)} {time.time()-t0:.0f}s", flush=True)


def main():
    summary = {}
    for city, (fname, split) in LINE_CITIES.items():
        if city == "amsterdam":
            process_amsterdam_chained(summary)
        else:
            process_line_city(city, fname, split, summary)
    for city, (fname, split) in POLY_CITIES.items():
        process_poly_city(city, fname, split, summary)
    with open(os.path.join(OUT, "cells_candidates_summary.csv"), "w",
              encoding="utf-8") as f:
        f.write("city,split,geom_approx,n_source_features,n_cells,km,"
                "n_bin_lt1.6,n_bin_1.6_2.4,n_bin_2.4_3.5,n_bin_ge3.5\n")
        for city, s in summary.items():
            b = s["bins"]
            f.write(f"{city},{s['split']},{s['approx']},{s['n_src']},{s['n_cells']},"
                    f"{s['km']},{b.get('<1.6', 0)},{b.get('1.6-2.4', 0)},"
                    f"{b.get('2.4-3.5', 0)},{b.get('>=3.5', 0)}\n")
    print("summary ->", os.path.join(OUT, "cells_candidates_summary.csv"))


if __name__ == "__main__":
    main()
