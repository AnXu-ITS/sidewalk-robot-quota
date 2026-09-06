# -*- coding: utf-8 -*-
"""
p1_decoupled.py — Phase 3: supplemental SUMO scan for the decoupled design.
IDENTICAL protocol to p1_multicity.py (same simulator, same criterion,
30 seeds, same ascending ladder, same qr* rule). Only the input is different:
pipeline/cells/decoupled_cells.json (120 flat combos with explicit qp levels).

Usage:
  python p1_decoupled.py --n-procs 12
  python p1_decoupled.py --skip-sim     # resume / re-derive only
"""
import argparse
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import PATHS, SIM, CONSTRAINTS, ROBOT_FLOWS_ALL, N_SEEDS_SWEEP  # noqa: E402
from run_batch import run_batch  # noqa: E402

DECOUPLED_JSON = os.path.join(os.path.dirname(PATHS["root"]), "cells",
                              "decoupled_cells.json")
OUT_DIR = os.path.join(PATHS["root"], "outputs", "decoupled")

L = SIM["L"]
DELTA_V = CONSTRAINTS["delta_v"]
DFLOOR = CONSTRAINTS["density_floor"]
OUTMIN = CONSTRAINTS["outflow_ratio_min"]
OUTMAX = CONSTRAINTS["outflow_ratio_max"]
QR_LEVELS = sorted(q for q in ROBOT_FLOWS_ALL if q != 0)
MAX_QR = max(QR_LEVELS)


def load_combos():
    with open(DECOUPLED_JSON, encoding="utf-8") as f:
        return json.load(f)["combos"]


def flow_ok(fr):
    return OUTMIN <= fr <= OUTMAX


def combo_passes(sub, vbar):
    if len(sub) == 0 or vbar <= 0:
        return False
    mean_Rv = float(sub["mean_speed"].mean() / vbar)
    fr = float(sub["flow_ratio"].mean())
    dens = float(sub["mean_density"].mean())
    return mean_Rv >= (1.0 - DELTA_V) and flow_ok(fr) and dens <= DFLOOR


def main(n_procs=None, skip_sim=False, seeds=N_SEEDS_SWEEP, limit=None):
    os.makedirs(OUT_DIR, exist_ok=True)
    base_csv = os.path.join(OUT_DIR, "decoupled_baseline.csv")
    sweep_csv = os.path.join(OUT_DIR, "decoupled_sweep.csv")
    combos = load_combos()
    if limit:
        combos = combos[:limit]
    grid = [(c, f"{c['combo_id'] if 'combo_id' in c else c['cell_id']}|qp{c['qp']}")
            for c in combos]
    print(f"=== decoupled grid: {len(grid)} combos x {seeds} seeds ===",
          flush=True)

    # Phase A: baselines (qr=0)
    if skip_sim and os.path.exists(base_csv) and os.path.getsize(base_csv) > 0:
        base_df = pd.read_csv(base_csv)
    else:
        scen = []
        for c, tag in grid:
            cl = [list(p) for p in c["centerline"]]
            for seed in range(seeds):
                scen.append((c["W"], L, float(c["qp"]), 0.0, seed,
                             None, None, None, cl, tag))
        print(f"=== Phase A: {len(scen)} baseline scenarios ===", flush=True)
        base_df = run_batch(scen, n_procs=n_procs, out_csv=base_csv,
                            label="dcbase")

    vbar, bad = {}, set()
    for tag, g in base_df.groupby("tag", sort=True):
        vbar[tag] = float(g["mean_speed"].mean())
        if g["mean_density"].mean() > DFLOOR or \
                g["flow_ratio"].mean() < 0.85 or \
                g["flow_ratio"].mean() > OUTMAX:
            bad.add(tag)
    good = [(c, tag) for c, tag in grid if tag not in bad]
    print(f"=== Case-1: {len(bad)} combos -> q_r*=0; {len(good)} proceed ===",
          flush=True)

    # Phase B: ascending sweep, resumable per level
    active = {tag for _, tag in good}
    scen_of = {tag: c for c, tag in good}
    sweep_parts = []
    for qr in QR_LEVELS:
        part_csv = os.path.join(OUT_DIR, f"decoupled_sweep_{qr}.csv")
        if skip_sim and os.path.exists(part_csv) and os.path.getsize(part_csv) > 0:
            part = pd.read_csv(part_csv)
        else:
            if not active:
                print(f"  qr={qr}: no active combos", flush=True)
                break
            scen = []
            for tag in sorted(active):
                c = scen_of[tag]
                cl = [list(p) for p in c["centerline"]]
                for seed in range(seeds):
                    scen.append((c["W"], L, float(c["qp"]), float(qr), seed,
                                 None, None, None, cl, tag))
            print(f"  --- qr={qr}: {len(scen)} scenarios, "
                  f"{len(active)} active ---", flush=True)
            part = run_batch(scen, n_procs=n_procs, out_csv=part_csv,
                             label=f"dcsweep_{qr}")
        sweep_parts.append(part)
        for tag in list(active):
            sub = part[part["tag"] == tag]
            if len(sub) and not combo_passes(sub, vbar[tag]):
                active.discard(tag)

    sweep_df = pd.concat(sweep_parts, ignore_index=True) if sweep_parts \
        else pd.DataFrame(columns=["tag", "qr", "W", "L", "qp", "seed",
                                   "mean_speed", "flow_ratio", "mean_density"])
    sweep_df.to_csv(sweep_csv, index=False)

    qr_star = {tag: 0.0 for _, tag in grid}
    for tag, g in sweep_df.groupby("tag", sort=True):
        for qr, sub in g.groupby("qr", sort=True):
            if combo_passes(sub, vbar.get(tag, 0.0)):
                qr_star[tag] = max(qr_star[tag], float(qr))

    rec = []
    for c, tag in grid:
        base = base_df[base_df["tag"] == tag]
        rec.append(dict(
            combo_id=c.get("combo_id", c["cell_id"]), cell_id=c["cell_id"],
            city=c["city"], city_code=c.get("city_code"),
            type=c["type"], context=c["context"], W=round(c["W"], 3),
            L=c["L"], qp=c["qp"], x=round(c["qp"] / c["W"], 3),
            sinuosity=round(c.get("sinuosity", 1.0), 4),
            ood_flags=c.get("ood_flags", ""),
            vbar=round(float(base["mean_speed"].mean()), 3) if len(base) else 0.0,
            base_pass=tag not in bad,
            qr_star=float(qr_star[tag]),
            above_upper=bool(qr_star[tag] >= MAX_QR)))
    res = pd.DataFrame(rec).sort_values(["city", "qp"])
    res_csv = os.path.join(OUT_DIR, "decoupled_results.csv")
    res.to_csv(res_csv, index=False)
    print(f"\n=== decoupled q_r*: {int((res['qr_star']>0).sum())}/"
          f"{len(res)} nonzero -> {res_csv}", flush=True)
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-procs", type=int, default=None)
    ap.add_argument("--skip-sim", action="store_true")
    ap.add_argument("--seeds", type=int, default=N_SEEDS_SWEEP)
    ap.add_argument("--limit", type=int, default=None,
                    help="run only the first N combos")
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()
    if args.smoke:
        args.limit = args.limit or 3
        args.seeds = 3
    main(n_procs=args.n_procs, skip_sim=args.skip_sim,
         seeds=args.seeds, limit=args.limit)
