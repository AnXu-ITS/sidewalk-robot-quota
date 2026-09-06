# -*- coding: utf-8 -*-
"""
fit_multicity.py
================
P1 wrap-up on top of the multi-city ground truth (outputs/p1_multicity/):

  1. Combined re-fit of the Model-A power-law amplitude (c, p) on
     synthetic + multi-city real cells, vs the current P1 model
     (quota_params_p1.json: x_crit=29.0, real C(W), synthetic c/p).
  2. Cross-city holdout: train (synthetic + singapore/london/tokyo),
     holdout amsterdam -> MAE / OAR / floor-rule violations.
  3. Type-B / Type-C external validation: does the algorithm over-predict
     q_r* on curved (B) and bottleneck (C) cells?  The curvature penalty
     W_c = W / sinuosity (arc/chord) is tested as the B-cell fix.

The floor rule q_hat_floor = floor(q_hat) is the deployment-safe output;
"violation" = floor(q_hat) > q_r* (over-allocation).

Usage:
  python fit_multicity.py [--real path/to/multicity_results.csv]
"""
import json
import math
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import PATHS, ROBOT_FLOWS_ALL  # noqa: E402
from fit_quota import fit_power_law, predict_quota  # noqa: E402

ROOT = PATHS["root"]
SYN_CSV = os.path.join(ROOT, "outputs", "quota_labels", "quota_dataset.csv")
MC_CSV = os.path.join(ROOT, "outputs", "p1_multicity", "multicity_results.csv")
P1_MODEL = os.path.join(ROOT, "models", "quota_algorithm", "quota_params_p1.json")
OUT_DIR = os.path.join(ROOT, "outputs", "p1_multicity")
Q_MAX = float(max(ROBOT_FLOWS_ALL))


def load_syn():
    df = pd.read_csv(SYN_CSV)
    df["source"] = "synthetic"
    df["city"] = "synthetic"
    return df


def load_real(path=MC_CSV):
    df = pd.read_csv(path)
    df["source"] = "real"
    return df


def fit_cp(df, base_model):
    """Re-fit ONLY the Model-A amplitude (c, p) on df, inheriting the capacity
    structure (x_crit / W_min / C(W) / q_max) from base_model.

    P1's x_crit=29.0 and C(W) are real Bendemeer capacity measurements; they
    must NOT be re-derived from the merged set, because degenerate cells (e.g.
    robot-impassable W < robot width -> 0-flow baselines that "pass") would
    inflate x_crit.  Only the power-law amplitude (c, p) is the free knob for
    the P1 wrap-up."""
    qp = df["qp"].to_numpy(float)
    W = df["W"].to_numpy(float)
    qr = df["qr_star"].to_numpy(float)
    c, p = fit_power_law(qp / W, qr / W)
    return dict(x_crit=base_model["x_crit"], W_min=base_model["W_min"],
                C_W=base_model["C_W"], q_max=base_model["q_max"], c=c, p=p)


def load_p1_model():
    with open(P1_MODEL, encoding="utf-8") as f:
        P = json.load(f)
    return dict(x_crit=P["x_crit"], W_min=P["W_min"],
                C_W=(np.asarray(P["C_W"]["W"], float),
                     np.asarray(P["C_W"]["C"], float)),
                q_max=P["q_max"], c=P["A"]["c"], p=P["A"]["p"])


def _pred(df, model, penalty):
    qp = df["qp"].to_numpy(float)
    W = df["W"].to_numpy(float)
    if penalty == "sinuosity" and "sinuosity" in df.columns:
        W = W / df["sinuosity"].to_numpy(float).clip(min=1.0)
    return predict_quota(qp, W, "A", (model["c"], model["p"]),
                         model["x_crit"], model["W_min"], model["C_W"],
                         model["q_max"])


def evaluate(df, model, penalty="none"):
    pred = _pred(df, model, penalty)
    qr = df["qr_star"].to_numpy(float)
    mae = float(np.mean(np.abs(pred - qr)))
    oar = float(np.mean(pred > qr))
    over_floor = int((np.floor(pred) > qr).sum())
    over_round = int(((np.round(pred * 2) / 2) > qr).sum())
    n = len(df)
    return dict(n=n, MAE=mae, OAR=oar,
                over_floor=over_floor, over_round=over_round)


