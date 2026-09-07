# -*- coding: utf-8 -*-
"""
Download official Hong Kong CSDI datasets (authoritative source) and compute SHA-256.

Sources:
  A) Highways Dept "Pavement Polygon"  dataset_id = hyd_rcd_1632210918434_60749
     layer INV_PG (Polygon, 64644 rows, 9 fields) via CSDI file-api (full HK).
  B) Lands Dept "Digital Topographic Map iB1000" dataset_id = landsd_rcd_1637223748322_25497
     TileIndex layer (Polygon, 3333 rows) via CSDI file-api.

Outputs go to data/raw/ and SHA256SUMS.txt.
"""
import hashlib
import json
import ssl
import sys
import time
import urllib.request

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

HDRS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"),
    "Accept": "*/*",
    "Accept-Encoding": "identity",
    "Referer": "https://portal.csdi.gov.hk/geoportal/",
}


def download(url, dest, label, chunk=1 << 20):
    t0 = time.time()
    sha = hashlib.sha256()
    got = 0
    req = urllib.request.Request(url, headers=HDRS)
    with urllib.request.urlopen(req, timeout=120, context=CTX) as r:
        total = int(r.headers.get("Content-Length") or 0)
        with open(dest, "wb") as f:
            while True:
                b = r.read(chunk)
                if not b:
                    break
                f.write(b)
                sha.update(b)
                got += len(b)
                if total:
                    sys.stderr.write(f"\r[{label}] {got}/{total} ({100.0*got/total:.1f}%)")
    dt = time.time() - t0
    sys.stderr.write(f"\r[{label}] DONE {got} bytes in {dt:.1f}s\n")
    return got, sha.hexdigest()


def main():
    base = "https://portal.csdi.gov.hk/csdi-webpage/file-api"
    jobs = [
        ("INV_PG_CSDI_INV_PG_converted.geojson",
         f"{base}?dataset_id=hyd_rcd_1632210918434_60749&format=geojson&layer_name=INV_PG",
         "PavementPolygon_INV_PG (full HK, GEOJSON)"),
        ("iB1000_Index_2026_08_13_TileIndex_converted.geojson",
         f"{base}?dataset_id=landsd_rcd_1637223748322_25497&format=geojson&layer_name=TileIndex",
         "iB1000 TileIndex (GEOJSON)"),
    ]
    sums = {}
    for fname, url, label in jobs:
        dest = f"data/raw/{fname}"
        got, sha = download(url, dest, label)
        sums[fname] = {"bytes": got, "sha256": sha, "url": url}
        print(json.dumps({fname: sums[fname]}, ensure_ascii=False, indent=2))
    with open("data/raw/SHA256SUMS.txt", "w", encoding="utf-8") as f:
        for fname, d in sums.items():
            f.write(f"{d['sha256']}  {fname}\n")
    print("SHA256SUMS written.")


if __name__ == "__main__":
    main()
