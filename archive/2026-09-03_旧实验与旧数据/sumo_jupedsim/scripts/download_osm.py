# -*- coding: utf-8 -*-
"""
download_osm.py
===============
Download pedestrian-relevant OSM data + POI/landuse/railway supplements for the
multi-city quota-algorithm training set, via the Overpass API.

For each city (except the already-downloaded Singapore anchor) two files land in
data/osm/<city>/:
  <city>_road.osm  -- footway/pedestrian/path/living_street ways (or foot=yes /
                      sidewalk=*) with their nodes  -> cell extraction
  <city>_poi.osm    -- amenity/shop/landuse/railway(station, subway_entrance)
                      -> context classification (q_p prior)

Usage:
  python download_osm.py [--cities london,tokyo,amsterdam]
"""
import argparse
import os
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data", "osm")
OVERPASS = "https://overpass-api.de/api/interpreter"
OVERPASS_FALLBACKS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
UA = "PhD-quota-research/1.0 (contact: local research use)"

# city -> (S, W, N, E) bbox
CITIES = {
    "london":    (51.506, -0.144, 51.518, -0.118),  # Soho/Covent Garden/West End
    "tokyo":     (35.685, 139.693, 35.700, 139.708),  # Shinjuku + Kabukicho
    "amsterdam": (52.358, 4.868, 52.378, 4.902),      # Jordaan + canal belt
}


def road_query(bbox):
    s, w, n, e = bbox
    return (
        "[out:xml][timeout:300];\n"
        "(\n"
        f'  way["highway"~"^(footway|pedestrian|path|living_street)$"]'
        f"({s},{w},{n},{e});\n"
        f'  way["foot"~"^(yes|designated)$"]({s},{w},{n},{e});\n'
        f'  way["sidewalk"~"^(both|left|right|yes)$"]({s},{w},{n},{e});\n'
        ");\n"
        "(._;>;);\n"   # union ways with their nodes (node TAGS kept -> barrier/
        "out body;\n"  # crossing/traffic_signals evidence for analyze_osm.py)
    )


def poi_query(bbox):
    s, w, n, e = bbox
    return (
        "[out:xml][timeout:300];\n"
        "(\n"
        f'  node["amenity"]({s},{w},{n},{e});\n'
        f'  node["shop"]({s},{w},{n},{e});\n'
        f'  way["landuse"]({s},{w},{n},{e});\n'
        f'  relation["landuse"]({s},{w},{n},{e});\n'
        f'  node["railway"~"^(station|subway_entrance)$"]({s},{w},{n},{e});\n'
        f'  way["railway"~"^(rail|subway|tram)$"]({s},{w},{n},{e});\n'
        ");\n"
        "out body;\n"
        ">;\n"
        "out skel qt;\n"
    )


def fetch(query, dest, retries=3):
    body = urllib.parse.urlencode({"data": query}).encode("utf-8")
    endpoints = [OVERPASS] + OVERPASS_FALLBACKS
    for ep in endpoints:
        for attempt in range(1, retries + 1):
            try:
                req = urllib.request.Request(ep, data=body,
                                             headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=600) as r:
                    payload = r.read()
                if len(payload) > 5000 and b"<osm" in payload[:2000]:
                    with open(dest, "wb") as f:
                        f.write(payload)
                    return len(payload)
                print(f"  attempt {attempt}/{retries} via {ep}: "
                      f"bad payload len={len(payload)}")
            except Exception as exc:  # noqa: BLE001
                print(f"  attempt {attempt}/{retries} via {ep} failed: {exc}")
            time.sleep(10 * attempt)
    return -1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cities", default=",".join(CITIES))
    args = ap.parse_args()
    cities = [c.strip() for c in args.cities.split(",") if c.strip()]

    os.makedirs(DATA, exist_ok=True)
    for city in cities:
        if city not in CITIES:
            print(f"!! unknown city {city}, skip")
            continue
        bbox = CITIES[city]
        cdir = os.path.join(DATA, city)
        os.makedirs(cdir, exist_ok=True)

        for kind, qfn in (("road", road_query), ("poi", poi_query)):
            dest = os.path.join(cdir, f"{city}_{kind}.osm")
            print(f"[{city}/{kind}] querying Overpass bbox={bbox} ...")
            n = fetch(qfn(bbox), dest)
            if n < 0:
                print(f"!! {city}/{kind} download FAILED")
            else:
                mb = n / 1e6
                print(f"    -> {dest}  ({mb:.2f} MB)")
        print()


if __name__ == "__main__":
    sys.exit(main())
