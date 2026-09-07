# -*- coding: utf-8 -*-
"""Utilisation-vs-overprediction tradeoff of the margin (the #1 utilisation lever).

Sweeps the deployment margin Delta and reports, on the 7 D2 cities (existing
ground truth, no new simulation), how utilisation and overprediction move.

Two views:
  A) GLOBAL margin: one Delta for all widths (simple dial).
  B) SEGMENTED margin: per-bin Delta = Q_q of that bin's positive residuals
     (nominal - qr*), fit on D2 TRAIN cities, applied to all 7 cities.
"""
import os
import sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_REPO, "final_freeze", "src"))
from v2_quota import V2Quota

TRAIN = {"amsterdam", "melbourne", "newtaipei", "nyc", "taipei"}
W_BINS = [(1.6, 2.0), (2.0, 2.4), (2.4, 3.0)]
C = 24.374155890965095
P = -0.9454494315945483


def load_d2():
    d2 = pd.read_csv(os.path.join(_REPO, "data", "final",
                                  "full_reference_dataset.csv"))
    rows = []
    for r in d2.itertuples():
        g = dict(type=r.type, sinuosity=float(r.sinuosity),
                 max_turn_deg=0.0, cum_turn_deg=0.0)
        vbar = float(r.vbar) if not pd.isna(r.vbar) else None
        # W_eff per v2 (synthetic rectangle -> width_p10 = W)
        We = min(float(r.W), 3.0)
        # nominal on W_eff
        x = float(r.qp) / We if We > 0 else 0.0
        nom = C * We * (x ** P) if x > 0 else 0.0
        rows.append(dict(city=r.city, W=float(r.W), We=We, qp=float(r.qp),
                         base_pass=int(r.base_pass), geom=g, vbar=vbar,
                         ref=float(r.qr_star), nominal=nom))
    return pd.DataFrame(rows)


def apply(v, d):
    """v: V2Quota; d: DataFrame with W, qp, base_pass, geom, vbar, ref."""
    q = [v.quota(r.W, r.qp, r.base_pass, r.geom, r.vbar,
                 geometry_type=r.geom["type"], width_p10=r.W)
         for r in d.itertuples()]
    q = pd.Series(q, index=d.index, dtype=float)
    e = q - d.ref
    pos = d[d.ref > 0]
    upos = q[pos.index] / pos.ref
    return dict(n=int(q.notna().sum()),
                mae=float(np.mean(np.abs(e[q.notna()]))),
                overpred=float(np.mean((e[q.notna()] > 0))),
                util_med=float(np.median(upos.dropna())) if len(upos) else np.nan,
                util_mean=float(np.mean(upos.dropna())) if len(upos) else np.nan)


def main():
    d = load_d2()

    print("=== A) GLOBAL margin sweep (one Delta for all widths) ===")
    print(f"{'Delta':>6} {'n':>4} {'MAE':>6} {'overpred%':>10} "
          f"{'util_med%':>10} {'util_mean%':>11}")
    for delta in [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.1]:
        v = V2Quota([(1.6, float("inf"), delta)])
        s = apply(v, d)
        print(f"{delta:6.2f} {s['n']:4d} {s['mae']:6.2f} {s['overpred']*100:9.1f}% "
              f"{s['util_med']*100:9.1f}% {s['util_mean']*100:10.1f}%")

    print("\n=== B) SEGMENTED margin: per-bin Delta = Q_q of positive residuals "
          "(fit on TRAIN) ===")
    print(f"{'q':>5} {'deltas':>22} {'n':>4} {'MAE':>6} {'overpred%':>10} "
          f"{'util_med%':>10} {'util_mean%':>11}")
    # precompute per-cell residual per bin (on train)
    for q in [0.50, 0.60, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.00]:
        bins = []
        deltas = []
        for lo, hi in W_BINS:
            sub = d[(d.We >= lo) & (d.We < hi) & (d.city.isin(TRAIN))]
            res = (sub.nominal - sub.ref).clip(lower=0.0)
            delta = float(np.quantile(res, q)) if len(res) else 3.1068
            bins.append((lo, hi, delta))
            deltas.append(round(delta, 2))
        bins.append((3.0, float("inf"), bins[-1][2]))
        v = V2Quota(bins)
        s = apply(v, d)
        print(f"{q:5.2f} {str(deltas):>22} {s['n']:4d} {s['mae']:6.2f} "
              f"{s['overpred']*100:9.1f}% {s['util_med']*100:9.1f}% "
              f"{s['util_mean']*100:10.1f}%")


if __name__ == "__main__":
    main()
