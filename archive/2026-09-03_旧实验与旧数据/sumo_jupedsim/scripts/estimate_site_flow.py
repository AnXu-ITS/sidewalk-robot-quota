# -*- coding: utf-8 -*-
"""
Desk-based estimation of pedestrian-flow CONTEXT for the multi-city sidewalk
cells (data/cells.json), replacing the build_cells heuristic with POI evidence.

Per cell (scored at its lat0/lon0):
  * MRT-frontage  : railway station / subway_entrance within 60 m, or within
                    120 m for a D-type junction forecourt
  * tourism/mixed : >=3 tourism amenities (attraction/museum/gallery/theatre/
                    cinema/pub/bar/nightclub/hotel) and not retail-swamped
                    (n_com < 20)
  * commercial    : shop nodes or commercial amenities dense within 100 m, or
                    landuse=retail/commercial nearby
  * residential   : otherwise (incl. landuse=residential)

W_eff is KEPT from cells.json (geometry: width tag or highway default) -- the
width axis must stay a geometry fact, not a context prior. Only q_p is
re-derived:  q_p = x_ctx * W_eff  with the §5 priors (peak / off-peak ranges).

The multi-city POI downloads (data/osm/<city>/<city>_poi.osm) carry
amenity/shop/landuse/railway but NOT building footprints, so the classifier is
shop/amenity/landuse/railway-based (uniform across all four cities).

Outputs:
  data/cells.json             updated in place (context + q_p + context_src=poi)
  data/site_flow_estimate.csv per-cell context/q_p table (all cities)
  data/context_coverage.md    context axis vs §2 targets (~35/30/25/10)

Usage:
  python estimate_site_flow.py [--cells data/cells.json] [--out data/cells.json]
"""
import argparse
import csv
import json
import math
import os
import sys
import xml.etree.ElementTree as ET
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
OSM_DIR = os.path.join(DATA, "osm")
CELLS_JSON = os.path.join(DATA, "cells.json")
OUT_EST = os.path.join(DATA, "site_flow_estimate.csv")
OUT_CTX = os.path.join(DATA, "context_coverage.md")

CITY_OSM = {"singapore": "bendemeer", "london": "london",
            "tokyo": "tokyo", "amsterdam": "amsterdam"}

R = 6371000.0
RADIUS = 100.0    # m, amenity/shop/landuse evidence radius
MRT_R = 150.0     # m, rail-station frontage radius (reporting only)
FRONTAGE_R = 60.0   # m, hard station-forecourt distance
FORECOURT_D_R = 120.0  # m, D-type junction forecourt near a station

# §5 context -> unit-width bidirectional flow x (ped/min/m): peak / off-peak
X_CTX = {
    "residential":   {"peak": (5.0, 12.0), "off": (1.5, 3.0)},
    "commercial":    {"peak": (15.0, 25.0), "off": (4.0, 7.0)},
    "MRT-frontage":  {"peak": (30.0, 45.0), "off": (8.0, 12.0)},
    "tourism/mixed": {"peak": (20.0, 35.0), "off": (6.0, 10.0)},
}
CTX_TARGETS = {"residential": 35, "commercial": 30,
               "MRT-frontage": 25, "tourism/mixed": 10}

COMMERCIAL_AMEN = {
    "cafe", "restaurant", "fast_food", "food_court", "supermarket",
    "marketplace", "convenience", "pharmacy", "bank", "post_office",
    "clinic", "school", "hospital", "kindergarten", "dentist",
}
TOURISM_AMEN = {
    "attraction", "museum", "gallery", "theatre", "cinema", "pub", "bar",
    "nightclub", "hotel", "hostel", "viewpoint", "fountain", "artwork",
    "biergarten", "casino",
}
LANDUSE_PRIORITY = ["tourism", "retail", "commercial", "residential",
                    "industrial", "recreation_ground"]


