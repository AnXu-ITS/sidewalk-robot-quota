"""
closed_loop_safe.py
===================
Closed-loop Service Violation Rate for the safe-side deployment variants:
  * A-floor : Model A prediction floored to the nearest whole robot/min
              (conservative rounding -- a natural operational rule);
  * A-iso   : non-parametric isotonic model (monotone, safe-side).

Reuses the held-out test cells and their reference baselines; re-simulates each
feasible cell at the variant's allocated quota and checks the mean
pedestrian-service constraints.
"""

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import PATHS, CONSTRAINTS, N_SEEDS_VALIDATION, SIM
from simulator import evaluate_constraints
from run_batch import run_batch

L = SIM["L"]


def main(n_procs=None):
    truth = pd.read_csv(os.path.join(PATHS["validation"], "test_truth.csv"))

    variants = {
        "A-floor": ("pred_A", lambda q: np.floor(q)),
        "A-iso": ("pred_A-iso", lambda q: np.round(q * 2.0) / 2.0),
    }

    delta_v = CONSTRAINTS["delta_v"]
    outmin = CONSTRAINTS["outflow_ratio_min"]
    dfloor = CONSTRAINTS["density_floor"]

    summary = []
    for name, (col, round_fn) in variants.items():
        scen = []
        for _, row in truth.iterrows():
            if not row["base_pass"]:
                continue
            qhat = max(0.0, float(round_fn(float(row[col]))))
            for s in range(N_SEEDS_VALIDATION):
                scen.append((row["W"], L, row["qp"], qhat, s, None, None, None))
        csv = os.path.join(PATHS["validation"], f"closed_loop_{name}.csv")
        df = run_batch(scen, n_procs=n_procs, out_csv=csv, label=f"closed-loop {name}")

        rows = []
        for _, row in truth.iterrows():
            if not row["base_pass"]:
                continue
            Wv, qpv, vbar = row["W"], row["qp"], row["vbar"]
            qhat = max(0.0, float(round_fn(float(row[col]))))
            sub = df[(df["W"] == Wv) & (df["qp"] == qpv)]
            flags = [evaluate_constraints(m, vbar, delta_v, outmin, dfloor)
                     for m in sub.to_dict("records")]
            mean_Rv = float(np.mean([f["Rv"] for f in flags]))
            mean_fr = float(sub["flow_ratio"].mean())
            mean_rho = float(sub["mean_density"].mean())
            viol = not (mean_Rv >= (1.0 - delta_v) and mean_fr >= outmin
                        and mean_rho <= dfloor)
            rows.append(dict(W=Wv, qp=qpv, q_hat=qhat,
                             qr_star=row["qr_star"], violated=viol,
                             mean_Rv=mean_Rv))
        tab = pd.DataFrame(rows)
        svr = float(tab["violated"].mean()) if len(tab) else float("nan")
        summary.append(dict(model=name, SVR=svr,
                            n_viol=int(tab["violated"].sum()),
                            n_feasible=len(tab)))
        print(f"{name:10s} SVR = {svr:.4f} "
              f"({int(tab['violated'].sum())}/{len(tab)} feasible cells)")

    summ = pd.DataFrame(summary)
    summ.to_csv(os.path.join(PATHS["validation"], "svr_summary.csv"),
                index=False)
    return summ


if __name__ == "__main__":
    main()
