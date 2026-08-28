"""
validate.py
===========
Held-out validation of the quota algorithm on unseen Singapore sidewalk cells
(different effective widths) plus the closed-loop Service Violation Rate.

Steps
-----
  1. load the fitted model parameters;
  2. for each held-out cell (W, q_p): run baseline + robot-flow sweep to obtain
     the true q_r* (independent of the fit);
  3. predict q_hat_r and score MAE / RMSE / over-allocation / OAR / under;
  4. closed-loop: re-simulate each cell at the predicted q_hat_r and check
     whether the pedestrian service constraints still hold -> SVR.
"""

import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (SIM, CONSTRAINTS, PATHS, WIDTHS_TEST, PED_FLOWS_TEST,
                    ROBOT_FLOWS, N_SEEDS_VALIDATION)
from simulator import evaluate_constraints
from run_batch import run_batch
from fit_quota import predict_quota

L = SIM["L"]


def load_model():
    with open(os.path.join(PATHS["models"], "quota_params.json")) as f:
        P = json.load(f)
    x_crit = P["x_crit"]
    W_min = P.get("W_min", 0.0)
    A = (P["A"]["c"], P["A"]["p"])
    B = (P["B"]["a"], P["B"]["m"], P["B"]["n"])
    iso = (P["A-iso"]["bounds"], P["A-iso"]["vals"])
    return x_crit, W_min, A, B, iso


def derive_test_quota(baseline_df, sweep_df, cells):
    delta_v = CONSTRAINTS["delta_v"]
    conf = CONSTRAINTS["conf_level"]
    outmin = CONSTRAINTS["outflow_ratio_min"]
    dfloor = CONSTRAINTS["density_floor"]
    rec = []
    for W, qp in cells:
        base = baseline_df[(baseline_df["W"] == W) & (baseline_df["qp"] == qp)]
        vbar = base["mean_speed"].mean() if len(base) else 0.0
        base_pass = (base["mean_density"].mean() <= dfloor and
                     base["flow_ratio"].mean() >= 0.85) if len(base) else False
        qr_star = 0.0
        above = False
        if base_pass:
            sub_all = sweep_df[(sweep_df["W"] == W) & (sweep_df["qp"] == qp)]
            passes = {}
            for qr in [q for q in ROBOT_FLOWS if q != 0]:
                sub = sub_all[sub_all["qr"] == qr]
                if len(sub) == 0:
                    continue
                mean_Rv = float(sub["mean_speed"].mean() / vbar) if vbar > 0 else 0.0
                mean_fr = float(sub["flow_ratio"].mean())
                mean_rho = float(sub["mean_density"].mean())
                pass_mean = (mean_Rv >= (1.0 - delta_v) and
                             mean_fr >= outmin and mean_rho <= dfloor)
                passes[qr] = pass_mean
                if pass_mean:
                    qr_star = qr
            if passes and all(passes.values()):
                above = True
        rec.append(dict(W=W, qp=qp, vbar=vbar, base_pass=base_pass,
                        qr_star=qr_star, above_upper=above))
    return rec


