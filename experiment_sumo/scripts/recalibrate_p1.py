# -*- coding: utf-8 -*-
"""
recalibrate_p1.py
=================
Recalibrate the capacity cutoff (x_crit + C(W)) from the P1 real-site data,
then re-validate the fitted algorithm on the P1 ground truth.

Data (30-seed capacity sweep p1_capacity.py + P1 anchor):
  * residential W=1.65 : q_r* > 0 up to qp=48  -> synthetic C=35 is conservative
                         (keep).
  * commercial  W=2.25 : qr=1 passes at 60, fails at 66 -> C_real = 63.0.
  * MRT-frontage W=2.60: qr=1 passes at 74, fails at 78 (P1) -> C_real = 76.0.

The synthetic C(W) was *observed* for W<=2.1 but *censored* for W>=2.4
(C=90 = max_qp + 30 margin, never observed).  We replace the censored region
with the measured values, keeping the observed narrow region.

x_crit is lowered from the synthetic 33.3 to 29.0: the measured unit-flow
transition is x~=28.0 (commercial 63/2.25) to 29.2 (MRT 76/2.6).  Within the
calibrated width range the W-dependent C(W) table is the binding constraint, so
x_crit only acts as a global safety floor for out-of-range extrapolation.

Curvature penalty: effective clear width W_c = W_eff / sinuosity (arc/chord).
Every Bendemeer cell is essentially straight (sinuosity <= 1.0024), so W_c ~=
W_eff here; this is the framework for curved/bottleneck (Type-B/C) cells later.

Outputs: models/quota_algorithm/quota_params_p1.json,
         outputs/p1_real_site/p1_recalibrated.csv
"""
import json
import math
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import PATHS  # noqa: E402
from validate import load_model  # noqa: E402
from fit_quota import predict_quota  # noqa: E402

ROOT = PATHS["root"]
MODEL_DIR = os.path.join(ROOT, "models", "quota_algorithm")
P1_OUT = os.path.join(ROOT, "outputs", "p1_real_site")
CELLS_JSON = os.path.join(ROOT, "..", "sumo_jupedsim", "data", "cells.json")

# synthetic OBSERVED knots (W <= 2.1; q_r* hit 0 inside the swept range)
SYN_OBSERVED_W = [1.5, 1.6, 1.7, 1.8, 2.1]
SYN_OBSERVED_C = [10.0, 35.0, 35.0, 45.0, 45.0]

# measured real capacity (30-seed sweep, see module docstring)
REAL_W = [2.25, 2.6]
REAL_C = [63.0, 76.0]

X_CRIT_NEW = 29.0   # real-data unit-flow safety floor (was 33.33)


def sinuosity(cell):
    cl = cell["centerline"]
    arc = sum(math.hypot(cl[i + 1][0] - cl[i][0], cl[i + 1][1] - cl[i][1])
              for i in range(len(cl) - 1))
    chord = math.hypot(cl[-1][0] - cl[0][0], cl[-1][1] - cl[0][1])
    return arc / max(chord, 1e-9)


def build_new_cw():
    Ws = SYN_OBSERVED_W + REAL_W + [3.0]
    Cs = SYN_OBSERVED_C + REAL_C + [REAL_C[-1]]  # flat conservative extension
    order = np.argsort(Ws)
    Ws = [float(Ws[i]) for i in order]
    Cs = [float(Cs[i]) for i in order]
    # isotonic (non-decreasing in W) — already sorted but enforced defensively
    Cs = list(np.maximum.accumulate(Cs))
    return Ws, Cs


def main():
    W_new, C_new = build_new_cw()
    print("=== new C(W) knots ===")
    print("W =", W_new)
    print("C =", C_new, f"(x_crit {X_CRIT_NEW})")

    x_crit_old, W_min, A, B, iso, _, q_max = load_model()

    P = dict(x_crit=X_CRIT_NEW, W_min=W_min,
             C_W=dict(W=W_new, C=C_new), q_max=q_max,
             A=dict(c=A[0], p=A[1]),
             B=dict(a=B[0], m=B[1], n=B[2]),
             **{"A-iso": dict(bounds=iso[0], vals=iso[1])})
    new_json = os.path.join(MODEL_DIR, "quota_params_p1.json")
    with open(new_json, "w", encoding="utf-8") as f:
        json.dump(P, f, indent=2)
    print(f"wrote {new_json}")

    # old C(W) for before/after comparison
    with open(os.path.join(MODEL_DIR, "quota_params.json"), encoding="utf-8") as f:
        P0 = json.load(f)
    cw_old = (np.asarray(P0["C_W"]["W"], float),
              np.asarray(P0["C_W"]["C"], float))
    cw_new = (np.asarray(W_new, float), np.asarray(C_new, float))

    res = pd.read_csv(os.path.join(P1_OUT, "p1_results.csv"))
    cells = {c["cell_id"]: c for c in json.load(open(CELLS_JSON, encoding="utf-8"))["cells"]}

    res["sinuosity"] = res["cell_id"].map(lambda cid: sinuosity(cells[cid]))
    res["W_c"] = res["W"] / res["sinuosity"]

    def pred(qp, W, model, params, x_crit, cw):
        return float(predict_quota([qp], [W], model, params, x_crit, W_min,
                                   cw, q_max)[0])

    rows = []
    for _, r in res.iterrows():
        row = dict(cell_id=r["cell_id"], context=r["context"],
                   qp=int(r["qp"]), W_c=round(r["W_c"], 3),
                   sinuosity=round(r["sinuosity"], 4),
                   qr_star=float(r["qr_star"]))
        for tag, key, params in [("A", "A", A), ("B", "B", B),
                                 ("A-iso", "A-iso", iso)]:
            row[f"qhat_{tag}_old"] = round(pred(r["qp"], r["W_c"], key, params,
                                                x_crit_old, cw_old), 2)
            row[f"qhat_{tag}_new"] = round(pred(r["qp"], r["W_c"], key, params,
                                                X_CRIT_NEW, cw_new), 2)
        rows.append(row)
    df = pd.DataFrame(rows)

    print("\n=== before/after violation counts (safe-side rules) ===")
    for tag, key in [("A", "A"), ("B", "B"), ("A-iso", "A-iso")]:
        for rule, fn in [("round", lambda v: np.round(v * 2) / 2),
                         ("floor", np.floor)]:
            over_old = int((fn(df[f"qhat_{tag}_old"]) > df["qr_star"]).sum())
            over_new = int((fn(df[f"qhat_{tag}_new"]) > df["qr_star"]).sum())
            print(f"  {tag:6s} {rule:5s}: old={over_old}/{len(df)}  "
                  f"new={over_new}/{len(df)}")

    out_csv = os.path.join(P1_OUT, "p1_recalibrated.csv")
    df.to_csv(out_csv, index=False)
    print(f"\nwrote {out_csv}")
    cols = ["cell_id", "context", "qp", "W_c", "qr_star",
            "qhat_A_old", "qhat_A_new", "qhat_B_new", "qhat_A-iso_new"]
    print(df[cols].to_string(index=False))
    return df


if __name__ == "__main__":
    main()
