# -*- coding: utf-8 -*-
"""
Cut 50 m sidewalk cells from per-city footway candidate lists (analyze_osm.py
output) and select cells against the multi-city training budget defined in
data/multi_city_selection.md §2-§3.

Pipeline per city:
  data/osm/<city>_road.osm                 (geometry)
  data/osm/<city>_footway_candidates.csv   (analyze_osm.py output)
      -> cut into CELL_LEN m cells
      -> select per §2 budget (width strata x geometry type) + per-city quota
      -> unified output

Outputs:
  data/cells.json        unified cell list; every cell carries "city"/"city_code"
  data/cells_<city>.csv  per-city manifest of the SELECTED cells
  data/cell_coverage.md  coverage vs the §2 grid (width x type), incl. gaps

Attribute sources (documented estimates, to be refined by estimate_site_flow.py):
  W_eff   width tag when present, else per-highway default (path 1.2 m,
          footway 1.5 m, pedestrian 2.5 m, cycleway 2.0 m, ...)
  context heuristic: D -> MRT-frontage, pedestrian/living_street -> commercial,
          else residential
  q_p     §5 priors: q_p = x_ctx * W_eff (peak/off-peak ranges)

Usage:
  python build_cells.py                        # all cities, §2 budgets
  python build_cells.py --city tokyo           # subset of cities
  python build_cells.py --all-cells            # every cut cell, no selection
  python build_cells.py --out data/cells.json --cell-len 50
"""
import argparse
import csv
import json
import math
import os
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
OSM_DIR = os.path.join(DATA, "osm")
OUT_JSON = os.path.join(DATA, "cells.json")
OUT_REPORT = os.path.join(DATA, "cell_coverage.md")

CELL_LEN = 50.0      # m
MIN_CELL_LEN = 15.0  # m, skip shorter slivers
MAX_PER_WAY = 3      # diversity cap: cells selected per way
TOTAL_TARGET = 100   # §2 total cell budget

# city -> osm file prefix / §3 cell quota / cell-id code
CITY_INFO = {
    "singapore": {"osm": "bendemeer", "quota": 35, "code": "SIN"},
    "london":    {"osm": "london",    "quota": 25, "code": "LON"},
    "tokyo":     {"osm": "tokyo",     "quota": 25, "code": "TYO"},
    "amsterdam": {"osm": "amsterdam", "quota": 15, "code": "AMS"},
}
CITY_ORDER = ["singapore", "london", "tokyo", "amsterdam"]

# §2 width strata: (key, lo, hi, target, label)
WIDTH_STRATA = [
    ("narrow", 1.0, 1.5, 20, "1.0-1.5 m"),
    ("cliff",  1.5, 1.8, 30, "1.5-1.8 m"),
    ("mid",    1.8, 2.4, 25, "1.8-2.4 m"),
    ("wide",   2.4, 3.5, 20, "2.4-3.5 m"),
    ("extra",  3.5, 99.0, 10, ">3.5 m"),
]
TYPE_TARGETS = {"A": 40, "B": 20, "C": 25, "D": 15}

# per-city selection mandates: (predicate spec, cap). Caps sum to the §3 city
# quota so every city contributes a stratified mix, not just its first spec.
MANDATE = {
    "singapore": [("type=A&w>=1.8", 20), ("w>=2.4", 8), ("type=C", 4), ("type=B", 3)],
    "london":    [("w<1.8", 15), ("type=C", 6), ("type=D", 3), ("type=B", 1)],
    "tokyo":     [("w<1.5", 12), ("type=D", 6), ("type=C", 4), ("type=B", 3)],
    "amsterdam": [("type=B", 8), ("type=C", 4), ("type=D", 2), ("type=A&w>=1.8", 1)],
}

# W_eff estimate when the way carries no width tag (documented guess, m)
W_DEFAULT = {
    "path": 1.2, "footway": 1.5, "pedestrian": 2.5, "cycleway": 2.0,
    "living_street": 2.2, "service": 1.5, "residential": 1.5,
    "unclassified": 1.5, "primary": 1.8, "secondary": 1.8, "tertiary": 1.8,
}
W_FALLBACK = 1.5

