# -*- coding: utf-8 -*-
"""
p1_real_site.py
===============
P1 (real-site validation): run the ground-truth quota sweep on the real
Bendemeer sidewalk cells (real centerline geometry + estimated W_eff / q_p) and
compare the simulated reference quota q_r* against the fitted algorithm q̂_r.

Grid: representative cells (2 per land-use context) x peak-flow levels
(peak-low, peak-high from the desk estimate).

Sweep strategy: q_r is monotone in service degradation, so we sweep q_r in
ASCENDING order and stop a (cell, qp) combo at its FIRST failing q_r.  This is
essential for the dense MRT-frontage cells, where a single robot can take ~30-60s
per run.

Outputs (outputs/p1_real_site/):
  p1_baseline.csv, p1_sweep.csv, p1_results.csv (+ console summary)
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
from validate import load_model  # noqa: E402
from fit_quota import predict_quota  # noqa: E402

L = SIM["L"]
P1_DATA = os.path.join(PATHS["root"], "..", "sumo_jupedsim", "data", "cells.json")
OUT_DIR = os.path.join(PATHS["root"], "outputs", "p1_real_site")

CONTEXTS = ["residential", "commercial", "MRT-frontage"]

DFLOOR = CONSTRAINTS["density_floor"]
DELTA_V = CONSTRAINTS["delta_v"]
OUTMIN = CONSTRAINTS["outflow_ratio_min"]
OUTMAX = CONSTRAINTS["outflow_ratio_max"]
MAX_QR = max(q for q in ROBOT_FLOWS_ALL if q != 0)


def load_cells():
    with open(P1_DATA, encoding="utf-8") as f:
        return json.load(f)["cells"]


def pick_representatives(cells, per_context=2):
    """2 cells per context, preferring ones with more centerline points."""
    sel = []
    for ctx in CONTEXTS:
        pool = [c for c in cells if c["context"] == ctx]
        pool.sort(key=lambda c: -len(c["centerline"]))
        sel.extend(pool[:per_context])
    return sel


def build_grid(sel):
    """(cell, qp, tag) for peak-low and peak-high flow per cell."""
    grid = []
    for c in sel:
        qlo = int(round(c["q_p_peak"][0]))
        qhi = int(round(c["q_p_peak"][1]))
        for qp in sorted(set([qlo, qhi])):
            tag = f"{c['cell_id']}|qp{qp}"
            grid.append((c, qp, tag))
    return grid


def flow_ok(fr):
    return OUTMIN <= fr <= OUTMAX


def combo_passes(sub, vbar):
    """Mean-over-seeds pedestrian-first pass for one (tag, qr) group."""
    if len(sub) == 0 or vbar <= 0:
        return False
    mean_Rv = float(sub["mean_speed"].mean() / vbar)
    fr = float(sub["flow_ratio"].mean())
    dens = float(sub["mean_density"].mean())
    return mean_Rv >= (1.0 - DELTA_V) and flow_ok(fr) and dens <= DFLOOR


def main(n_procs=None, skip_sim=False):
    os.makedirs(OUT_DIR, exist_ok=True)
    base_csv = os.path.join(OUT_DIR, "p1_baseline.csv")
    sweep_csv = os.path.join(OUT_DIR, "p1_sweep.csv")

    cells = load_cells()
    sel = pick_representatives(cells)
    grid = build_grid(sel)
    all_tags = {tag for _, _, tag in grid}
    print(f"=== P1 grid: {len(sel)} cells x {len(grid) // len(sel)} qp levels = "
          f"{len(grid)} (cell,qp) combos ===", flush=True)
    for c, qp, tag in grid:
        print(f"  {tag:34s} W={c['W_eff']:.2f} qp={qp} ctx={c['context']} "
              f"pts={len(c['centerline'])}", flush=True)

    if skip_sim and os.path.exists(base_csv) and os.path.exists(sweep_csv):
        base_df = pd.read_csv(base_csv)
        sweep_df = pd.read_csv(sweep_csv)
        print("=== Reusing existing P1 baseline/sweep CSVs (skip_sim) ===",
              flush=True)
    else:
        # ---- Phase A: baselines (qr=0) ------------------------------
        base_scen = []
        for c, qp, tag in grid:
            cl = [list(p) for p in c["centerline"]]
            for seed in range(N_SEEDS_SWEEP):
                base_scen.append((c["W_eff"], L, float(qp), 0.0, seed,
                                  None, None, None, cl, tag))
        print(f"=== Phase A: {len(base_scen)} baseline scenarios ===", flush=True)
        base_df = run_batch(base_scen, n_procs=n_procs, out_csv=base_csv,
                            label="p1base")

        # ---- Phase B: Case-1 detection ------------------------------
        bad = set()
        for tag, g in base_df.groupby("tag", sort=True):
            if g["mean_density"].mean() > DFLOOR or \
                    g["flow_ratio"].mean() < 0.85 or \
                    g["flow_ratio"].mean() > OUTMAX:
                bad.add(tag)
        good = [(c, qp, tag) for c, qp, tag in grid if tag not in bad]
        print(f"=== Phase B: {len(bad)} over-capacity combos (q_r*=0); "
              f"{len(good)} proceed to robot sweep ===", flush=True)
        for t in sorted(bad):
            print(f"  Case-1: {t}", flush=True)

        # ---- Phase C: ascending robot sweep with early stopping -----
        vbar = {tag: float(base_df[base_df["tag"] == tag]["mean_speed"].mean())
                for tag in all_tags}
        active = {tag for _, _, tag in good}
        sweep_parts = []
        for qr in sorted(q for q in ROBOT_FLOWS_ALL if q != 0):
            if not active:
                break
            scen = []
            for c, qp, tag in good:
                if tag not in active:
                    continue
                cl = [list(p) for p in c["centerline"]]
                for seed in range(N_SEEDS_SWEEP):
                    scen.append((c["W_eff"], L, float(qp), float(qr), seed,
                                 None, None, None, cl, tag))
            print(f"--- qr={qr}: {len(scen)} scenarios, "
                  f"{len(active)} active combos ---", flush=True)
            part = run_batch(scen, n_procs=n_procs,
                             out_csv=os.path.join(OUT_DIR, f"p1_sweep_{qr}.csv"),
                             label=f"p1sweep_{qr}")
            sweep_parts.append(part)
            for c, qp, tag in list(good):
                if tag not in active:
                    continue
                sub = part[part["tag"] == tag]
                if len(sub) == 0:
                    continue
                if combo_passes(sub, vbar[tag]):
                    continue  # still passing; keep active
                active.discard(tag)  # first failure -> stop this combo
        sweep_df = pd.concat(sweep_parts, ignore_index=True) \
            if sweep_parts else pd.DataFrame()
        sweep_df.to_csv(sweep_csv, index=False)

    # ---- unified derivation (works for sim and skip_sim) ------------
    vbar = {tag: float(base_df[base_df["tag"] == tag]["mean_speed"].mean())
            if len(base_df[base_df["tag"] == tag]) else 0.0
            for tag in all_tags}
    bad = set()
    for tag, g in base_df.groupby("tag", sort=True):
        if g["mean_density"].mean() > DFLOOR or \
                g["flow_ratio"].mean() < 0.85 or \
                g["flow_ratio"].mean() > OUTMAX:
            bad.add(tag)

    qr_star = {tag: 0.0 for tag in all_tags}
    for tag, g in sweep_df.groupby("tag", sort=True):
        for qr, sub in g.groupby("qr", sort=True):
            if combo_passes(sub, vbar[tag]):
                qr_star[tag] = max(qr_star[tag], float(qr))
    above = {tag: qr_star[tag] >= MAX_QR for tag in all_tags}

    # ---- assemble results -------------------------------------------
    rec = []
    for c, qp, tag in grid:
        base = base_df[base_df["tag"] == tag]
        rec.append(dict(
            cell_id=c["cell_id"], context=c["context"], W=c["W_eff"], qp=qp,
            vbar=round(float(base["mean_speed"].mean()), 3) if len(base) else 0.0,
            base_pass=tag not in bad,
            dens_base=round(float(base["mean_density"].mean()), 3) if len(base) else 0.0,
            fr_base=round(float(base["flow_ratio"].mean()), 3) if len(base) else 0.0,
            qr_star=float(qr_star[tag]), above_upper=bool(above[tag])))
    res = pd.DataFrame(rec)

    # ---- predict q̂_r with the fitted algorithm ----------------------
    x_crit, W_min, A, B, iso, C_knots, q_max = load_model()
    preds = []
    for r in rec:
        qp, W = r["qp"], r["W"]
        qA = float(predict_quota([qp], [W], "A", A, x_crit, W_min, C_knots, q_max)[0])
        qB = float(predict_quota([qp], [W], "B", B, x_crit, W_min, C_knots, q_max)[0])
        qI = float(predict_quota([qp], [W], "A-iso", iso, x_crit, W_min, C_knots, q_max)[0])
        qA_r = round(qA * 2) / 2.0
        qA_f = math.floor(qA)
        preds.append(dict(cell_id=r["cell_id"], qp=qp, qhat_A=round(qA, 2),
                          qhat_A_round=round(qA_r, 2), qhat_A_floor=round(qA_f, 2),
                          qhat_B=round(qB, 2), qhat_iso=round(qI, 2)))
    pred = pd.DataFrame(preds)
    res = res.merge(pred, on=["cell_id", "qp"])

    res["over_A_round"] = (res["qhat_A_round"] > res["qr_star"]).astype(int)
    res["over_A_floor"] = (res["qhat_A_floor"] > res["qr_star"]).astype(int)
    res["over_iso"] = (res["qhat_iso"] > res["qr_star"]).astype(int)

    res_csv = os.path.join(OUT_DIR, "p1_results.csv")
    res.sort_values(["context", "qp"]).to_csv(res_csv, index=False)

    print("\n=== P1 results (qr_star vs qhat) ===", flush=True)
    cols = ["cell_id", "context", "W", "qp", "qr_star", "above_upper",
            "qhat_A_round", "qhat_A_floor", "qhat_iso"]
    print(res[cols].to_string(index=False), flush=True)
    n = len(res)
    print(f"\nviolations: A-round={res['over_A_round'].sum()}/{n}, "
          f"A-floor={res['over_A_floor'].sum()}/{n}, "
          f"A-iso={res['over_iso'].sum()}/{n}", flush=True)
    print(f"wrote {res_csv}", flush=True)
    return res


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-procs", type=int, default=None)
    ap.add_argument("--skip-sim", action="store_true")
    args = ap.parse_args()
    main(n_procs=args.n_procs, skip_sim=args.skip_sim)
