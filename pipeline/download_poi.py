# -*- coding: utf-8 -*-
"""
download_poi.py — Overpass POI download around the selected cells.

One query per city: node[shop]/[amenity]/[tourism]/[railway]/[public_transport]
+ way[landuse] within 150 m of each cell midpoint, written as
pipeline/osm/<city>_poi.osm (XML, parsed later by annotate_flow.py).
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

CELLS = r"C:\Users\xuan1\Desktop\UOL学习\配送机器人workbench\pipeline\cells\selected_cells.json"
OUT_DIR = r"C:\Users\xuan1\Desktop\UOL学习\配送机器人workbench\pipeline\osm"
ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
RADIUS = 150

QUERY_TMPL = """[out:xml][timeout:300];
(
{clauses}
);
(._;>;);
out body;
"""


def build_query(cells):
    clauses = []
    for c in cells:
        lat, lon = c["lat0"], c["lon0"]
        for kind in ('node["shop"]', 'node["amenity"]', 'node["tourism"]',
                     'node["railway"]', 'node["public_transport"]',
                     'way["landuse"]'):
            clauses.append(f'  {kind}(around:{RADIUS},{lat:.6f},{lon:.6f});')
    return QUERY_TMPL.format(clauses="\n".join(clauses))


def post(url, data):
    req = urllib.request.Request(url, data=data.encode("utf-8"),
                                 headers={"User-Agent": "quota-pipeline/1.0",
                                          "Content-Type":
                                          "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return r.read()


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    data = json.load(open(CELLS, encoding="utf-8"))
    by_city = {}
    for c in data["cells"]:
        by_city.setdefault(c["city"], []).append(c)
    for city, cells in sorted(by_city.items()):
        out = os.path.join(OUT_DIR, f"{city}_poi.osm")
        if os.path.exists(out) and os.path.getsize(out) > 1000:
            print(f"[{city}] cached ({os.path.getsize(out)} bytes)", flush=True)
            continue
        # chunked queries (4 cells per chunk) + merge
        import xml.etree.ElementTree as ET
        parts = []
        CHUNK = 4
        for ci in range(0, len(cells), CHUNK):
            chunk = cells[ci:ci + CHUNK]
            query = build_query(chunk)
            body = "data=" + urllib.parse.quote(query, safe="")
            chunk_ok = False
            for attempt in range(3):
                for ep in ENDPOINTS:
                    try:
                        t0 = time.time()
                        resp = post(ep, body)
                        parts.append(resp)
                        print(f"[{city}] chunk {ci//CHUNK} "
                              f"{len(resp)} bytes via {ep} "
                              f"({time.time()-t0:.0f}s)", flush=True)
                        chunk_ok = True
                        break
                    except Exception as e:
                        print(f"[{city}] chunk {ci//CHUNK} {ep} failed: "
                              f"{type(e).__name__} (attempt {attempt+1})",
                              flush=True)
                        time.sleep(10)
                if chunk_ok:
                    break
            if not chunk_ok:
                print(f"[{city}] chunk {ci//CHUNK} FAILED 3x", flush=True)
                sys.exit(1)
            time.sleep(2)
        # merge chunk XMLs into one file
        merged_root = None
        for resp in parts:
            chunk_root = ET.fromstring(resp)
            if merged_root is None:
                merged_root = chunk_root
                continue
            for child in list(chunk_root):
                merged_root.append(child)
        tree = ET.ElementTree(merged_root)
        tree.write(out, encoding="utf-8", xml_declaration=True)
        print(f"[{city}] merged {len(parts)} chunks -> {os.path.getsize(out)} bytes",
              flush=True)
        time.sleep(2)
    print("ALL POI DOWNLOADS DONE ->", OUT_DIR)


if __name__ == "__main__":
    main()
