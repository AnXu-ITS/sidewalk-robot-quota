# -*- coding: utf-8 -*-
"""
Analyze a SUMO/OSM export for pedestrian-relevant ways and classify them into
sidewalk cell types for the quota-algorithm real-network training set:

  Type-A 直线 straight cell     -- straight-ish geometry; 15-60 m = ready cell,
                                   >60 m = splittable (can be cut into 20-50 m)
  Type-B 曲线 curve / corner    -- meaningful curvature: cumulative turn >= 30 deg,
                                   a single turn >= 45 deg, or sinuosity >= 1.02
  Type-C 瓶颈 bottleneck        -- width pinch: width/est_width <= 1.5 m,
                                   maxwidth(:physical) <= 1.6 m, barrier node on
                                   the way (bollard/gate/...), bridge/tunnel/
                                   narrow=yes, or >=20% narrower than neighbours
                                   sharing an endpoint
  Type-D 路口前场 junction forecourt -- short (<=60 m) way whose endpoint sits on a
                                   junction node (>=3 ways sharing the node) or on
                                   a crossing / traffic_signals node

Precedence for the summary `cell_type` column: C > B > D > A. The per-type
boolean columns (type_a/b/c/d) are independent evidence flags; downstream
tools (e.g. build_cells.py) may re-map them freely.

Outputs:
  <out csv> -- every pedestrian-relevant way with geometry + type columns

Usage:
  python analyze_osm.py --osm bendemeer --out bendemeer.csv
  python analyze_osm.py --osm path/to/file.osm [--out out.csv]
  python analyze_osm.py [path_to.osm]              # backward compatible
  python analyze_osm.py                            # legacy default: bendemeer

--osm accepts either a city token (resolved under data/osm/ as <city>_road.osm,
<city>/<city>_road.osm or <city>.osm) or a direct .osm file path.
--out defaults to data/osm/<city>_footway_candidates.csv; a bare run with no
arguments keeps the legacy output data/footway_candidates.csv.
"""
import argparse
import csv
import math
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from statistics import median

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
OSM_DIR = os.path.join(DATA, "osm")
DEFAULT_CITY = "bendemeer"
LEGACY_OUT = os.path.join(DATA, "footway_candidates.csv")

# ways we treat as pedestrian-relevant (robot-run footpath candidates)
PED_HIGHWAYS = {"footway", "pedestrian", "path", "living_street"}
# excluded regardless of foot=* / sidewalk=* tags (wheeled robots cannot use)
EXCLUDE_HIGHWAYS = {"steps", "construction", "proposed"}

R = 6371000.0  # Earth radius (m)

# --- classification thresholds (documented; tune per city if needed) ---
A_MAX_TURN = 15.0        # deg: max consecutive-segment turn for Type-A
A_MIN_LEN = 15.0         # m:   Type-A ready-cell band
A_MAX_LEN = 60.0

B_MIN_CUM_TURN = 30.0    # deg: total turning along the way => curve evidence
B_SHARP_TURN = 45.0      # deg: a single turn this large is a corner/curve
B_MIN_SINUOSITY = 1.02   # path/chord ratio => curve evidence

C_NARROW_M = 1.5         # m: width/est_width <= this => pinch
C_MAXWIDTH_M = 1.6       # m: maxwidth(:physical) <= this => pinch
C_REL_NARROW = 0.80      # width <= 80% of neighbour median => pinch
C_NBR_MIN = 2            # neighbours with a width tag needed for relative test

D_JUNC_DEG = 3           # distinct ways sharing an endpoint node => junction
D_MAX_LEN = 60.0         # m: only short ways count as forecourts


