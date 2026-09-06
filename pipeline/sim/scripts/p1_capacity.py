# -*- coding: utf-8 -*-
"""
p1_capacity.py
==============
Locate the REAL pedestrian capacity C_real(W) on the Bendemeer cells: the
pedestrian flow above which the corridor stops admitting ANY robot
(q_r* transitions >0 -> 0).

Method: for each (cell, qp) run the pedestrian-only baseline (qr=0, 30 seeds)
and the minimal-robot state (qr=1, 30 seeds).  q_r* == 0 iff the baseline is
already over capacity (Case-1) OR the qr=1 state fails the pedestrian-first
constraints.  Sweeping qp ascending locates the transition; C_real(W) is placed
at the midpoint between the last operable and first inoperable flow.

Probes (ascending qp, anchored on the P1 run's known points):
  residential W=1.65 : known q_r*>0 at qp=20  -> probe [24,28,32,36]
  commercial  W=2.25 : known q_r*>0 at qp=56  -> probe [60,64,68,72]
  MRT-frontage W=2.60: known q_r*=0 at qp=78  -> probe [60,66,72]

Outputs: outputs/p1_real_site/p1_capacity.csv
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (PED, WALL, ROBOT, SIM, CONSTRAINTS, PATHS,
                    N_SEEDS_SWEEP)  # noqa: E402
from run_batch import run_batch  # noqa: E402

L = SIM["L"]
CELLS_JSON = os.path.join(PATHS["root"], "..", "sumo_jupedsim", "data", "cells.json")
OUT = os.path.join(PATHS["root"], "outputs", "p1_real_site")

PROBES = {
    "BND-253918225-0": [36, 40, 44, 48],   # residential W=1.65 (pass@20-36 known)
    "BND-873552517-2": [60, 66, 70, 74],   # commercial W=2.25 (pass@56 known)
    "BND-661246488-2": [60, 66, 70, 74],   # MRT-frontage W=2.60 (fail@78 known)
}

DFLOOR = CONSTRAINTS["density_floor"]
DELTA_V = CONSTRAINTS["delta_v"]
OUTMIN = CONSTRAINTS["outflow_ratio_min"]
OUTMAX = CONSTRAINTS["outflow_ratio_max"]


def load_cells():
    with open(CELLS_JSON, encoding="utf-8") as f:
        return {c["cell_id"]: c for c in json.load(f)["cells"]}


def flow_ok(fr):
    return OUTMIN <= fr <= OUTMAX


def state_fails(sub, vbar):
    """Mean-over-seeds pedestrian-first failure test for one (tag, qr) group."""
    if len(sub) == 0 or vbar <= 0:
        return True
    mean_Rv = float(sub["mean_speed"].mean() / vbar)
    fr = float(sub["flow_ratio"].mean())
    dens = float(sub["mean_density"].mean())
    return not (mean_Rv >= (1.0 - DELTA_V) and flow_ok(fr) and dens <= DFLOOR)


def main(n_procs=None):
    os.makedirs(OUT, exist_ok=True)
    cells = load_cells()

    # ---- Phase 1: baselines for every probe --------------------------
    base_scen = []
    for cid, qps in PROBES.items():
        c = cells[cid]
        cl = [list(p) for p in c["centerline"]]
        for qp in qps:
            for seed in range(N_SEEDS_SWEEP):
                base_scen.append((c["W_eff"], L, float(qp), 0.0, seed,
                                  None, None, None, cl, f"{cid}|qp{qp}"))
    print(f"=== capacity baselines: {len(base_scen)} scenarios ===", flush=True)
    base_df = run_batch(base_scen, n_procs=n_procs,
                        out_csv=os.path.join(OUT, "p1_capacity_baseline.csv"),
                        label="p1cap_base")

    # Case-1: baseline already over capacity -> q_r* = 0 (no qr=1 needed)
    case1 = set()
    vbar = {}
    for tag, g in base_df.groupby("tag", sort=True):
        vbar[tag] = float(g["mean_speed"].mean())
        if g["mean_density"].mean() > DFLOOR or \
                g["flow_ratio"].mean() < 0.85 or \
                g["flow_ratio"].mean() > OUTMAX:
            case1.add(tag)

    # ---- Phase 2: qr=1 for baseline-passing probes --------------------
    qr1_scen = []
    for cid, qps in PROBES.items():
        c = cells[cid]
        cl = [list(p) for p in c["centerline"]]
        for qp in qps:
            tag = f"{cid}|qp{qp}"
            if tag in case1:
                continue
            for seed in range(N_SEEDS_SWEEP):
                qr1_scen.append((c["W_eff"], L, float(qp), 1.0, seed,
                                 None, None, None, cl, tag))
    qr1_df = pd.DataFrame()
    if qr1_scen:
        print(f"=== capacity qr=1: {len(qr1_scen)} scenarios ===", flush=True)
        qr1_df = run_batch(qr1_scen, n_procs=n_procs,
                           out_csv=os.path.join(OUT, "p1_capacity_qr1.csv"),
                           label="p1cap_qr1")
    else:
        print("=== capacity qr=1: skipped (all Case-1) ===", flush=True)

    # ---- Phase 3: determine q_r*=0 per (cell, qp) ---------------------
    rows = []
    for cid, qps in PROBES.items():
        c = cells[cid]
        for qp in qps:
            tag = f"{cid}|qp{qp}"
            if tag in case1:
                qr_star = 0.0
                reason = "case1"
            else:
                sub = qr1_df[qr1_df["tag"] == tag]
                if len(sub) == 0:
                    qr_star = np.nan
                    reason = "no-qr1"
                elif state_fails(sub, vbar[tag]):
                    qr_star = 0.0
                    reason = "qr1-fail"
                else:
                    qr_star = 1.0  # admits >= 1 robot (operable)
                    reason = "qr1-pass"
            b = base_df[base_df["tag"] == tag]
            rows.append(dict(cell_id=cid, context=c["context"], W=c["W_eff"],
                             qp=qp, reason=reason, qr_star=qr_star,
                             dens_base=round(float(b["mean_density"].mean()), 3),
                             fr_base=round(float(b["flow_ratio"].mean()), 3),
                             Rv_qr1=round(float(qr1_df[qr1_df["tag"] == tag]
                                               ["mean_speed"].mean() / vbar[tag]), 3)
                             if (tag not in case1 and len(qr1_df) and
                                 len(qr1_df[qr1_df["tag"] == tag])) else np.nan))
    res = pd.DataFrame(rows)

    # ---- Phase 4: C_real(W) = midpoint(last operable, first inoperable)
    cap_rows = []
    for cid in PROBES:
        sub = res[res["cell_id"] == cid].sort_values("qp")
        pos = sub[sub["qr_star"] > 0]["qp"].to_numpy(float)
        zero = sub[sub["qr_star"] == 0]["qp"].to_numpy(float)
        W = cells[cid]["W_eff"]
        if len(zero) == 0:
            C = None  # not found within probe range (censored upper)
        elif len(pos) == 0:
            C = float(zero[0])  # first probe already inoperable (lower bound)
        else:
            C = 0.5 * (pos.max() + zero.min())
        cap_rows.append(dict(cell_id=cid, context=cells[cid]["context"], W=W,
                             C_real=C, last_operable=float(pos.max()) if len(pos) else np.nan,
                             first_inoperable=float(zero.min()) if len(zero) else np.nan))

    cap = pd.DataFrame(cap_rows)
    res_csv = os.path.join(OUT, "p1_capacity.csv")
    res.to_csv(res_csv, index=False)
    cap.to_csv(os.path.join(OUT, "p1_capacity_C.csv"), index=False)

    print("\n=== per-probe q_r* state ===", flush=True)
    print(res.to_string(index=False), flush=True)
    print("\n=== C_real(W) estimates ===", flush=True)
    print(cap.to_string(index=False), flush=True)
    return res, cap


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-procs", type=int, default=None)
    args = ap.parse_args()
    main(n_procs=args.n_procs)
