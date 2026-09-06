# -*- coding: utf-8 -*-
"""
strict_loco.py — STRICT Leave-One-City-Out evaluation of the frozen rule.

Reproduces the two distinct held-out-evaluation scopes side by side, so the
paper can report them honestly:

  (A) POOLED fit  + fold margin : fit c,p on ALL 7 cities once, then calibrate a
      Q80 margin per held-out city (train residuals).  ->  25.75 -> 6.75 -> 2.75 %

  (B) STRICT LOCO (per-fold refit): for each held-out city, RE-FIT c,p on the
      other 6 cities, calibrate the Q80 margin on those 6, evaluate on the
      held-out city.  ->  26.25 -> 7.50 -> 3.50 %

(B) is the honest "independent held-out city" number: the final coefficients do
NOT see the held-out city. (A) uses the final all-7-city coefficients and is a
pooled diagnostic, not a strict LOCO.

Fit procedure (matches pipeline/fit_models.py model_A):
    subset  = qr_star > 0 AND above_upper == 0
    OLS     log(qr_star / W) = log(c) + p * log(x),  x = q_p / W

Frozen guard stack (same as reproduce_frozen_chain.py): W_min, x_crit, Q_low(W),
q_max, floor. NO SUMO, no new data.
"""
import os
import sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))          # final_freeze/src -> repo root
DATA = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    _REPO, "data", "final", "full_reference_dataset.csv")

C_FROZEN = 24.374155890965095
P_FROZEN = -0.9454494315945483
W_MIN = 1.6
X_CRIT = 33.333333333333336
Q_MAX = 20.0
QW = [1.5, 1.6, 1.7, 1.8, 2.1, 2.4, 2.7, 3.0]
QQ = [0.0, 5.0, 6.0, 8.0, 10.0, 18.0, 20.0, 20.0]


def qlow(w):
    return np.interp(np.clip(w, QW[0], QW[-1]), QW, QQ)


def guards(pred, w, xx):
    pred = np.asarray(pred, dtype=float)
    pred = np.where((w < W_MIN) | (xx >= X_CRIT), 0.0, pred)
    pred = np.minimum(pred, qlow(w))
    pred = np.minimum(pred, Q_MAX)
    return np.floor(np.maximum(0.0, pred))


def fit_model_A(idx):
    """OLS log(q/W) ~ log(x) on qr_star>0 & above_upper==0. Returns (c, p)."""
    m = (q[idx] > 0) & (above_upper[idx] == 0)
    A = np.column_stack([np.ones(m.sum()), np.log(x[idx][m])])
    b = np.log(q[idx][m] / W[idx][m])
    beta, _, _, _ = np.linalg.lstsq(A, b, rcond=None)
    return float(np.exp(beta[0])), float(beta[1])


def over_metrics(qop, qs):
    e = np.asarray(qop, dtype=float) - qs
    over = e > 1e-9
    return dict(over_rate=100.0 * float(over.mean()), over_max=float(e.max()),
                n=int(len(qop)), n_over=int(over.sum()))


df = pd.read_csv(DATA)
W = df["W"].astype(float).values
x = df["x"].astype(float).values
q = df["qr_star"].astype(float).values
bp = df["base_pass"].astype(int).values
above_upper = df["above_upper"].astype(int).values
city = df["city"].values
cities = sorted(set(city))
n = len(df)

# ---------- (A) pooled fit + fold margin (the frozen headline) ----------
cp, pp = fit_model_A(np.ones(n, dtype=bool))
qnom_pooled = cp * W * np.power(x, pp)
fold_margin_pooled = np.empty(n)
for c in cities:
    tr = city != c
    fold_margin_pooled[city == c] = float(
        np.quantile(np.maximum(0.0, qnom_pooled[tr] - q[tr]), 0.80))
A_g0 = guards(qnom_pooled, W, x)
A_g1 = guards(qnom_pooled - fold_margin_pooled, W, x)
A_g1b = np.where(bp == 0, 0.0, A_g1)

# ---------- (B) strict LOCO (per-fold refit) ----------
g0 = np.zeros(n); g1 = np.zeros(n)
for c in cities:
    tr = city != c
    te = city == c
    cH, pH = fit_model_A(tr)
    margin = float(np.quantile(np.maximum(0.0, cH * W[tr] * x[tr] ** pH - q[tr]), 0.80))
    pred_te = cH * W[te] * x[te] ** pH
    g0[te] = guards(pred_te, W[te], x[te])
    g1[te] = guards(pred_te - margin, W[te], x[te])
g1b = np.where(bp == 0, 0.0, g1)

print("=" * 70)
print(f"rows = {n}; cities = {cities}")
print(f"pooled fit (all 7 cities): c={cp:.6f} p={pp:.6f}  "
      f"(frozen {C_FROZEN:.6f} / {P_FROZEN:.6f})")
print("=" * 70)
print("(A) POOLED fit + fold margin   -> "
      f"{over_metrics(A_g0, q)['over_rate']:.2f} -> "
      f"{over_metrics(A_g1, q)['over_rate']:.2f} -> "
      f"{over_metrics(A_g1b, q)['over_rate']:.2f} %")
print("(B) STRICT LOCO (per-fold refit) -> "
      f"{over_metrics(g0, q)['over_rate']:.2f} -> "
      f"{over_metrics(g1, q)['over_rate']:.2f} -> "
      f"{over_metrics(g1b, q)['over_rate']:.2f} %")
print()
for name, qo in (("A_G0", A_g0), ("A_G1", A_g1), ("A_G1b", A_g1b),
                 ("B_G0", g0), ("B_G1", g1), ("B_G1b", g1b)):
    m = over_metrics(qo, q)
    print(f"{name:6s} over_rate={m['over_rate']:.2f}%  over_max={m['over_max']:.1f}")

# assertions: strict LOCO is the honest held-out number
assert abs(over_metrics(A_g1, q)["over_rate"] - 6.75) < 0.01
assert abs(over_metrics(A_g1b, q)["over_rate"] - 2.75) < 0.01
assert abs(over_metrics(g0, q)["over_rate"] - 26.25) < 0.01
assert abs(over_metrics(g1, q)["over_rate"] - 7.50) < 0.01
assert abs(over_metrics(g1b, q)["over_rate"] - 3.50) < 0.01
print("\nOK: pooled 25.75->6.75->2.75 and strict-LOCO 26.25->7.50->3.50 "
      "both reproduced.")
