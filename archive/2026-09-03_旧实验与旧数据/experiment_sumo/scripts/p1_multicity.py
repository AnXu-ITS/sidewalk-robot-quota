# -*- coding: utf-8 -*-
"""
p1_multicity.py
===============
Multi-city ground-truth: run the SUMO-JuPedSim baseline + ascending robot sweep
over the selected sidewalk cells (data/cells.json, with a `city` field) and
derive the reference robot quota q_r* per (cell, pedestrian-flow) combo.

This is the parameterized generalization of p1_real_site.py (Bendemeer-only):
  * every selected cell across singapore / london / tokyo / amsterdam;
  * q_p levels taken from each cell's q_p_peak (desk/POI estimate);
  * stratified `--limit N` for pipeline validation before the full run;
  * resumable: per-q_r-level sweep CSVs are reused if present.

Sweep strategy (unchanged from P1): q_r is monotone in service degradation, so
we sweep ASCENDING and stop a combo at its first failing q_r.

Usage:
  python p1_multicity.py --limit 20 --seeds 30 --n-procs 8      # validation
  python p1_multicity.py --n-procs 12                            # full 100 cells
  python p1_multicity.py --skip-sim --limit 20                   # re-derive only

Outputs (outputs/p1_multicity/):
  multicity_baseline.csv, multicity_sweep_{qr}.csv, multicity_sweep.csv,
  multicity_results.csv
"""
import json
import math
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (PED, WALL, ROBOT, SIM, CONSTRAINTS, PATHS,
                    ROBOT_FLOWS_ALL, N_SEEDS_SWEEP)  # noqa: E402
from run_batch import run_batch  # noqa: E402

L = SIM["L"]
CELLS_JSON = os.path.join(PATHS["root"], "..", "sumo_jupedsim", "data", "cells.json")
OUT_DIR = os.path.join(PATHS["root"], "outputs", "p1_multicity")

DFLOOR = CONSTRAINTS["density_floor"]
DELTA_V = CONSTRAINTS["delta_v"]
OUTMIN = CONSTRAINTS["outflow_ratio_min"]
OUTMAX = CONSTRAINTS["outflow_ratio_max"]
QR_LEVELS = sorted(q for q in ROBOT_FLOWS_ALL if q != 0)
MAX_QR = max(QR_LEVELS)


def load_cells():
    with open(CELLS_JSON, encoding="utf-8") as f:
        return json.load(f)["cells"]


def stratified_order(cells):
    """Order cells round-robin across (city, type) buckets, spreading widths,
    so the first N cells cover the city x type grid."""
    buckets = {}
    for c in cells:
        buckets.setdefault((c["city"], c["type"]), []).append(c)
    for k in buckets:
        buckets[k].sort(key=lambda c: c["W_eff"])
    order, keys = [], list(buckets)
    while any(buckets.values()):
        for k in list(keys):
            if buckets[k]:
                order.append(buckets[k].pop(0))
        keys = [k for k in keys if buckets[k]]
    return order


def build_grid(sel):
    """(cell, qp, tag) for peak-low and peak-high flow per cell."""
    grid = []
    for c in sel:
        qlo = int(round(c["q_p_peak"][0]))
        qhi = int(round(c["q_p_peak"][1]))
        for qp in sorted(set([qlo, qhi])):
            grid.append((c, qp, f"{c['cell_id']}|qp{qp}"))
    return grid


def flow_ok(fr):
    return OUTMIN <= fr <= OUTMAX


def combo_passes(sub, vbar):
    if len(sub) == 0 or vbar <= 0:
        return False
    mean_Rv = float(sub["mean_speed"].mean() / vbar)
    fr = float(sub["flow_ratio"].mean())
    dens = float(sub["mean_density"].mean())
    return mean_Rv >= (1.0 - DELTA_V) and flow_ok(fr) and dens <= DFLOOR