def main(n_procs=None):
    x_crit, W_min, A, B, iso = load_model()

    cells = [(W, qp) for W in WIDTHS_TEST for qp in PED_FLOWS_TEST]

    # ---- baselines --------------------------------------------------------
    base_scen = [(W, L, qp, 0.0, s, None, None, None)
                 for W, qp in cells for s in range(N_SEEDS_VALIDATION)]
    base_csv = os.path.join(PATHS["validation"], "test_baseline.csv")
    base_df = run_batch(base_scen, n_procs=n_procs, out_csv=base_csv,
                        label="test baseline")

    # ---- sweep for true q_r* ----------------------------------------------
    sweep_scen = [(W, L, qp, qr, s, None, None, None)
                  for W, qp in cells
                  for qr in ROBOT_FLOWS if qr != 0
                  for s in range(N_SEEDS_VALIDATION)]
    sweep_csv = os.path.join(PATHS["validation"], "test_sweep.csv")
    sweep_df = run_batch(sweep_scen, n_procs=n_procs, out_csv=sweep_csv,
                         label="test sweep")

    recs = derive_test_quota(base_df, sweep_df, cells)
    truth = pd.DataFrame(recs)

    # ---- predictions + error metrics --------------------------------------
    qp = truth["qp"].to_numpy(float)
    W = truth["W"].to_numpy(float)
    qr_true = truth["qr_star"].to_numpy(float)

    results = {}
    for key, name, params in [("A", "Model A", A), ("B", "Model B", B),
                              ("A-iso", "Model A-iso", iso)]:
        pred = predict_quota(qp, W, key, params, x_crit, W_min)
        truth[f"pred_{key}"] = pred
        err = pred - qr_true
        over = np.maximum(0.0, err)
        under = np.maximum(0.0, -err)
        mae = float(np.mean(np.abs(err)))
        rmse = float(np.sqrt(np.mean(err ** 2)))
        oar = float(np.mean(pred > qr_true))
        results[key] = dict(model=name, MAE=mae, RMSE=rmse,
                            mean_over=float(over.mean()),
                            max_over=float(over.max()),
                            mean_under=float(under.mean()), OAR=oar)
        print(f"{name:24s} MAE={mae:6.3f} RMSE={rmse:6.3f} OAR={oar:5.3f} "
              f"mean_over={over.mean():5.3f} max_over={over.max():5.3f} "
              f"mean_under={under.mean():5.3f}")

    # ---- closed-loop SVR (Model A primary) ---------------------------------
    print("\n=== closed-loop Service Violation Rate (Model A) ===")
    svr_scen = []
    for i, row in truth.iterrows():
        qhat = round(float(row["pred_A"]) * 2.0) / 2.0
        qhat = max(0.0, qhat)
        for s in range(N_SEEDS_VALIDATION):
            svr_scen.append((row["W"], L, row["qp"], qhat, s,
                             None, None, None))
    svr_csv = os.path.join(PATHS["validation"], "closed_loop.csv")
    svr_df = run_batch(svr_scen, n_procs=n_procs, out_csv=svr_csv,
                       label="closed-loop")

    delta_v = CONSTRAINTS["delta_v"]
    outmin = CONSTRAINTS["outflow_ratio_min"]
    dfloor = CONSTRAINTS["density_floor"]
    rows = []
    for i, trow in truth.iterrows():
        if not trow["base_pass"]:
            # over-capacity cell (Case 1): the algorithm correctly allocates 0;
            # a pre-existing pedestrian-only violation is not an algorithm error.
            continue
        Wv, qpv = trow["W"], trow["qp"]
        vbar = trow["vbar"]
        sub = svr_df[(svr_df["W"] == Wv) & (svr_df["qp"] == qpv)]
        flags = [evaluate_constraints(m, vbar, delta_v, outmin, dfloor)
                 for m in sub.to_dict("records")]
        pf = float(np.mean([f["pass"] for f in flags]))
        mean_Rv = float(np.mean([f["Rv"] for f in flags]))
        mean_fr = float(sub["flow_ratio"].mean())
        mean_rho = float(sub["mean_density"].mean())
        viol = not (mean_Rv >= (1.0 - delta_v) and mean_fr >= outmin
                    and mean_rho <= dfloor)
        rows.append(dict(W=Wv, qp=qpv, q_hat=trow["pred_A"], qr_star=trow["qr_star"],
                         pass_frac=pf, violated=viol, mean_Rv=mean_Rv))
    svr_table = pd.DataFrame(rows)
    svr = float(svr_table["violated"].mean()) if len(svr_table) else float("nan")
    print(f"SVR (Model A, feasible cells) = {svr:.4f} "
          f"({int(svr_table['violated'].sum())}/{len(svr_table)} test cells "
          f"violate service constraints)")

    truth.to_csv(os.path.join(PATHS["validation"], "test_truth.csv"), index=False)
    svr_table.to_csv(os.path.join(PATHS["validation"], "svr_table.csv"),
                     index=False)
    pd.DataFrame([r for r in results.values()]).to_csv(
        os.path.join(PATHS["validation"], "test_metrics.csv"), index=False)

    return truth, svr_table, results


if __name__ == "__main__":
    main()
