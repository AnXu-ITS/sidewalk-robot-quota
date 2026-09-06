# -*- coding: utf-8 -*-
"""
select_40.py — Phase 1: pick 40 representative cells for the decoupled
supplemental experiment (same 140-cell pool, no re-simulation of the main grid).

Stratification: 5 train cities x 6 + 2 test cities x 5 = 40.
Per city quotas by width bin: train {narrow:2, mid:2, wide:1, xwide:1};
test {narrow:2, mid:1, wide:1, xwide:1}. Within a bin prefer Type-B (curved)
for geometry diversity, then A. Deterministic (seed=7).

Note on length: the frozen protocol fixes every cell at L=50 m (the simulator's
measure zone is [15,35] m and flows are per-minute, i.e. length-insensitive by
construction), so the short/medium/long stratum is N/A in this experiment;
documented in the report rather than faked.
"""
import csv
import json
import os
import random

CELLS = r"C:\Users\xuan1\Desktop\UOL学习\配送机器人workbench\pipeline\cells\selected_cells.json"
OUT_CSV = r"C:\Users\xuan1\Desktop\UOL学习\配送机器人workbench\pipeline\cells\selected_40_cells.csv"
OUT_JSON = r"C:\Users\xuan1\Desktop\UOL学习\配送机器人workbench\pipeline\cells\selected_40_cells.json"

TRAIN = ["nyc", "amsterdam", "melbourne", "taipei", "newtaipei"]
TEST = ["seattle", "taoyuan"]


def bin_of(w):
    if w < 1.6:
        return "narrow"
    if w < 2.4:
        return "mid"
    if w < 3.5:
        return "wide"
    return "xwide"


def main():
    random.seed(7)
    data = json.load(open(CELLS, encoding="utf-8"))
    cells = data["cells"]
    sel = []
    for city, quota in [(c, {"narrow": 2, "mid": 2, "wide": 1, "xwide": 1})
                        for c in TRAIN] + \
                       [(c, {"narrow": 2, "mid": 1, "wide": 1, "xwide": 1})
                        for c in TEST]:
        pool = [c for c in cells if c["city"] == city]
        for bname, q in quota.items():
            cand = [c for c in pool if bin_of(c["W_eff"]) == bname]
            # prefer Type-B (curve), then A, then C; deterministic tiebreak
            cand.sort(key=lambda c: ({"B": 0, "A": 1, "C": 2, "D": 3}.get(c["type"], 9),
                                     c["W_eff"], c["cell_id"]))
            sel.extend(cand[:q])
    # write csv
    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        wcsv = csv.writer(f)
        wcsv.writerow(["cell_id", "city", "split", "W", "L", "context", "type",
                       "sinuosity", "orig_qp_lo", "orig_qp_hi", "orig_x_lo",
                       "orig_x_hi", "geom_approx", "rationale"])
        for c in sorted(sel, key=lambda c: (c["city"], c["cell_id"])):
            qlo, qhi = c["q_p_peak"]
            wcsv.writerow([
                c["cell_id"], c["city"], c["split"], c["W_eff"], c["L"],
                c["context"], c["type"], c["sinuosity"],
                qlo, qhi, round(qlo / c["W_eff"], 2), round(qhi / c["W_eff"], 2),
                c["geom_approx"],
                f"bin={bin_of(c['W_eff'])};type={c['type']};"
                f"ctx={c['context']};width-spread"])
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump({"n": len(sel), "cells": sel}, f, ensure_ascii=False, indent=1)
    by_city = {}
    for c in sel:
        by_city.setdefault(c["city"], []).append(round(c["W_eff"], 2))
    print("selected:", len(sel), "cells")
    for k, v in by_city.items():
        print(f"  {k:10s} n={len(v)} W={v}")


if __name__ == "__main__":
    main()
