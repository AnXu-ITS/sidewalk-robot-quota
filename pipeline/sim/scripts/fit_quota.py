"""
fit_quota.py
============
Fit the interpretable quota algorithms

    q_hat_r = f(q_p, W)

to the simulation-derived reference quota dataset.

  Model A (primary, width-normalized engineering curve):
      y = q_r* / W = c * (q_p / W)^p ,  p < 0
      ->  q_hat_r = W * c * (q_p/W)^p
      Monotone: d q_hat/d q_p <= 0 and d q_hat/d W >= 0.

  Model B (2-D monotonic surface, unconstrained exponents):
      q_hat_r = a * W^m * q_p^n ,  m > 0 , n < 0

  Model A-iso (non-parametric isotonic baseline, handles zero-quota cells):
      y = g(x), g monotone non-increasing (pool-adjacent-violators).

Over-capacity cells (pedestrian-only baseline already unacceptable) are
handled with a hard zero: if x = q_p/W >= x_crit then q_hat_r = 0.

Fits are performed on cells with q_r* > 0 (log-log requires positive labels);
zero-quota cells are used to calibrate x_crit and to score the models.
"""

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import PATHS, ROBOT_FLOWS_ALL  # noqa: E402


# ---------------------------------------------------------------------------
# isotonic regression (non-increasing), pool-adjacent-violators
# ---------------------------------------------------------------------------
def isotonic_decreasing(x, y):
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    order = np.argsort(x)
    xs = x[order]
    ys = y[order]
    # blocks of (sum, count, list_of_x)
    blocks = [(float(ys[i]), 1, [float(xs[i])]) for i in range(len(xs))]
    i = 0
    while i < len(blocks) - 1:
        s1, c1, bx1 = blocks[i]
        s2, c2, bx2 = blocks[i + 1]
        if s1 / c1 >= s2 / c2 - 1e-12:      # non-increasing: OK
            i += 1
        else:                                # violation -> merge
            blocks[i] = (s1 + s2, c1 + c2, bx1 + bx2)
            blocks.pop(i + 1)
            if i > 0:
                i -= 1
    bounds = []
    vals = []
    for s, c, bx in blocks:
        bounds.append((min(bx), max(bx)))
        vals.append(s / c)
    return bounds, vals


def predict_isotonic(xq, bounds, vals):
    out = np.empty_like(np.asarray(xq, float))
    for i, x in enumerate(np.asarray(xq, float)):
        v = vals[-1]
        for (lo, hi), val in zip(bounds, vals):
            if x <= hi:
                v = val
                break
        out[i] = v
    return out


# ---------------------------------------------------------------------------
# fitting
# ---------------------------------------------------------------------------
def fit_power_law(x, y):
    """log y = log c + p log x  ->  returns (c, p)."""
    mask = (x > 0) & (y > 0)
    lx = np.log(x[mask])
    ly = np.log(y[mask])
    if len(lx) < 2:
        return 1.0, -1.0
    p, logc = np.polyfit(lx, ly, 1)
    return float(np.exp(logc)), float(p)


def fit_2d_power(qp, W, qr):
    """log q_hat = log a + m log W + n log q_p."""
    mask = (qp > 0) & (W > 0) & (qr > 0)
    X = np.column_stack([np.log(W[mask]), np.log(qp[mask])])
    y = np.log(qr[mask])
    if len(y) < 3:
        return 1.0, 1.0, -1.0
    coef, *_ = np.linalg.lstsq(np.column_stack([np.ones(len(y)), X]), y,
                               rcond=None)
    loga, m, n = coef
    return float(np.exp(loga)), float(m), float(n)


def calibrate_x_crit(qp, W, base_pass):
    """Largest x = q_p/W whose pedestrian-only baseline is acceptable."""
    x = np.asarray(qp) / np.asarray(W)
    ok = x[np.asarray(base_pass, bool)]
    if len(ok) == 0:
        return 0.0
    return float(ok.max())


def _isotonic_increasing(vals):
    """Pool-adjacent-violators, non-decreasing."""
    vals = [float(v) for v in vals]
    blocks = [(v, 1) for v in vals]  # (sum, count)
    i = 0
    while i < len(blocks) - 1:
        s1, c1 = blocks[i]
        s2, c2 = blocks[i + 1]
        if s1 / c1 <= s2 / c2 + 1e-12:
            i += 1
        else:
            blocks[i] = (s1 + s2, c1 + c2)
            blocks.pop(i + 1)
            if i > 0:
                i -= 1
    return [s / c for s, c in blocks]


def estimate_capacity(df, margin=30.0):
    """W-dependent robot-admissible pedestrian-flow capacity C(W).

    For each training width, C(W) is the pedestrian flow above which the
    corridor can no longer admit ANY robot (q_r* == 0).  It is placed at the
    midpoint between the last operable and the first inoperable flow (a
    conservative safety margin) and is guaranteed non-decreasing in W.  Widths
    whose quota never reaches zero inside the swept flow range are censored to
    ``max_flow + margin`` (effectively no cutoff).  Returns (W_knots, C_knots).
    """
    flows = np.sort(df["qp"].to_numpy(float))
    max_qp = float(flows.max())
    knots_W, knots_C = [], []
    for W in np.sort(df["W"].unique()):
        sub = df[df["W"] == W].sort_values("qp")
        qp = sub["qp"].to_numpy(float)
        qr = sub["qr_star"].to_numpy(float)
        pos = qp[qr > 0]
        zeros = qp[qr == 0]
        if len(pos) == 0:
            C = float(qp[0]) if len(qp) else 0.0
        elif len(zeros) == 0:
            C = max_qp + margin
        else:
            C = 0.5 * (float(pos.max()) + float(zeros.min()))
        knots_W.append(float(W))
        knots_C.append(C)
    # enforce non-decreasing C(W) WITHOUT changing the knot count (PAV would
    # shrink the array and desynchronize it from knots_W); cumulative max keeps
    # length aligned and matches the recalibrate_p1 construction.
    knots_C = np.maximum.accumulate(np.asarray(knots_C, float))
    return np.array(knots_W), knots_C