# §5 context -> unit-width flow priors (ped/min/m), peak / off-peak
X_CTX = {
    "residential":   {"peak": (5.0, 12.0), "off": (1.5, 3.0)},
    "commercial":    {"peak": (15.0, 25.0), "off": (4.0, 7.0)},
    "MRT-frontage":  {"peak": (30.0, 45.0), "off": (8.0, 12.0)},
    "tourism/mixed": {"peak": (20.0, 35.0), "off": (6.0, 10.0)},
}

M_PER_DEG_LAT = 111132.0
M_PER_DEG_LON = 111320.0  # * cos(lat) applied per way


def hav(lat1, lon1, lat2, lon2):
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def ang_diff(a, b):
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def width_stratum(w):
    if w < 1.5:
        return "narrow", "1.0-1.5 m"
    if w < 1.8:
        return "cliff", "1.5-1.8 m"
    if w < 2.4:
        return "mid", "1.8-2.4 m"
    if w <= 3.5:
        return "wide", "2.4-3.5 m"
    return "extra", ">3.5 m"


def matches(cell, spec):
    """Predicate over a cell dict; specs like 'type=B', 'w<1.5', 'type=A&w>=1.8'."""
    for part in spec.split("&"):
        p = part.strip()
        if p.startswith("type="):
            if cell["type"] != p[5:]:
                return False
        elif p.startswith("w<="):
            if not cell["W_eff"] <= float(p[3:]):
                return False
        elif p.startswith("w>="):
            if not cell["W_eff"] >= float(p[3:]):
                return False
        elif p.startswith("w<"):
            if not cell["W_eff"] < float(p[2:]):
                return False
        elif p.startswith("w>"):
            if not cell["W_eff"] > float(p[2:]):
                return False
        else:
            raise ValueError(f"bad mandate spec: {spec}")
    return True


def pool_key(cell, spec):
    """Sort key that puts the most on-mandate cells first."""
    if "&" not in spec and "w<" in spec:
        return (cell["W_eff"],)
    if "type=B" in spec:  # prefer moderate canal-curve geometry, not loops
        return (abs(cell["sinuosity"] - 1.05),)
    if "type=C" in spec:
        return (-min(cell["n_barriers"], 1), cell["W_eff"])
    if "type=D" in spec:
        return (-cell["junc_deg_max"],)
    return (-cell["L"],)


def cell_geometry(sub):
    """Path length / max turn / cumulative turn / sinuosity of a local polyline."""
    if len(sub) < 2:
        return 0.0, 0.0, 0.0, 1.0
    brgs = []
    path = 0.0
    for i in range(len(sub) - 1):
        dx, dy = sub[i + 1][0] - sub[i][0], sub[i + 1][1] - sub[i][1]
        path += math.hypot(dx, dy)
        brgs.append((math.degrees(math.atan2(dy, dx)) + 360.0) % 360.0)
    max_turn = max((ang_diff(brgs[i], brgs[i + 1]) for i in range(len(brgs) - 1)),
                   default=0.0)
    cum_turn = sum(ang_diff(brgs[i], brgs[i + 1]) for i in range(len(brgs) - 1))
    chord = math.hypot(sub[-1][0] - sub[0][0], sub[-1][1] - sub[0][1])
    sinu = path / chord if chord > 0.05 else 1.0
    return path, max_turn, cum_turn, sinu


def cell_width(row):
    w = (row.get("width_m") or "").strip()
    if w:
        return float(w), "tag"
    hw = row.get("highway") or ""
    return W_DEFAULT.get(hw, W_FALLBACK), f"default:{hw or '?'}"


def guess_context(ctype, highway):
    if ctype == "D":
        return "MRT-frontage"
    if highway in ("pedestrian", "living_street"):
        return "commercial"
    return "residential"


