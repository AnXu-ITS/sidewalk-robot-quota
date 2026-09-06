# -*- coding: utf-8 -*-
"""
Faithful reproduction of the frozen operational chain from the D2 reference table.
Rule extracted verbatim from guardrail_form_audit.py (frozen constants + apply_guards).
NO SUMO, no re-fit. Reads full_reference_dataset.csv only.
"""
import os
import sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))          # final_freeze/src -> repo root
DATA = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    _REPO, "data", "final", "full_reference_dataset.csv")
df = pd.read_csv(DATA)
W = df["W"].values.astype(float)
x = df["x"].values.astype(float)
qstar = df["qr_star"].values.astype(float)
base_pass = df["base_pass"].values.astype(int)
cities = df["city"].values

C = 24.374155890965095
P = -0.9454494315945483
W_MIN = 1.6
X_CRIT = 33.333333333333336
Q_MAX = 20.0
QW = [1.5, 1.6, 1.7, 1.8, 2.1, 2.4, 2.7, 3.0]
QQ = [0.0, 5.0, 6.0, 8.0, 10.0, 18.0, 20.0, 20.0]


def qlow(w):
    return np.interp(np.clip(w, QW[0], QW[-1]), QW, QQ)


def apply_guards(pred, w, xx):
    pred = np.asarray(pred, dtype=float)
    z = (w < W_MIN) | (xx >= X_CRIT)
    pred = np.where(z, 0.0, pred)
    pred = np.minimum(pred, qlow(w))
    pred = np.minimum(pred, Q_MAX)
    pred = np.maximum(0.0, pred)
    return np.floor(pred)


def over_metrics(qop):
    e = np.asarray(qop, dtype=float) - qstar
    over = e > 1e-9
    return dict(over_rate=float(over.mean()), over_max=float(e.max()),
                n=len(qop), n_over=int(over.sum()))


qnom = C * W * np.power(x, P)
resid_pos = np.maximum(0.0, qnom - qstar)
D80_FROZEN = float(np.quantile(resid_pos, 0.80))

city_list = sorted(set(cities))
margin = {held: float(np.quantile(resid_pos[cities != held], 0.80))
          for held in city_list}

# G0 nominal
g0 = apply_guards(qnom, W, x)
# G1 additive Q80 — single frozen pooled margin D80_FROZEN
g1_single = apply_guards(qnom - D80_FROZEN, W, x)
g1_single_bp = np.where(base_pass == 0, 0.0, g1_single)
# G1 additive Q80 — LOCO fold-calibrated margins (as in guarded_rule)
g1_fold = np.empty_like(qnom)
for held in city_list:
    te = cities == held
    g1_fold[te] = apply_guards(qnom[te] - margin[held], W[te], x[te])
g1_fold_bp = np.where(base_pass == 0, 0.0, g1_fold)

print(f"rows             = {len(df)}")
print(f"D80_FROZEN       = {D80_FROZEN:.6f}   (frozen Delta80 = 3.1068)")
print(f"fold margins     = { {c: round(margin[c],4) for c in city_list} }")
print()
rows = [
    ("G0 nominal (25.75 / 19)", g0),
    ("G1 +Q80 single D80 (6.75 / 16)", g1_single),
    ("G1 +Q80 fold margins (6.75 / 16)", g1_fold),
    ("G1 +base_pass single (2.75 / 7)", g1_single_bp),
    ("G1 +base_pass fold   (2.75 / 7)", g1_fold_bp),
]
for name, qop in rows:
    m = over_metrics(qop)
    print(f"{name:36s} over_rate={m['over_rate']:.6f}  over_max={m['over_max']:.1f}")

# checks
assert abs(D80_FROZEN - 3.1068) < 0.001, D80_FROZEN
assert abs(over_metrics(g0)["over_rate"] - 0.2575) < 0.0005
assert over_metrics(g0)["over_max"] == 19.0
# NOTE: the frozen 6.75% "+Q80" step uses LOCO fold-calibrated margins, NOT the
# single pooled D80 (which gives 6.5%). The pooled D80=3.1068 is the reported
# representative value.
assert abs(over_metrics(g1_fold)["over_rate"] - 0.0675) < 0.0005
assert over_metrics(g1_fold)["over_max"] == 16.0
assert abs(over_metrics(g1_single)["over_rate"] - 0.0650) < 0.0005  # diagnostic
assert abs(over_metrics(g1_fold_bp)["over_rate"] - 0.0275) < 0.0005
assert over_metrics(g1_fold_bp)["over_max"] == 7.0
print("\nALL FROZEN-CHAIN CHECKS PASSED: 25.75 -> 6.75 -> 2.75  and  19 -> 16 -> 7")
