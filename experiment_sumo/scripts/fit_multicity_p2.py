# -*- coding: utf-8 -*-
"""P2 hardening: conservative sharp-corner guard + extra-wide q_max cap.

Evaluates the P1 model vs a guarded P2 model on the 200 multi-city combos,
reporting over-allocation and under-allocation before/after.

Guard rules (interim, documented as sparse-sample):
  * sharp corner: corrected max_turn_deg >= SHARP_DEG -> q_hat = 0 (discrete).
  * extra wide:  W > 3.0 -> q_max = QMAX_EXTRA (15) instead of 20.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fit_multicity import load_p1_model, load_real, _pred

SHARP_DEG = 20.0      # corrected max_turn lower bound (bend sweep collapses >= 30 deg)
CONC_RATIO = 0.6      # max_turn/cum_turn: ~1 = single sharp corner, <~0.5 = gradual curve
QMAX_EXTRA = 15.0


def predict_guarded(real, p1):
    base = np.floor(_pred(real, p1, "sinuosity"))
    qr = real["qr_star"].to_numpy(float)
    cells = {c["cell_id"]: c for c in json.load(
        open(r"sumo_jupedsim\data\cells.json", encoding="utf-8"))["cells"]}
    mt = real["cell_id"].map(lambda c: cells[c]["max_turn_deg"]).to_numpy(float)
    cum = real["cell_id"].map(lambda c: cells[c]["cum_turn_deg"]).to_numpy(float)
    W = real["W"].to_numpy(float)
    # single sharp-corner hazard: a concentrated corner (not a gradual curve)
    conc = np.divide(mt, cum, out=np.zeros_like(mt), where=cum > 1e-6)
    sharp = (mt >= SHARP_DEG) & (cum >= SHARP_DEG) & (conc >= CONC_RATIO)
    base = np.where(sharp, 0.0, base)
    # extra-wide q_max cap
    base = np.where(W > 3.0, np.minimum(base, QMAX_EXTRA), base)
    return base


def report(pred, real, label):
    qr = real["qr_star"].to_numpy(float)
    over = pred - qr
    under = qr - pred
    n = len(real)
    ov = (over > 0).sum()
    un = (under > 0).sum()
    print(f"{label}: MAE={np.abs(pred-qr).mean():.3f} "
          f"over_floor={ov}/{n} under_floor={un}/{n} "
          f"max_over={over.max():.0f} max_under={under.max():.0f}")
    return over, under


def main():
    real = load_real(r"experiment_sumo\outputs\p1_multicity\multicity_results.csv")
    p1 = load_p1_model()
    base = np.floor(_pred(real, p1, "sinuosity"))
    guarded = predict_guarded(real, p1)
    print("=== before (P1 + sinuosity) vs after (P2 guard) ===")
    report(base, real, "P1   ")
    over_g, under_g = report(guarded, real, "P2   ")
    print()
    # cells affected by the guard
    cells = {c["cell_id"]: c for c in json.load(
        open(r"sumo_jupedsim\data\cells.json", encoding="utf-8"))["cells"]}
    real["max_turn"] = real["cell_id"].map(lambda c: cells[c]["max_turn_deg"])
    changed = real[np.abs(guarded - base) > 0.5]
    print(f"=== combos changed by guard ({len(changed)}) ===")
    print(changed[["cell_id", "city", "type", "W", "qp", "qr_star", "max_turn",
                   "sinuosity"]].assign(
                       base_pred=base[changed.index].astype(int),
                       guarded_pred=guarded[changed.index].astype(int)
                   ).to_string(index=False))


if __name__ == "__main__":
    main()