def cut_way(city, code, wid, row, refs, pts, node_ev, cell_len, min_cell_len):
    """Cut one way into cells; boundaries align to crossing/barrier nodes so
    cells end at disturbances (plan §cell-splitting). Local tangent-plane frame
    anchored at the way's first point (+x east, +y north)."""
    cum = [0.0]
    for i in range(len(pts) - 1):
        cum.append(cum[-1] + hav(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1]))
    total = cum[-1]
    # boundaries: way ends + regular grid + feature nodes (crossing/barrier)
    bounds = [0.0]
    for k in range(1, int(total // cell_len) + 2):
        b = round(k * cell_len, 3)
        if b < total - 1e-6:
            bounds.append(b)
    bounds.append(total)
    for i, r in enumerate(refs):
        if node_ev.get(r) and 1e-6 < cum[i] < total - 1e-6:
            bounds.append(round(cum[i], 3))
    bounds = sorted(bounds)
    dedup = [bounds[0]]
    for b in bounds[1:]:
        if b - dedup[-1] > 0.5:
            dedup.append(b)  # keep-first: feature wins over nearby grid mark
    if dedup[-1] < total:
        dedup.append(total)

    ref = pts[0]
    clat = math.cos(math.radians(ref[0]))

    def local(pt):
        return (round((pt[1] - ref[1]) * M_PER_DEG_LON * clat, 3),
                round((pt[0] - ref[0]) * M_PER_DEG_LAT, 3))

    def interp(a, b, f):
        return (a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1]))

    # way-level evidence (from analyze_osm.py)
    ev_w = row["evidence"]
    way_c = row["cell_type"] == "C"
    c_other = way_c and any(k in ev_w for k in
                            ("narrow_width", "maxwidth", "bridge=", "tunnel=",
                             "narrow=yes", "rel_narrow"))
    weff, wsrc = cell_width(row)
    out = []
    ci = 0
    for b0, b1 in zip(dedup, dedup[1:]):
        if b1 - b0 < min_cell_len:
            continue
        # feature nodes strictly inside (b0, b1] -> cell-local evidence
        bars, nc = [], 0
        end_crossing = False
        for i, r in enumerate(refs):
            pos = cum[i]
            if b0 + 1e-6 < pos <= b1 + 1e-6:
                ev = node_ev.get(r)
                if not ev:
                    continue
                if "barrier" in ev:
                    bars.append(ev["barrier"])
                if "crossing" in ev:
                    nc += 1
                    if abs(pos - b1) < 1e-6:
                        end_crossing = True
        nb = len(bars)
        # sub-polyline in local meters
        sub = []
        geo0 = None
        s_acc = 0.0
        for i in range(len(pts) - 1):
            seg = cum[i + 1] - cum[i]
            s_next = s_acc + seg
            if s_next <= b0:
                s_acc = s_next
                continue
            if s_acc >= b1:
                break
            lo = max(s_acc, b0)
            hi = min(s_next, b1)
            if not sub:
                f = (lo - s_acc) / (seg + 1e-9)
                geo0 = interp(pts[i], pts[i + 1], f)
                sub.append(local(geo0))
            if hi >= s_next - 1e-9:
                sub.append(local(pts[i + 1]))
            else:
                f = (hi - s_acc) / (seg + 1e-9)
                sub.append(local(interp(pts[i], pts[i + 1], f)))
                break
            s_acc = s_next
        if len(sub) < 2:
            sub = [local(pts[0]), local(pts[-1])]
            geo0 = pts[0]
        L, max_turn, cum_turn, sinu = cell_geometry(sub)

        # cell-level type (precedence C > B > D > A, like analyze_osm.py)
        cell_c = (way_c and c_other) or nb >= 1
        at_end = b1 >= total - 1e-6
        at_start = b0 <= 1e-6
        junc_deg = int(row["junc_deg_max"])
        cell_d = end_crossing or (
            (at_start or at_end) and (row["type_d"] == "1" or junc_deg >= 3))
        # B requires genuine cell-level curvature: a real bend (sin 1.01-2.0,
        # <=180 deg of turning), not plaza loops/switchbacks or straight chunks
        cell_b = (row["type_b"] == "1"
                  and 1.01 <= sinu <= 2.0 and cum_turn <= 180.0)
        straight = max_turn <= 15.0
        if cell_c:
            ctype = "C"
        elif cell_b:
            ctype = "B"
        elif cell_d:
            ctype = "D"
        elif straight:
            ctype = "A"
        else:
            ctype = "other"

        reasons = []
        if nb:
            reasons.append("barrier=" + ",".join(sorted(set(bars))))
        if end_crossing:
            reasons.append("crossing_end")
        if cell_c and c_other:
            reasons.append(";".join(p for p in ev_w.split(";")
                                    if any(k in p for k in (
                                        "narrow_width", "maxwidth", "bridge",
                                        "tunnel", "narrow", "rel_narrow"))))
        if ctype == "B":
            reasons.append(f"curve(sin={sinu:.3f},cum={cum_turn:.0f})")
        if ctype == "D":
            reasons.append(f"junc(deg={junc_deg})")
        if ctype == "A":
            reasons.append("straight")

        ctx = guess_context(ctype, row["highway"])
        out.append({
            "cell_id": f"{code}-{wid}-{ci}",
            "city": city,
            "city_code": code,
            "way_id": wid,
            "name": row["name"],
            "highway": row["highway"],
            "type": ctype,
            "type_a": 1 if ctype == "A" else 0,
            "type_b": 1 if ctype == "B" else 0,
            "type_c": 1 if ctype == "C" else 0,
            "type_d": 1 if ctype == "D" else 0,
            "context": ctx,
            "context_src": "heuristic",
            "W_eff": weff, "W_lo": weff, "W_hi": weff,
            "width_src": wsrc,
            "q_p_peak": [round(x * weff, 1) for x in X_CTX[ctx]["peak"]],
            "q_p_off": [round(x * weff, 1) for x in X_CTX[ctx]["off"]],
            "q_p_src": "prior",
            "L": round(b1 - b0, 1),
            "centerline": sub,
            "lat0": round(geo0[0], 6),
            "lon0": round(geo0[1], 6),
            "sinuosity": round(sinu, 4),
            "cum_turn_deg": round(cum_turn, 1),
            "max_turn_deg": round(max_turn, 1),
            "n_barriers": nb,
            "n_crossings": nc,
            "junc_deg_max": junc_deg,
            "evidence": ";".join(reasons),
        })
        ci += 1
    return out


