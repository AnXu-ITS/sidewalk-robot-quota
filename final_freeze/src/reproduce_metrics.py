# -*- coding: utf-8 -*-
"""
reproduce_metrics.py  (offline reproduction, NO SUMO)

Loads the frozen config and the final D2 reference table, then reproduces the
three-variant operational outputs and the headline metrics:

    overprediction %     25.75 -> 6.75 -> 2.75
    max overprediction   19    -> 16   -> 7

Variants:
    V1 nominal           zero-guards + nominal + Q_low + q_max + floor
                         (NO margin, NO base_pass gate)
    V2 +Q80              V1 + additive margin (Delta_80) before Q_low/q_max
    V3 +baseline guard   V2 + base_pass==0 => 0 gate

Expected input CSV columns (final D2 table):
    city, W, qp, qr_star, base_pass   (optionally type, sinuosity, x)

Exits with status BLOCKED if the D2 table is absent; does NOT fabricate numbers.
"""
import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from operational_quota import OperationalQuota

FROZEN = {
    "overprediction_chain_pct": [25.75, 6.75, 2.75],
    "max_overprediction_chain": [19, 16, 7],
}


def variant_quota(m, r, margin=False, base_pass_gate=False):
    W = float(r["W"]); qp = float(r["qp"]); qr_star = float(r["qr_star"])
    bp = int(r.get("base_pass", 1))
    # Step 0 OOD is handled by the caller filtering; here we force in-domain eval
    # by calling the internal steps directly.
    if base_pass_gate and bp == 0:
        return 0.0
    if W < m.W_min:
        return 0.0
    x = qp / W
    if x >= m.x_crit:
        return 0.0
    if qp >= m._interp(W, m.CW, m.CC):
        return 0.0
    q = m.c * W * (x ** m.p)
    if margin:
        q = max(0.0, q - m.delta)
    q = min(q, m._interp(W, m.QW, m.QQ))
    q = min(q, m.q_max)
    return float(int(q))  # floor


def metrics(df, dep_col):
    over = df[dep_col] > df["qr_star"]
    over_pct = 100.0 * float(over.mean())
    max_over = float((df.loc[over, dep_col] - df.loc[over, "qr_star"]).max()) \
        if over.any() else 0.0
    return over_pct, max_over


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True,
                    help="final D2 reference table CSV (city,W,qp,qr_star,base_pass)")
    args = ap.parse_args()

    if not os.path.exists(args.input):
        print("[BLOCKED] D2 reference table not found:", args.input)
        print("Copy full_reference_dataset.csv from the analysis machine, then "
              "re-run with --input <path>.")
        sys.exit(3)

    df = pd.read_csv(args.input)
    m = OperationalQuota()

    df["v1_nominal"] = df.apply(lambda r: variant_quota(m, r, False, False), axis=1)
    df["v2_q80"] = df.apply(lambda r: variant_quota(m, r, True, False), axis=1)
    df["v3_guard"] = df.apply(lambda r: variant_quota(m, r, True, True), axis=1)

    got_over = []
    got_max = []
    for col in ("v1_nominal", "v2_q80", "v3_guard"):
        op, mo = metrics(df, col)
        got_over.append(round(op, 2))
        got_max.append(int(mo))
        print(f"{col:12s} overprediction={op:.2f}%  max_over={mo:.0f}")

    print("\nFROZEN  overprediction chain:", FROZEN["overprediction_chain_pct"])
    print("FROZEN  max overprediction chain:", FROZEN["max_overprediction_chain"])
    print("GOT     overprediction chain:", got_over)
    print("GOT     max overprediction chain:", got_max)

    ok = (got_over == FROZEN["overprediction_chain_pct"] and
          got_max == FROZEN["max_overprediction_chain"])
    print("\nREPRODUCTION:", "PASS" if ok else "MISMATCH")
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()