def predict_quota(qp, W, model, params, x_crit, W_min=0.0, C_knots=None,
                  q_max=None):
    qp = np.asarray(qp, float)
    W = np.asarray(W, float)
    x = qp / W
    # W-dependent capacity cutoff: a corridor admits a robot only while
    # q_p < C(W) (the robot-admissible pedestrian capacity).  This subsumes the
    # global x_crit as the binding hard zero for narrow corridors, which saturate
    # at a *lower* unit-width flow than wide ones.  Without C_knots the model
    # falls back to the original x >= x_crit behaviour.
    if C_knots is not None:
        C_w = np.interp(W, C_knots[0], C_knots[1])
    else:
        C_w = np.full_like(W, np.inf)
    m = (x < x_crit) & (qp < C_w) & (W >= W_min)
    out = np.zeros_like(x)
    if model == "A":
        c, p = params
        out[m] = W[m] * c * (x[m] ** p)
    elif model == "B":
        a, mm, nn = params
        out[m] = a * (W[m] ** mm) * (qp[m] ** nn)
    elif model == "A-iso":
        out[m] = W[m] * predict_isotonic(x[m], *params)
    out = np.maximum(out, 0.0)
    if q_max is not None:
        # never recommend more than the verified sweep ceiling (safe-side cap on
        # the wide / light plateau)
        out = np.minimum(out, q_max)
    return out


def fit_and_save():
    quota_csv = os.path.join(PATHS["quota_labels"], "quota_dataset.csv")
    df = pd.read_csv(quota_csv)

    qp = df["qp"].to_numpy(float)
    W = df["W"].to_numpy(float)
    qr = df["qr_star"].to_numpy(float)
    base_pass = df["base_pass"].to_numpy(bool)

    x = qp / W
    y = qr / W
    x_crit = calibrate_x_crit(qp, W, base_pass)
    # minimum robot-operable width: smallest W with a non-zero reference quota
    W_min = float(df.loc[df["qr_star"] > 0, "W"].min()) if (df["qr_star"] > 0).any() else 0.0
    # W-dependent robot-admissible pedestrian-flow capacity (P0' structural fix)
    C_knots = estimate_capacity(df)
    q_max = float(max(ROBOT_FLOWS_ALL))

    c, p = fit_power_law(x, y)
    a, m, n = fit_2d_power(qp, W, qr)
    bounds, vals = isotonic_decreasing(x, y)

    models = {
        "A": dict(name="Model A (normalized power law)",
                  params=(c, p), x_crit=x_crit),
        "B": dict(name="Model B (2-D power surface)",
                  params=(a, m, n), x_crit=x_crit),
        "A-iso": dict(name="Model A-iso (isotonic)",
                      params=(bounds, vals), x_crit=x_crit),
    }

    # predictions and fit metrics
    rows = []
    for key, spec in models.items():
        pred = predict_quota(qp, W, key, spec["params"], spec["x_crit"],
                             W_min, C_knots, q_max)
        df[f"pred_{key}"] = pred
        err = pred - qr
        mae = float(np.mean(np.abs(err)))
        rmse = float(np.sqrt(np.mean(err ** 2)))
        over = np.maximum(0.0, err)
        under = np.maximum(0.0, -err)
        oar = float(np.mean(pred > qr))
        max_over = float(over.max())
        rows.append(dict(model=key, MAE=mae, RMSE=rmse,
                         mean_over=float(over.mean()),
                         max_over=max_over,
                         mean_under=float(under.mean()),
                         OAR=oar))
        print(f"{spec['name']:32s} MAE={mae:6.3f} RMSE={rmse:6.3f} "
              f"OAR={oar:5.3f} mean_over={over.mean():5.3f} "
              f"max_over={max_over:5.3f} mean_under={under.mean():5.3f}")

    print(f"\nx_crit (over-capacity zero threshold) = {x_crit:.2f} ped/min/m")
    print(f"W_min (minimum robot-operable width) = {W_min:.2f} m")
    print("C(W) robot-admissible capacity knots: W = "
          + ", ".join(f"{w:.2f}" for w in C_knots[0])
          + " ; C = " + ", ".join(f"{c:.1f}" for c in C_knots[1]))
    print(f"q_max (verified ceiling cap) = {q_max:.0f} robot/min")
    print(f"Model A: c={c:.4f}, p={p:.4f}")
    print(f"Model B: a={a:.4f}, m={m:.4f}, n={n:.4f}")

    # save
    df.to_csv(os.path.join(PATHS["processed"], "quota_predictions.csv"),
              index=False)
    metric_df = pd.DataFrame(rows)
    metric_df.to_csv(os.path.join(PATHS["processed"], "fit_metrics.csv"),
                     index=False)

    # save model parameters as JSON
    import json
    params_out = {
        "x_crit": x_crit,
        "W_min": W_min,
        "C_W": {"W": [float(w) for w in C_knots[0]],
                "C": [float(c) for c in C_knots[1]]},
        "q_max": q_max,
        "A": {"c": c, "p": p},
        "B": {"a": a, "m": m, "n": n},
        "A-iso": {"bounds": [[float(lo), float(hi)] for lo, hi in bounds],
                  "vals": [float(v) for v in vals]},
    }
    with open(os.path.join(PATHS["models"], "quota_params.json"), "w") as f:
        json.dump(params_out, f, indent=2)

    return df, metric_df, models


if __name__ == "__main__":
    fit_and_save()