def cut_city(city, cell_len, min_cell_len):
    info = CITY_INFO[city]
    csv_path = os.path.join(OSM_DIR, f"{info['osm']}_footway_candidates.csv")
    osm_path = os.path.join(OSM_DIR, f"{info['osm']}_road.osm")
    if not os.path.exists(osm_path):  # nested layout: data/osm/<city>/<city>_road.osm
        osm_path = os.path.join(OSM_DIR, info["osm"], f"{info['osm']}_road.osm")
    if not (os.path.exists(csv_path) and os.path.exists(osm_path)):
        print(f"skip {city}: missing {csv_path} or {osm_path}")
        return []
    rows = {}
    with open(csv_path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            rows[r["way_id"]] = r
    tree = ET.parse(osm_path)
    root = tree.getroot()
    nodes = {nd.get("id"): (float(nd.get("lat")), float(nd.get("lon")))
             for nd in root.iter("node") if nd.get("lat")}
    node_ev = {}
    for nd in root.iter("node"):
        tags = {t.get("k"): t.get("v") for t in nd.findall("tag")}
        if not tags:
            continue
        ev = {}
        if "barrier" in tags:
            ev["barrier"] = tags["barrier"]
        if tags.get("highway") in ("crossing", "traffic_signals") or "crossing" in tags:
            ev["crossing"] = True
        if ev:
            node_ev[nd.get("id")] = ev
    cells = []
    for w in root.iter("way"):
        wid = w.get("id")
        if wid not in rows:
            continue
        refs = [nd.get("ref") for nd in w.findall("nd")]
        pts = [nodes[r] for r in refs if r in nodes]
        if len(pts) < 2:
            continue
        cells.extend(cut_way(city, info["code"], wid, rows[wid], refs, pts,
                             node_ev, cell_len, min_cell_len))
    print(f"{city}: cut {len(cells)} cells from {len(rows)} ways")
    return cells


# which city is on-mandate for a grid key (pass 2 fill prefers these)
RELEVANCE = {
    "A": ["singapore", "london", "tokyo", "amsterdam"],
    "B": ["amsterdam", "london", "tokyo", "singapore"],
    "C": ["london", "tokyo", "amsterdam", "singapore"],
    "D": ["tokyo", "london", "amsterdam", "singapore"],
    "narrow": ["tokyo", "london", "amsterdam", "singapore"],
    "cliff": ["london", "tokyo", "amsterdam", "singapore"],
    "mid": ["singapore", "amsterdam", "london", "tokyo"],
    "wide": ["singapore", "amsterdam", "london", "tokyo"],
    "extra": ["singapore", "amsterdam", "london", "tokyo"],
}


def city_rank(city, key):
    lst = RELEVANCE.get(key, CITY_ORDER)
    return lst.index(city) if city in lst else len(lst)


def select(cells_by_city, all_cells, max_per_way, total_target):
    """Greedy budget selection: per-city mandate -> fill quota -> global §2 fill."""
    if all_cells:
        return [c for cs in cells_by_city.values() for c in cs
                if c["type"] in TYPE_TARGETS]

    sel = []
    sel_ids = set()
    used_ways = Counter()

    def take(cell):
        sel.append(cell)
        sel_ids.add(cell["cell_id"])
        used_ways[(cell["city"], cell["way_id"])] += 1

    # pass 1: per-city mandates, using RESERVE_FRAC of each quota so pass 2
    # can balance the §2 grid (width strata x type) afterwards
    RESERVE_FRAC = 0.2
    for city in CITY_ORDER:
        pool_all = [c for c in cells_by_city.get(city, [])
                    if c["type"] in TYPE_TARGETS]
        quota = CITY_INFO[city]["quota"]
        quota_eff = int(round(quota * (1.0 - RESERVE_FRAC)))
        picked = 0
        for spec, cap in MANDATE[city]:
            if picked >= quota_eff:
                break
            cap_eff = max(1, int(round(cap * (1.0 - RESERVE_FRAC))))
            got = 0
            pool = [c for c in pool_all
                    if c["cell_id"] not in sel_ids and matches(c, spec)]
            pool.sort(key=lambda c: pool_key(c, spec))
            for c in pool:
                if picked >= quota_eff or got >= cap_eff:
                    break
                if used_ways[(city, c["way_id"])] >= max_per_way:
                    continue
                take(c)
                picked += 1
                got += 1
        if picked < quota_eff:  # fill the rest with anything (unused ways first)
            rest = [c for c in pool_all if c["cell_id"] not in sel_ids]
            rest.sort(key=lambda c: (used_ways[(city, c["way_id"])], -c["L"]))
            for c in rest:
                if picked >= quota_eff:
                    break
                if used_ways[(city, c["way_id"])] >= max_per_way:
                    continue
                take(c)
                picked += 1

    # pass 2: global fill towards the §2 grid and the total target
    def counts(cells):
        cnt = Counter()
        for c in cells:
            cnt[(width_stratum(c["W_eff"])[0], c["type"])] += 1
        return cnt

    def gaps(cnt):
        g = []
        for sk, lo, hi, target, label in WIDTH_STRATA:
            got = sum(cnt[(sk, t)] for t in TYPE_TARGETS)
            g.append(("W", sk, target - got))
        for t, target in TYPE_TARGETS.items():
            got = sum(cnt[(sk, t)] for sk, _, _, _, _ in WIDTH_STRATA)
            g.append(("T", t, target - got))
        return sorted(g, key=lambda x: -x[2])

    leftover = [c for city in CITY_ORDER for c in cells_by_city.get(city, [])
                if c["cell_id"] not in sel_ids and c["type"] in TYPE_TARGETS]
    tried = set()
    city_cnt = Counter(c["city"] for c in sel)
    while len(sel) < total_target:
        g = [x for x in gaps(counts(sel))
             if x[2] > 0 and (x[0], x[1]) not in tried]
        if not g:
            break
        gap_map = {(x[0], x[1]): x[2] for x in gaps(counts(sel))}
        axis, key, _ = g[0]
        cand = [c for c in leftover
                if (width_stratum(c["W_eff"])[0] == key if axis == "W"
                    else c["type"] == key)
                and city_cnt[c["city"]] < CITY_INFO[c["city"]]["quota"] * 1.2]
        if not cand:
            tried.add((axis, key))
            continue

        def score(c):
            # prefer cells that also close another deficit ("two birds")
            sk = width_stratum(c["W_eff"])[0]
            gains = 0
            if axis == "W" and gap_map.get(("T", c["type"]), 0) > 0:
                gains += 1
            if axis == "T" and gap_map.get(("W", sk), 0) > 0:
                gains += 1
            return (-gains, city_rank(c["city"], key),
                    used_ways[(c["city"], c["way_id"])])

        cand.sort(key=score)
        c = cand[0]
        leftover = [x for x in leftover if x["cell_id"] != c["cell_id"]]
        if used_ways[(c["city"], c["way_id"])] >= max_per_way:
            continue
        take(c)
        city_cnt[c["city"]] += 1
    return sel


def grid_table(cells):
    cnt = Counter()
    for c in cells:
        cnt[(width_stratum(c["W_eff"])[0], c["type"])] += 1
    rows = []
    for sk, lo, hi, target, label in WIDTH_STRATA:
        vals = [cnt[(sk, t)] for t in ("A", "B", "C", "D")]
        rows.append((label, vals, sum(vals), target))
    tvals = [sum(cnt[(sk, t)] for sk, _, _, _, _ in WIDTH_STRATA)
             for t in ("A", "B", "C", "D")]
    return rows, tvals


def write_report(sel, pool_by_city, all_cells, out_md):
    city_sel = {city: [c for c in sel if c["city"] == city] for city in CITY_ORDER}
    add = []
    add.append("# Multi-city cell coverage vs §2 grid")
    add.append("")
    add.append(f"- generated: {date.today().isoformat()}")
    add.append("- mode: " + ("all cut cells (no selection)" if all_cells
                            else "budget-selected (§2 grid + §3 per-city quota)"))
    add.append(f"- selected cells: {len(sel)}")
    add.append("")

    add.append("## 1. Per-city quota")
    add.append("")
    add.append("| city | quota | selected | A | B | C | D | narrow(<1.5 m) |")
    add.append("|---|---|---|---|---|---|---|---|")
    for city in CITY_ORDER:
        cs = city_sel[city]
        ct = Counter(c["type"] for c in cs)
        narrow = sum(1 for c in cs if c["W_eff"] < 1.5)
        add.append(f"| {city} | {CITY_INFO[city]['quota']} | {len(cs)} | "
                   f"{ct['A']} | {ct['B']} | {ct['C']} | {ct['D']} | {narrow} |")

    for title, cells in (("2. Grid coverage (selected)", sel),
                         ("3. Available pool (all cut cells)", sum(pool_by_city.values(), []))):
        rows, tvals = grid_table(cells)
        add.append("")
        add.append(f"## {title}")
        add.append("")
        add.append("| width \\ type | A | B | C | D | row | §2 target |")
        add.append("|---|---|---|---|---|---|---|")
        for label, vals, row, target in rows:
            add.append(f"| {label} | {' | '.join(map(str, vals))} | {row} | ~{target} |")
        add.append(f"| **total** | {' | '.join(map(str, tvals))} | {sum(tvals)} | ~{TOTAL_TARGET} |")
        add.append(f"| **§2 type target** | 40 | 20 | 25 | 15 | ~{TOTAL_TARGET} | |")

    # context axis (heuristic only, see notes)
    ctx_cnt = Counter(c["context"] for c in sel)
    add.append("")
    add.append("### Context axis (heuristic)")
    add.append("")
    add.append("| context | residential | commercial | MRT-frontage | tourism/mixed |")
    add.append("|---|---|---|---|---|")
    add.append(f"| selected | {ctx_cnt.get('residential', 0)} | "
               f"{ctx_cnt.get('commercial', 0)} | {ctx_cnt.get('MRT-frontage', 0)} | "
               f"{ctx_cnt.get('tourism/mixed', 0)} |")
    add.append("| §2 target | ~35 | ~30 | ~25 | ~10 |")

    # highlighted gap checks
    srows, stvals = grid_table(sel)
    scnt = Counter((width_stratum(c["W_eff"])[0], c["type"]) for c in sel)
    srow = {sk: sum(scnt[(sk, t)] for t in ("A", "B", "C", "D"))
            for sk, _, _, _, _ in WIDTH_STRATA}
    add.append("")
    add.append("## 4. Gap check (highlighted)")
    add.append("")
    pool = sum(pool_by_city.values(), [])
    narrow_got = srow.get("narrow", 0)
    narrow_pool = sum(1 for c in pool if c["W_eff"] < 1.5)
    tokyo_narrow = sum(1 for c in city_sel["tokyo"] if c["W_eff"] < 1.5)
    ams_b = sum(1 for c in city_sel["amsterdam"] if c["type"] == "B")
    lon_c = sum(1 for c in city_sel["london"] if c["type"] == "C")
    b_got = stvals[1]
    c_got = stvals[2]
    d_got = stvals[3]
    add.append(f"- **窄 1.0-1.5 m**：已采 {narrow_got} / 目标 ~20"
               f"（池内可用 {narrow_pool}；东京贡献 {tokyo_narrow}，"
               f"主要来自 path 默认 1.2 m + 显式 width 标签）"
               + (" — 缺口 " + str(20 - narrow_got) if narrow_got < 20 else " — 达标"))
    add.append(f"- **B 曲线**：已采 {b_got} / 目标 ~20"
               f"（阿姆斯特丹 {ams_b} 个，quota {CITY_INFO['amsterdam']['quota']}）"
               + (" — 缺口 " + str(20 - b_got) if b_got < 20 else " — 达标"))
    add.append(f"- **C 瓶颈**：已采 {c_got} / 目标 ~25"
               f"（伦敦 {lon_c} 个，quota {CITY_INFO['london']['quota']}）"
               + (" — 缺口 " + str(25 - c_got) if c_got < 25 else " — 达标"))
    add.append(f"- **D 路口前场**：已采 {d_got} / 目标 ~15"
               + (" — 缺口 " + str(15 - d_got) if d_got < 15 else " — 达标"))
    add.append(f"- **语境**：启发式分类 住宅 {ctx_cnt.get('residential', 0)} / "
               f"商业 {ctx_cnt.get('commercial', 0)} / 换乘前场 {ctx_cnt.get('MRT-frontage', 0)} "
               f"vs §2 ~35/30/25，旅游混行缺失；POI 已下载（data/osm/<city>/<city>_poi.osm），"
               f"待 estimate_site_flow.py 参数化精确语境。")
    add.append("")
    add.append("## 5. Notes")
    add.append("")
    add.append("- W_eff：有 width 标签用标签值，否则按 highway 默认（path 1.2 m、footway 1.5 m、"
               "pedestrian 2.5 m、cycleway 2.0 m、living_street 2.2 m、道路 1.5-1.8 m）。"
               "OSM 显式 width 标签稀疏，窄档主要靠默认估计。")
    add.append("- context 为启发式（D→MRT-frontage，pedestrian/living_street→commercial，其余 residential）；"
               "POI 精确语境分类待 estimate_site_flow.py 参数化。")
    add.append("- q_p 用 §5 先验 q_p = x_ctx·W_eff（峰时/非峰区间），q_p_src=prior。")
    add.append("- 每 way 最多取 " + str(MAX_PER_WAY) + " 个 cell（多样性上限）。")
    os.makedirs(os.path.dirname(out_md) or ".", exist_ok=True)
    with open(out_md, "w", encoding="utf-8-sig") as f:
        f.write("\n".join(add) + "\n")
    print(f"wrote coverage report -> {out_md}")
    return add


def write_outputs(sel, cell_len, out_json):
    cells_out = []
    for c in sel:
        d = dict(c)
        cells_out.append(d)
    payload = {
        "cell_len": cell_len,
        "cities": [city for city in CITY_ORDER
                   if any(c["city"] == city for c in sel)],
        "n": len(cells_out),
        "cells": cells_out,
    }
    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"wrote {len(cells_out)} cells -> {out_json}")

    for city in CITY_ORDER:
        cs = [c for c in sel if c["city"] == city]
        if not cs:
            continue
        path = os.path.join(DATA, f"cells_{city}.csv")
        cols = ["cell_id", "way_id", "name", "highway", "type", "context",
                "W_eff", "width_src", "L", "sinuosity", "cum_turn_deg",
                "max_turn_deg", "n_barriers", "junc_deg_max",
                "lat0", "lon0", "evidence"]
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            wcsv = csv.DictWriter(f, fieldnames=cols)
            wcsv.writeheader()
            for c in sorted(cs, key=lambda c: c["cell_id"]):
                wcsv.writerow({k: c[k] for k in cols})
        print(f"wrote {len(cs)} {city} cells -> {path}")


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Cut 50 m cells per city and select against the §2 budget "
                    "(multi_city_selection.md).")
    p.add_argument("--city", action="append", default=[],
                   help="city to process (repeatable; default: all)")
    p.add_argument("--out", default=OUT_JSON, help="unified cells.json path")
    p.add_argument("--report", default=OUT_REPORT, help="coverage report path")
    p.add_argument("--cell-len", type=float, default=CELL_LEN, help="cell length (m)")
    p.add_argument("--min-cell-len", type=float, default=MIN_CELL_LEN,
                   help="skip shorter slivers (m)")
    p.add_argument("--all-cells", action="store_true",
                   help="export every cut cell (skip budget selection)")
    p.add_argument("--total", type=int, default=None,
                   help="global cell target (default: sum of the processed "
                        "cities' quotas; all 4 cities -> 100, per §2)")
    return p.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    cities = args.city or CITY_ORDER
    known = set(CITY_INFO) | {"bendemeer"}
    for c in cities:
        if c.lower() not in known:
            raise SystemExit(f"error: unknown city '{c}' (have: {sorted(known)})")
    cities = [("singapore" if c.lower() == "bendemeer" else c.lower()) for c in cities]

    pool_by_city = {}
    for city in cities:
        pool_by_city[city] = cut_city(city, args.cell_len, args.min_cell_len)

    total = args.total if args.total is not None else \
        sum(CITY_INFO[c]["quota"] for c in cities)
    sel = select(pool_by_city, args.all_cells, MAX_PER_WAY, total)

    # console summary
    for city in cities:
        cs = [c for c in sel if c["city"] == city]
        ct = Counter(c["type"] for c in cs)
        print(f"  {city:10s} selected {len(cs):3d}  A={ct['A']:3d} B={ct['B']:3d} "
              f"C={ct['C']:3d} D={ct['D']:3d}")
    rows, tvals = grid_table(sel)
    print("  grid (selected):")
    for label, vals, row, target in rows:
        print(f"    {label:10s} " + " ".join(f"{t}={v:3d}" for t, v in
                                            zip(("A", "B", "C", "D"), vals))
              + f"   (target ~{target})")

    write_outputs(sel, args.cell_len, args.out)
    write_report(sel, pool_by_city, args.all_cells, args.report)
    return sel


if __name__ == "__main__":
    main(sys.argv[1:])