def haversine(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def bearing(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def ang_diff(a, b):
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def parse_width(tags):
    """First numeric value of width/est_width tags, in metres (or None)."""
    for k in ("width", "est_width"):
        m = re.search(r"(\d+(?:\.\d+)?)", tags.get(k, "") or "")
        if m:
            return float(m.group(1))
    return None


def parse_maxwidth(tags):
    for k in ("maxwidth:physical", "maxwidth"):
        m = re.search(r"(\d+(?:\.\d+)?)", tags.get(k, "") or "")
        if m:
            return float(m.group(1))
    return None


def resolve_osm(token):
    """Resolve a city token (or a direct path) to an .osm file."""
    if token is None:
        token = DEFAULT_CITY
    if os.path.sep in token or token.endswith(".osm") or os.path.exists(token):
        return token
    cands = [
        os.path.join(OSM_DIR, f"{token}_road.osm"),
        os.path.join(OSM_DIR, token, f"{token}_road.osm"),
        os.path.join(OSM_DIR, f"{token}.osm"),
    ]
    for c in cands:
        if os.path.exists(c):
            return c
    raise SystemExit(
        f"error: cannot resolve --osm '{token}'. tried:\n  " + "\n  ".join(cands)
    )


def city_of(osm_path):
    base = os.path.basename(osm_path)
    base = re.sub(r"\.osm$", "", base)
    base = re.sub(r"_road$", "", base)
    return base or DEFAULT_CITY


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Classify pedestrian-relevant OSM ways into cell types "
                    "A (straight) / B (curve) / C (bottleneck) / D (junction forecourt).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="examples:\n"
               "  python analyze_osm.py --osm bendemeer --out bendemeer.csv\n"
               "  python analyze_osm.py --osm data/osm/bendemeer_road.osm\n"
               "  python analyze_osm.py                 # legacy bendemeer run",
    )
    p.add_argument("--osm", help="city token (resolved under data/osm/) or direct .osm path")
    p.add_argument("--out", help="output CSV path "
                                 "(default: data/osm/<city>_footway_candidates.csv)")
    p.add_argument("osm_pos", nargs="?", help="backward-compatible positional .osm path")
    return p.parse_args(argv)


def main(args):
    try:  # console may be GBK; never crash on CJK way names
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    osm_path = resolve_osm(args.osm or args.osm_pos)
    city = city_of(osm_path)
    if args.out:
        out_csv = args.out
    elif args.osm or args.osm_pos:
        out_csv = os.path.join(OSM_DIR, f"{city}_footway_candidates.csv")
    else:
        out_csv = LEGACY_OUT

    print(f"osm   : {osm_path}")
    print(f"output: {out_csv}")
    print(f"parsing {osm_path} ...")
    tree = ET.parse(osm_path)
    root = tree.getroot()

    # --- nodes: coordinates + evidence tags (barrier / crossing / signals) ---
    nodes = {}
    node_tags = {}
    for nd in root.iter("node"):
        lat, lon = nd.get("lat"), nd.get("lon")
        if lat is not None and lon is not None:
            nodes[nd.get("id")] = (float(lat), float(lon))
        tags = {t.get("k"): t.get("v") for t in nd.findall("tag")}
        if tags:
            node_tags[nd.get("id")] = tags

    lats = [v[0] for v in nodes.values()]
    lons = [v[1] for v in nodes.values()]
    print(f"nodes={len(nodes)}  bbox lat[{min(lats):.5f},{max(lats):.5f}] "
          f"lon[{min(lons):.5f},{max(lons):.5f}]")

    # --- pass 1: all ways -> topology (junction degree) + ped-relevant geometry ---
    node_deg = {}      # node id -> set of way ids sharing it
    way_tags = {}      # way id -> tag dict (for neighbour width comparisons)
    ped_raw = []       # ped-relevant ways with geometry + refs + tags

    for w in root.iter("way"):
        wid = w.get("id")
        refs = [nd.get("ref") for nd in w.findall("nd")]
        if len(refs) < 2:
            continue
        tags = {t.get("k"): t.get("v") for t in w.findall("tag")}
        way_tags[wid] = tags
        for r in (refs[0], refs[-1]):
            node_deg.setdefault(r, set()).add(wid)

        hw = tags.get("highway") or ""  # some ped ways carry foot/sidewalk only
        if hw in EXCLUDE_HIGHWAYS:
            continue
        ped_relevant = (
            hw in PED_HIGHWAYS
            or tags.get("foot") in ("yes", "designated")
            or tags.get("sidewalk") in ("both", "left", "right", "yes")
        )
        if not ped_relevant:
            continue
        pts = [nodes[r] for r in refs if r in nodes]
        if len(pts) < 2:
            continue

        total = 0.0
        seg_brg = []
        for i in range(len(pts) - 1):
            d = haversine(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])
            total += d
            seg_brg.append(bearing(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1]))

        # straightness: max turning angle between consecutive segments
        max_turn = 0.0
        for i in range(len(seg_brg) - 1):
            max_turn = max(max_turn, ang_diff(seg_brg[i], seg_brg[i + 1]))
        # cumulative turning (total curvature) and sinuosity (path / chord)
        cum_turn = sum(ang_diff(seg_brg[i], seg_brg[i + 1])
                       for i in range(len(seg_brg) - 1))
        chord = haversine(pts[0][0], pts[0][1], pts[-1][0], pts[-1][1])
        sinuosity = total / chord if chord > 0.05 else 1.0
        # overall straightness: endpoint bearing vs chord bearing
        cb = bearing(pts[0][0], pts[0][1], pts[-1][0], pts[-1][1])
        wander = max(ang_diff(b, cb) for b in seg_brg) if seg_brg else 0.0

        ped_raw.append({
            "way_id": wid,
            "refs": refs,
            "tags": tags,
            "highway": hw,
            "name": tags.get("name", ""),
            "name_zh": tags.get("name:zh", ""),
            "n_nodes": len(pts),
            "length_m": round(total, 1),
            "max_turn_deg": round(max_turn, 1),
            "wander_deg": round(wander, 1),
            "cum_turn_deg": round(cum_turn, 1),
            "sinuosity": round(sinuosity, 3),
            "lat0": round(pts[0][0], 6),
            "lon0": round(pts[0][1], 6),
            "lat1": round(pts[-1][0], 6),
            "lon1": round(pts[-1][1], 6),
            "width_tag": tags.get("width", tags.get("est_width", "")),
        })

    # --- pass 2: classify each ped-relevant way ---
    rows = []
    for w in ped_raw:
        wid, refs, tags = w["way_id"], w["refs"], w["tags"]
        length = w["length_m"]
        max_turn = w["max_turn_deg"]
        cum_turn = w["cum_turn_deg"]
        sinuosity = w["sinuosity"]
        reasons = []

        # node evidence on the way: barriers (C) and crossings/signals (D)
        barriers = sorted({node_tags[r]["barrier"] for r in refs
                           if node_tags.get(r, {}).get("barrier")})
        crossings = [r for r in refs
                     if (nt := node_tags.get(r)) and (
                         nt.get("highway") in ("crossing", "traffic_signals")
                         or "crossing" in nt)]
        end_evid = 0
        for r in (refs[0], refs[-1]):
            nt = node_tags.get(r, {})
            if nt.get("highway") in ("crossing", "traffic_signals") or "crossing" in nt:
                end_evid = 1

        # junction degree at the way's endpoints
        deg = max(len(node_deg.get(refs[0], set())), len(node_deg.get(refs[-1], set())))
        junc = deg >= D_JUNC_DEG

        # --- Type-C (bottleneck) evidence ---
        width_m = parse_width(tags)
        maxw_m = parse_maxwidth(tags)
        nbr_ids = (node_deg.get(refs[0], set()) | node_deg.get(refs[-1], set())) - {wid}
        nbr_w = [x for x in (parse_width(way_tags.get(n, {})) for n in nbr_ids) if x]
        rel_narrow = (
            width_m is not None and len(nbr_w) >= C_NBR_MIN
            and width_m <= C_REL_NARROW * median(nbr_w)
        )
        c = False
        if width_m is not None and width_m <= C_NARROW_M:
            c = True
            reasons.append(f"narrow_width={width_m:g}")
        if maxw_m is not None and maxw_m <= C_MAXWIDTH_M:
            c = True
            reasons.append(f"maxwidth={maxw_m:g}")
        if barriers:
            c = True
            reasons.append("barrier=" + ",".join(barriers))
        if tags.get("bridge"):
            c = True
            reasons.append(f"bridge={tags['bridge']}")
        if tags.get("tunnel"):
            c = True
            reasons.append(f"tunnel={tags['tunnel']}")
        if tags.get("narrow") == "yes":
            c = True
            reasons.append("narrow=yes")
        if rel_narrow:
            c = True
            reasons.append(f"rel_narrow={width_m:g}<{median(nbr_w):.1f}")

        # --- Type-B (curve) evidence ---
        b = max_turn > A_MAX_TURN and (
            cum_turn >= B_MIN_CUM_TURN
            or max_turn >= B_SHARP_TURN
            or sinuosity >= B_MIN_SINUOSITY
        )
        if b:
            reasons.append(f"curve(cum={cum_turn:g},max={max_turn:g},sin={sinuosity:g})")

        # --- Type-D (junction forecourt) evidence ---
        d = length <= D_MAX_LEN and (junc or end_evid or bool(tags.get("junction")))
        if d:
            reasons.append(f"junc(deg={deg},cross_end={end_evid})")

        # --- summary type (precedence C > B > D > A) + independent flags ---
        straight = max_turn <= A_MAX_TURN
        if c:
            cell_type = "C"
        elif b:
            cell_type = "B"
        elif d:
            cell_type = "D"
        elif straight:
            cell_type = "A"
        else:
            cell_type = "other"
            reasons.append("mild_kink")

        in_band = straight and A_MIN_LEN <= length <= A_MAX_LEN
        splittable = straight and length > A_MAX_LEN
        if straight:
            reasons.append("in_band" if in_band else
                           "splittable" if splittable else "short")

        row = dict(w)
        row.pop("refs")
        row.pop("tags")
        row.update({
            "width_m": round(width_m, 2) if width_m is not None else "",
            "n_barriers": len(barriers),
            "n_crossings": len(crossings),
            "junc_deg_max": deg,
            "junc_node": end_evid,
            "cell_type": cell_type,
            "type_a": 1 if in_band else 0,
            "type_b": 1 if b else 0,
            "type_c": 1 if c else 0,
            "type_d": 1 if d else 0,
            "splittable": 1 if splittable else 0,
            "evidence": ";".join(reasons),
        })
        rows.append(row)

    # --- write CSV ---
    cols = ["way_id", "highway", "name", "name_zh", "n_nodes", "length_m",
            "max_turn_deg", "wander_deg", "cum_turn_deg", "sinuosity",
            "lat0", "lon0", "lat1", "lon1", "width_tag", "width_m",
            "n_barriers", "n_crossings", "junc_deg_max", "junc_node",
            "cell_type", "type_a", "type_b", "type_c", "type_d", "splittable",
            "evidence"]
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
        wcsv = csv.DictWriter(f, fieldnames=cols)
        wcsv.writeheader()
        for r in rows:
            wcsv.writerow({c: r[c] for c in cols})
    print(f"wrote {len(rows)} pedestrian-relevant ways -> {out_csv}")

    # --- console summary ---
    by_type = Counter(w["highway"] for w in rows)
    print("by highway type:", dict(by_type))
    by_cell = Counter(w["cell_type"] for w in rows)
    print("by cell_type   :", dict(by_cell))

    # Type-A: straight, 15-60 m (ready cells)
    typeA = [w for w in rows if w["type_a"]]
    typeA.sort(key=lambda w: -w["length_m"])
    n_primary = sum(1 for w in rows if w["cell_type"] == "A" and w["type_a"])
    print(f"\nType-A candidates (straight, 15-60 m): {len(typeA)} flagged "
          f"/ {n_primary} primary")
    for w in typeA[:40]:
        print(f"  way={w['way_id']:>10} len={w['length_m']:6.1f}m "
              f"turn={w['max_turn_deg']:5.1f}deg {w['highway']:12s} "
              f"name={w['name'][:28]} @({w['lat0']},{w['lon0']})")

    # Splittable straight ways (> 60 m, can be cut into 20-50 m cells)
    split = [w for w in rows if w["splittable"]]
    split.sort(key=lambda w: -w["length_m"])
    print(f"\nSplittable straight ways (>60 m): {len(split)}")
    for w in split[:20]:
        print(f"  way={w['way_id']:>10} len={w['length_m']:6.1f}m "
              f"turn={w['max_turn_deg']:5.1f}deg {w['highway']:12s} "
              f"name={w['name'][:28]}")

    # Type-B curves
    typeB = [w for w in rows if w["type_b"]]
    typeB.sort(key=lambda w: -w["cum_turn_deg"])
    n_primary = sum(1 for w in rows if w["cell_type"] == "B")
    print(f"\nType-B curves/corners: {len(typeB)} flagged / {n_primary} primary")
    for w in typeB[:30]:
        print(f"  way={w['way_id']:>10} len={w['length_m']:6.1f}m "
              f"cum={w['cum_turn_deg']:6.1f}deg max={w['max_turn_deg']:5.1f}deg "
              f"sin={w['sinuosity']:.3f} {w['highway']:12s} name={w['name'][:24]}")

    # Type-C bottlenecks
    typeC = [w for w in rows if w["type_c"]]
    typeC.sort(key=lambda w: (w["width_m"] == "", -w["length_m"]))
    n_primary = sum(1 for w in rows if w["cell_type"] == "C")
    print(f"\nType-C bottlenecks: {len(typeC)} flagged / {n_primary} primary")
    for w in typeC[:30]:
        print(f"  way={w['way_id']:>10} len={w['length_m']:6.1f}m "
              f"w={w['width_m'] if w['width_m'] != '' else '-':>5} "
              f"bar={w['n_barriers']} {w['highway']:12s} {w['evidence'][:46]}")

    # Type-D junction forecourts
    typeD = [w for w in rows if w["type_d"]]
    typeD.sort(key=lambda w: -w["junc_deg_max"])
    n_primary = sum(1 for w in rows if w["cell_type"] == "D")
    print(f"\nType-D junction forecourts: {len(typeD)} flagged / {n_primary} primary")
    for w in typeD[:20]:
        print(f"  way={w['way_id']:>10} len={w['length_m']:6.1f}m "
              f"deg={w['junc_deg_max']} cross_end={w['junc_node']} "
              f"{w['highway']:12s} name={w['name'][:24]}")

    return rows


if __name__ == "__main__":
    main(parse_args(sys.argv[1:]))
