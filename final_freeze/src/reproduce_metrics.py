# -*- coding: utf-8 -*-
"""
reproduce_metrics.py  (offline reproduction, NO SUMO)

Reproduces the FROZEN headline chain from the D2 reference table, reading the
frozen constants from final_quota_method_config.json (via OperationalQuota).

    overprediction %     25.75 -> 6.75 -> 2.75
    max overprediction   19    -> 16   -> 7

Variants (frozen guard stack = W_min, x_crit, Q_low(W), q_max, floor — this is
the stack that produced the frozen headline; the DEPLOYED runtime additionally
applies C(W)/sharp-corner/speed-floor/type-sinuosity guards, see
operational_quota.py):

    V1 nominal          guard( q_nom )
    V2 +Q80 (fold)      guard( q_nom - fold_margin_80 )   # LOCO fold-calibrated
    V3 +baseline guard  V2 with base_pass==0 => 0

NOTE: the single pooled Delta80 = 3.1068 gives 6.5% (not 6.75%); the frozen 6.75%
uses per-held-city fold margins. This script reproduces the fold-margin version.

Exits with status BLOCKED if the D2 table is absent; does NOT fabricate numbers.
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from operational_quota import OperationalQuota

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
_DEFAULT_INPUT = os.path.join(_REPO, "data", "final", "full_reference_dataset.csv")

FROZEN = {
    "overprediction_chain_pct": [25.75, 6.75, 2.75],
    "max_overprediction_chain": [19, 16, 7],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=_DEFAULT_INPUT,
                    help=f"final D2 reference table CSV (default: {_DEFAULT_INPUT})")
    args = ap.parse_args()

    if not os.path.exists(args.input):
        print("[BLOCKED] D2 reference table not found:", args.input)
        print("Expected in data/final/full_reference_dataset.csv (see README).")
        sys.exit(3)

    df = pd.read_csv(args.input)
    m = OperationalQuota()

    W = df["W"].astype(float).values
    qp = df["qp"].astype(float).values
    x = qp / W
    qr_star = df["qr_star"].astype(float).values
    bp = df["base_pass"].astype(int).values
    city = df["city"].values

    q_nom = m.c * W * np.power(x, m.p)

    # LOCO fold-calibrated Q80 margins (per held-out city, from training residuals)
    city_list = sorted(set(city))
    fold_margin = np.empty_like(q_nom)
    for c in city_list:
        tr = city != c
        fold_margin[city == c] = float(
            np.quantile(np.maximum(0.0, q_nom[tr] - qr_star[tr]), 0.80))

    def guards(pred):
        pred = np.where((W < m.W_min) | (x >= m.x_crit), 0.0, pred)
        pred = np.minimum(pred, np.interp(np.clip(W, m.QW[0], m.QW[-1]),
                                          m.QW, m.QQ))
        pred = np.minimum(pred, m.q_max)
        return np.floor(np.maximum(0.0, pred))

    v1 = guards(q_nom)
    v2 = guards(q_nom - fold_margin)
    v3 = np.where(bp == 0, 0.0, v2)

    def metrics(qop):
        e = qop - qr_star
        over = e > 1e-9
        return 100.0 * float(over.mean()), float(e.max())

    got_over, got_max = [], []
    for name, qop in (("v1_nominal", v1), ("v2_q80", v2), ("v3_guard", v3)):
        op, mo = metrics(qop)
        got_over.append(round(op, 2))
        got_max.append(int(mo))
        print(f"{name:12s} overprediction={op:.2f}%  max_over={mo:.0f}")

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
