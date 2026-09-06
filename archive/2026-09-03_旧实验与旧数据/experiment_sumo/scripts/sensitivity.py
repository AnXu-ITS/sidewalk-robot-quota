"""
sensitivity.py
==============
Two robustness experiments from the plan (sections 22-23):

  1. Threshold sensitivity: re-derive q_r* under speed-retention floors
     delta_v in {5%, 10%, 15%} using the EXISTING sweep data (no new runs)
     -> strict / normal / permissive quota surfaces.

  2. Reference-robot speed sensitivity: run the sweep at
     v_ref * {0.8, 1.0, 1.2} on a representative subset of cells and compare
     the resulting q_r* surfaces (only answer: is the quota rule stable?).
"""

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (SIM, CONSTRAINTS, PATHS, WIDTHS_TRAIN, PED_FLOWS_TRAIN,
                    ROBOT_FLOWS, ROBOT_FLOWS_ALL, N_SEEDS_SWEEP,
                    DELTA_V_LEVELS, ROBOT_SPEED_FACTORS, ROBOT)
from simulator import evaluate_constraints
from run_batch import run_batch
from ground_truth import case1_cells

L = SIM["L"]


def rederive_thresholds():
    base = pd.read_csv(os.path.join(PATHS["baseline"], "baseline_results.csv"))
    sweep = pd.read_csv(os.path.join(PATHS["sweeps"], "sweep_results.csv"))
    outmin = CONSTRAINTS["outflow_ratio_min"]
    outmax = CONSTRAINTS["outflow_ratio_max"]
    dfloor = CONSTRAINTS["density_floor"]
    conf = CONSTRAINTS["conf_level"]
    bad = case1_cells(base)

    def flow_ok(fr):
        return outmin <= fr <= outmax

    rows = []
    for delta_v in DELTA_V_LEVELS:
        for W in WIDTHS_TRAIN:
            for qp in PED_FLOWS_TRAIN:
                b = base[(base["W"] == W) & (base["qp"] == qp)]
                vbar = b["mean_speed"].mean() if len(b) else 0.0
                base_pass = (b["mean_density"].mean() <= dfloor and
                             flow_ok(b["flow_ratio"].mean())) if len(b) else False
                qr_star = 0.0
                if base_pass:
                    sub = sweep[(sweep["W"] == W) & (sweep["qp"] == qp)]
                    for qr in [q for q in ROBOT_FLOWS_ALL if q != 0]:
                        s2 = sub[sub["qr"] == qr]
                        if len(s2) == 0:
                            continue
                        mean_Rv = float(s2["mean_speed"].mean() / vbar) if vbar > 0 else 0.0
                        if (mean_Rv >= (1.0 - delta_v) and
                                flow_ok(s2["flow_ratio"].mean()) and
                                s2["mean_density"].mean() <= dfloor):
                            qr_star = qr
                rows.append(dict(delta_v=delta_v, W=W, qp=qp, qr_star=qr_star))
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(PATHS["sensitivity"], "threshold_sensitivity.csv"),
              index=False)

    print("=== Threshold sensitivity: q_r* by delta_v ===")
    for dv in DELTA_V_LEVELS:
        piv = df[df["delta_v"] == dv].pivot(index="qp", columns="W",
                                            values="qr_star")
        print(f"\n delta_v = {dv:.0%}")
        print(piv.to_string())
    return df


def robot_speed_sensitivity(n_procs=None):
    # representative subset spanning the (q_p, W) space
    cells = [(1.8, 20), (2.1, 30), (2.4, 40), (2.7, 30), (3.0, 40), (2.4, 20)]
    seeds = 20
    scen = []
    for W, qp in cells:
        for f in ROBOT_SPEED_FACTORS:
            vref = ROBOT["v_ref"] * f
            for qr in ROBOT_FLOWS:
                for s in range(seeds):
                    scen.append((W, L, qp, qr, s, vref, None, None))

    out_csv = os.path.join(PATHS["sensitivity"], "speed_sensitivity.csv")
    df = run_batch(scen, n_procs=n_procs, out_csv=out_csv,
                   label="speed sensitivity")

    delta_v = CONSTRAINTS["delta_v"]
    outmin = CONSTRAINTS["outflow_ratio_min"]
    outmax = CONSTRAINTS["outflow_ratio_max"]
    dfloor = CONSTRAINTS["density_floor"]
    conf = CONSTRAINTS["conf_level"]

    def flow_ok(fr):
        return outmin <= fr <= outmax

    rows = []
    for W, qp in cells:
        for f in ROBOT_SPEED_FACTORS:
            vref = ROBOT["v_ref"] * f
            b = df[(df["W"] == W) & (df["qp"] == qp) & (df["qr"] == 0.0)]
            vbar = b["mean_speed"].mean() if len(b) else 0.0
            qr_star = 0.0
            sub = df[(df["W"] == W) & (df["qp"] == qp)]
            for qr in [q for q in ROBOT_FLOWS if q != 0]:
                s2 = sub[sub["qr"] == qr]
                if len(s2) == 0:
                    continue
                mean_Rv = float(s2["mean_speed"].mean() / vbar) if vbar > 0 else 0.0
                if (mean_Rv >= (1.0 - delta_v) and
                        flow_ok(s2["flow_ratio"].mean()) and
                        s2["mean_density"].mean() <= dfloor):
                    qr_star = qr
            rows.append(dict(W=W, qp=qp, speed_factor=f, qr_star=qr_star))

    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(PATHS["sensitivity"], "speed_sensitivity_summary.csv"),
               index=False)

    print("\n=== Robot speed sensitivity: q_r* by speed factor ===")
    piv = res.pivot_table(index=["W", "qp"], columns="speed_factor",
                          values="qr_star")
    print(piv.to_string())
    # quantify stability: std of q_r* across speed factors per cell
    g = res.groupby(["W", "qp"])["qr_star"]
    print("\nq_r* spread across speed factors:")
    print(pd.DataFrame({"min": g.min(), "max": g.max(), "std": g.std()}).to_string())
    return res


if __name__ == "__main__":
    rederive_thresholds()
    robot_speed_sensitivity()