def main(n_procs=None, skip_sim=False, limit=None, seeds=N_SEEDS_SWEEP):
    os.makedirs(OUT_DIR, exist_ok=True)
    base_csv = os.path.join(OUT_DIR, "multicity_baseline.csv")
    sweep_csv = os.path.join(OUT_DIR, "multicity_sweep.csv")

    cells = stratified_order(load_cells())
    if limit:
        cells = cells[:limit]
    grid = build_grid(cells)
    all_tags = {tag for _, _, tag in grid}
    print(f"=== multicity grid: {len(cells)} cells x "
          f"{len(grid) // max(1, len(cells))} qp levels = {len(grid)} combos, "
          f"seeds={seeds} ===", flush=True)
    for c, qp, tag in grid:
        print(f"  {tag:34s} {c['city']:10s} {c['type']} W={c['W_eff']:.2f} "
              f"qp={qp} ctx={c['context']:14s} pts={len(c['centerline'])}",
              flush=True)

    # ---- Phase A: baselines (qr=0) ------------------------------------
    if skip_sim and os.path.exists(base_csv) and os.path.getsize(base_csv) > 0:
        base_df = pd.read_csv(base_csv)
        print("=== reusing baseline CSV ===", flush=True)
    else:
        base_scen = []
        for c, qp, tag in grid:
            cl = [list(p) for p in c["centerline"]]
            for seed in range(seeds):
                base_scen.append((c["W_eff"], L, float(qp), 0.0, seed,
                                  None, None, None, cl, tag))
        print(f"=== Phase A: {len(base_scen)} baseline scenarios ===", flush=True)
        base_df = run_batch(base_scen, n_procs=n_procs, out_csv=base_csv,
                            label="mcbase")

    vbar = {}
    bad = set()
    for tag, g in base_df.groupby("tag", sort=True):
        vbar[tag] = float(g["mean_speed"].mean())
        if g["mean_density"].mean() > DFLOOR or \
                g["flow_ratio"].mean() < 0.85 or \
                g["flow_ratio"].mean() > OUTMAX:
            bad.add(tag)
    good = [(c, qp, tag) for c, qp, tag in grid if tag not in bad]
    print(f"=== Case-1 (baseline over capacity): {len(bad)} combos -> q_r*=0; "
          f"{len(good)} proceed ===", flush=True)

    # ---- Phase B: ascending robot sweep, resumable --------------------
    active = {tag for _, _, tag in good}
    scen_of = {tag: (c, qp) for c, qp, tag in good}
    sweep_parts = []
    for qr in QR_LEVELS:
        part_csv = os.path.join(OUT_DIR, f"multicity_sweep_{qr}.csv")
        if skip_sim and os.path.exists(part_csv) and os.path.getsize(part_csv) > 0:
            part = pd.read_csv(part_csv)
            print(f"  [resume] qr={qr}: reusing {len(part)} rows", flush=True)
        else:
            if not active:
                print(f"  qr={qr}: no active combos, stop sweep", flush=True)
                break
            scen = []
            for tag in sorted(active):
                c, qp = scen_of[tag]
                cl = [list(p) for p in c["centerline"]]
                for seed in range(seeds):
                    scen.append((c["W_eff"], L, float(qp), float(qr), seed,
                                 None, None, None, cl, tag))
            print(f"  --- qr={qr}: {len(scen)} scenarios, "
                  f"{len(active)} active ---", flush=True)
            part = run_batch(scen, n_procs=n_procs, out_csv=part_csv,
                             label=f"mcsweep_{qr}")
        sweep_parts.append(part)
        for tag in list(active):
            sub = part[part["tag"] == tag]
            if len(sub) and not combo_passes(sub, vbar[tag]):
                active.discard(tag)

    sweep_df = pd.concat(sweep_parts, ignore_index=True) if sweep_parts \
        else pd.DataFrame()
    sweep_df.to_csv(sweep_csv, index=False)

    # ---- derive q_r* ----------------------------------------------------
    qr_star = {tag: 0.0 for tag in all_tags}
    for tag, g in sweep_df.groupby("tag", sort=True):
        for qr, sub in g.groupby("qr", sort=True):
            if combo_passes(sub, vbar.get(tag, 0.0)):
                qr_star[tag] = max(qr_star[tag], float(qr))

    rec = []
    for c, qp, tag in grid:
        base = base_df[base_df["tag"] == tag]
        rec.append(dict(
            cell_id=c["cell_id"], city=c["city"], city_code=c.get("city_code"),
            type=c["type"], context=c["context"], W=round(c["W_eff"], 3),
            sinuosity=round(c.get("sinuosity", 1.0), 4),
            qp=qp,
            vbar=round(float(base["mean_speed"].mean()), 3) if len(base) else 0.0,
            base_pass=tag not in bad,
            dens_base=round(float(base["mean_density"].mean()), 3) if len(base) else 0.0,
            fr_base=round(float(base["flow_ratio"].mean()), 3) if len(base) else 0.0,
            qr_star=float(qr_star[tag]),
            above_upper=bool(qr_star[tag] >= MAX_QR)))
    res = pd.DataFrame(rec).sort_values(["city", "type", "qp"])

    res_csv = os.path.join(OUT_DIR, "multicity_results.csv")
    res.to_csv(res_csv, index=False)

    print("\n=== multicity q_r* ===", flush=True)
    print(res[["cell_id", "city", "type", "context", "W", "qp", "qr_star",
               "above_upper", "base_pass"]].to_string(index=False), flush=True)
    n = len(res)
    nonzero = int((res["qr_star"] > 0).sum())
    print(f"nonzero-quota combos: {nonzero}/{n}; wrote {res_csv}", flush=True)
    return res


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-procs", type=int, default=None)
    ap.add_argument("--skip-sim", action="store_true")
    ap.add_argument("--limit", type=int, default=None,
                    help="run only the first N cells in stratified order")
    ap.add_argument("--seeds", type=int, default=N_SEEDS_SWEEP)
    ap.add_argument("--smoke", action="store_true",
                    help="tiny run to validate the multi-city pipeline")
    args = ap.parse_args()
    if args.smoke:
        args.limit = args.limit or 3
        args.seeds = 3
    main(n_procs=args.n_procs, skip_sim=args.skip_sim,
         limit=args.limit, seeds=args.seeds)