def main(real_path=MC_CSV):
    syn = load_syn()
    real = load_real(real_path)
    comb = pd.concat([syn, real], ignore_index=True)

    p1 = load_p1_model()
    comb_fit = fit_cp(comb, p1)

    print("=" * 70)
    print("Model-A amplitude (c, p)  [x_crit/W_min/C(W) inherited from P1]")
    print(f"  P1 model (synthetic c/p): c={p1['c']:.4f} p={p1['p']:.4f} "
          f"(x_crit={p1['x_crit']:.1f})")
    print(f"  combined re-fit         : c={comb_fit['c']:.4f} p={comb_fit['p']:.4f}")
    print("=" * 70)

    # ---- 1. combined re-fit vs P1 model on the full real set ----------
    print("\n[1] On multi-city real cells (floor-rule over-allocation):")
    for name, model in [("P1 model (synthetic c/p)", p1),
                        ("combined re-fit", comb_fit)]:
        for penalty in ("none", "sinuosity"):
            m = evaluate(real, model, penalty)
            print(f"  {name:26s} penalty={penalty:10s} MAE={m['MAE']:.3f} "
                  f"OAR={m['OAR']:.3f} over_floor={m['over_floor']}/{m['n']} "
                  f"over_round={m['over_round']}/{m['n']}")

    # ---- 2. cross-city holdout -----------------------------------------
    train_cities = {"synthetic", "singapore", "london", "tokyo"}
    tr = comb[comb["city"].isin(train_cities)]
    te = real[real["city"] == "amsterdam"]
    print(f"\n[2] Cross-city holdout: train {len(tr)} (synthetic+SIN/LON/TYO), "
          f"test {len(te)} (amsterdam)")
    if len(te):
        tr_fit = fit_cp(tr, p1)
        m = evaluate(te, tr_fit, "none")
        ms = evaluate(te, tr_fit, "sinuosity")
        print(f"  train-fit c={tr_fit['c']:.4f} p={tr_fit['p']:.4f}")
        print(f"  holdout amsterdam: MAE={m['MAE']:.3f} OAR={m['OAR']:.3f} "
              f"over_floor={m['over_floor']}/{m['n']}")
        print(f"  + sinuosity pen. : MAE={ms['MAE']:.3f} OAR={ms['OAR']:.3f} "
              f"over_floor={ms['over_floor']}/{ms['n']}")

    # ---- 3. Type-B / Type-C external validation ------------------------
    print("\n[3] Type-B (curve) / Type-C (bottleneck) external validation "
          "(P1 model):")
    for typ in ("B", "C"):
        sub = real[real["type"] == typ]
        if not len(sub):
            print(f"  type {typ}: no cells"); continue
        mn = evaluate(sub, p1, "none")
        ms = evaluate(sub, p1, "sinuosity")
        sin_range = (sub["sinuosity"].min(), sub["sinuosity"].max()) \
            if "sinuosity" in sub.columns else (1.0, 1.0)
        print(f"  type {typ}: n={mn['n']} sinuosity "
              f"{sin_range[0]:.3f}-{sin_range[1]:.3f}")
        print(f"    plain W_eff    : MAE={mn['MAE']:.3f} OAR={mn['OAR']:.3f} "
              f"over_floor={mn['over_floor']}/{mn['n']}")
        print(f"    W_c=W/sinuosity: MAE={ms['MAE']:.3f} OAR={ms['OAR']:.3f} "
              f"over_floor={ms['over_floor']}/{ms['n']}")

    # ---- save combined model -------------------------------------------
    out = dict(x_crit=comb_fit["x_crit"], W_min=comb_fit["W_min"],
               C_W=dict(W=[float(w) for w in comb_fit["C_W"][0]],
                        C=[float(c) for c in comb_fit["C_W"][1]]),
               q_max=comb_fit["q_max"],
               A=dict(c=comb_fit["c"], p=comb_fit["p"]))
    out_json = os.path.join(ROOT, "models", "quota_algorithm",
                            "quota_params_multicity.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"\nwrote {out_json}")
    return comb_fit


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", default=MC_CSV)
    args = ap.parse_args()
    main(args.real)