def hav(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def resolve_poi(city):
    osm = CITY_OSM.get(city, city)
    for p in (os.path.join(OSM_DIR, f"{osm}_poi.osm"),
              os.path.join(OSM_DIR, osm, f"{osm}_poi.osm")):
        if os.path.exists(p):
            return p
    return None


def parse_poi(path):
    """Return dict: mrt [(lat,lon)], shop [(lat,lon)], amen [(lat,lon,kind)],
    landuse [(lat,lon,tag)] -- centroids for ways, points for nodes."""
    tree = ET.parse(path)
    root = tree.getroot()
    mrt, shop, amen = [], [], []
    # ways -> centroids (landuse polygons; buildings if present)
    nodes = {}
    for nd in root.iter("node"):
        lat, lon = nd.get("lat"), nd.get("lon")
        if lat is not None and lon is not None:
            nodes[nd.get("id")] = (float(lat), float(lon))
    landuse = []
    for w in root.iter("way"):
        tags = {t.get("k"): t.get("v") for t in w.findall("tag")}
        lu = tags.get("landuse")
        refs = [nd.get("ref") for nd in w.findall("nd")]
        pts = [nodes[r] for r in refs if r in nodes]
        if not pts:
            continue
        clat = sum(p[0] for p in pts) / len(pts)
        clon = sum(p[1] for p in pts) / len(pts)
        if lu:
            landuse.append((clat, clon, lu))
        b = tags.get("building")
        if b:
            # map building kind to the same amen/shop signals as the original
            if b in ("residential", "house", "apartments", "terrace"):
                pass  # residential buildings do not change the default
            elif b in ("commercial", "retail", "office", "hotel", "school",
                       "hospital"):
                shop.append((clat, clon))
    for nd in root.iter("node"):
        tags = {t.get("k"): t.get("v") for t in nd.findall("tag")}
        lat, lon = nd.get("lat"), nd.get("lon")
        if lat is None or lon is None:
            continue
        lat, lon = float(lat), float(lon)
        if tags.get("railway") in ("station", "subway_entrance", "halt") \
                or tags.get("public_transport") == "station":
            mrt.append((lat, lon))
        if "shop" in tags:
            shop.append((lat, lon))
        a = tags.get("amenity")
        if a:
            amen.append((lat, lon, a))
    return {"mrt": mrt, "shop": shop, "amen": amen, "landuse": landuse}


def classify(d_mrt, n_shop, n_com, n_tour, lu, ctype):
    # station forecourt: truly at a station, or a D-type junction forecourt
    # within the frontage ring (otherwise dense station districts would label
    # every nearby commercial street as MRT-frontage).
    if d_mrt <= FRONTAGE_R or (d_mrt <= FORECOURT_D_R and ctype == "D"):
        return "MRT-frontage"
    # tourism/mixed: tourism amenity present but not swamped by retail/services
    if n_tour >= 3 and n_com < 20:
        return "tourism/mixed"
    if lu in ("retail", "commercial") or n_shop >= 3 or n_com >= 5:
        return "commercial"
    return "residential"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", default=CELLS_JSON)
    ap.add_argument("--out", default=None, help="defaults to --cells (in place)")
    ap.add_argument("--radius", type=float, default=RADIUS)
    ap.add_argument("--mrt-radius", type=float, default=MRT_R)
    args = ap.parse_args()

    with open(args.cells, encoding="utf-8") as f:
        data = json.load(f)
    cells = data["cells"]

    poi_cache = {}
    for c in cells:
        city = c["city"]
        if city not in poi_cache:
            poi_path = resolve_poi(city)
            poi_cache[city] = parse_poi(poi_path) if poi_path else None
        poi = poi_cache[city]
        lat, lon = c["lat0"], c["lon0"]
        if poi is None:
            c["context_src"] = "heuristic"
            continue
        d_mrt = min((hav(lat, lon, m[0], m[1]) for m in poi["mrt"]),
                    default=1e9)
        n_shop = sum(1 for s in poi["shop"] if hav(lat, lon, s[0], s[1]) <= args.radius)
        n_com = sum(1 for a in poi["amen"]
                    if a[2] in COMMERCIAL_AMEN and hav(lat, lon, a[0], a[1]) <= args.radius)
        n_tour = sum(1 for a in poi["amen"]
                     if a[2] in TOURISM_AMEN and hav(lat, lon, a[0], a[1]) <= args.radius)
        lu_counts = Counter()
        for bl, bo, tag in poi["landuse"]:
            if hav(lat, lon, bl, bo) <= args.radius:
                lu_counts[tag] += 1
        lu = next((t for t in LANDUSE_PRIORITY if lu_counts.get(t)), "")

        ctx = classify(d_mrt, n_shop, n_com, n_tour, lu, c["type"])
        W = c["W_eff"]
        xp = X_CTX[ctx]["peak"]
        xo = X_CTX[ctx]["off"]
        c["context"] = ctx
        c["context_src"] = "poi"
        c["q_p_peak"] = [round(xp[0] * W, 1), round(xp[1] * W, 1)]
        c["q_p_off"] = [round(xo[0] * W, 1), round(xo[1] * W, 1)]
        c["q_p_src"] = "prior"
        c["d_mrt_m"] = round(d_mrt, 0) if d_mrt < 1e8 else None
        c["n_shop"] = n_shop
        c["n_amen_com"] = n_com
        c["n_amen_tour"] = n_tour
        c["landuse"] = lu

    out_path = args.out or args.cells
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"updated {len(cells)} cells -> {out_path}")

    # per-cell estimate CSV (human review)
    cols = ["cell_id", "city", "type", "context", "context_src", "W_eff",
            "q_p_peak", "q_p_off", "d_mrt_m", "n_shop", "n_amen_com",
            "n_amen_tour", "landuse"]
    with open(OUT_EST, "w", newline="", encoding="utf-8-sig") as f:
        wcsv = csv.DictWriter(f, fieldnames=cols)
        wcsv.writeheader()
        for c in sorted(cells, key=lambda x: (x["city"], x["cell_id"])):
            wcsv.writerow({k: c.get(k) for k in cols})

    # context axis vs §2 targets
    by_city = Counter()
    ctx_all = Counter()
    for c in cells:
        ctx_all[c["context"]] += 1
        by_city[(c["city"], c["context"])] += 1
    print("\ncontext counts (all cities):", dict(ctx_all))
    print("per city:")
    for city in sorted({c["city"] for c in cells}):
        row = {ctx: by_city[(city, ctx)] for ctx in X_CTX}
        print(f"  {city:10s} " + "  ".join(f"{k}={v}" for k, v in row.items()))

    lines = ["# Context axis coverage vs §2 grid (POI-refined)",
             "",
             "| context | selected | §2 target | gap (+over / -short) |",
             "|---|---|---|---|"]
    for ctx, target in CTX_TARGETS.items():
        got = ctx_all.get(ctx, 0)
        gap = got - target
        lines.append(f"| {ctx} | {got} | ~{target} | "
                     + (f"+{gap}" if gap > 0 else
                        f"{gap}" if gap < 0 else "达标"))
    lines += ["",
              "| city | residential | commercial | MRT-frontage | tourism/mixed |",
              "|---|---|---|---|---|"]
    for city in sorted({c["city"] for c in cells}):
        lines.append(f"| {city} | {by_city[(city, 'residential')]} | "
                     f"{by_city[(city, 'commercial')]} | "
                     f"{by_city[(city, 'MRT-frontage')]} | "
                     f"{by_city[(city, 'tourism/mixed')]} |")
    lines.append("")
    lines.append("> W_eff 保持几何来源（width 标签/ highway 默认），q_p = x_ctx·W_eff（§5 先验）。")
    with open(OUT_CTX, "w", encoding="utf-8-sig") as f:
        f.write("\n".join(lines) + "\n")
    print(f"wrote {OUT_EST} and {OUT_CTX}")


if __name__ == "__main__":
    main()
