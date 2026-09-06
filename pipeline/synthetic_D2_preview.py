# -*- coding: utf-8 -*-
"""
synthetic_D2_preview.py — predict the identifiability gain of the decoupled
experiment BEFORE the real scans finish.

Pseudo-ground-truth generator: qr* = W * c * x^p  (c=27.166, p=-0.9334),
rounded to integer, censored at q_max=20 and at x>=x_crit=33.33,
plus N(0, sigma=1.5) noise. Same protocol as audit_design.py.

D1 = the real 280-combo design (contextual qp levels).
D2 = D1 + the 120 decoupled combos (x in {18,24,30} on the 40 selected cells).

Reports per dataset:
  * p_hat mean/bias/std/95% CI width over 400 noise trials
  * LOCO-city fold stability: std of p_hat across 7 city folds (one trial each,
    using the union of other cities)
"""
import json
import math

import numpy as np

C_TRUE, P_TRUE = 27.166, -0.9334
X_CRIT, Q_MAX, SIGMA = 33.33, 20.0, 1.5
RNG = np.random.default_rng(2026)

CELLS = r"C:\Users\xuan1\Desktop\UOL学习\配送机器人workbench\pipeline\cells\selected_cells.json"
DEC = r"C:\Users\xuan1\Desktop\UOL学习\配送机器人workbench\pipeline\cells\decoupled_cells.json"


def design():
    d1 = []
    cells = json.load(open(CELLS, encoding="utf-8"))["cells"]
    for c in cells:
        for qp in c["q_p_peak"]:
            d1.append((c["city"], c["W_eff"], qp))
    d2 = list(d1)
    for c in json.load(open(DEC, encoding="utf-8"))["combos"]:
        d2.append((c["city"], c["W"], c["qp"]))
    return d1, d2


def synth_fit(rows):
    xs, ys = [], []
    for city, W, qp in rows:
        x = qp / W
        if x >= X_CRIT:
            continue
        mu = W * C_TRUE * x ** P_TRUE
        if mu >= Q_MAX:
            continue
        y = round(mu) + RNG.normal(0, SIGMA)
        if y <= 0:
            y = 0.5
        xs.append(math.log(x))
        ys.append(math.log(y / W))
    if len(xs) < 5:
        return None
    A = np.vstack([np.ones(len(xs)), xs]).T
    (lc, lp), *_ = np.linalg.lstsq(A, ys, rcond=None)
    return lp


def trial(ds):
    return [synth_fit(rows) for rows in ds]


def main():
    d1, d2 = design()
    print(f"D1 combos: {len(d1)}  D2 combos: {len(d2)} (+{len(d2)-len(d1)} decoupled)")
    p1, p2 = [], []
    for _ in range(400):
        r1, r2 = synth_fit(d1), synth_fit(d2)
        if r1 is not None:
            p1.append(r1)
        if r2 is not None:
            p2.append(r2)
    for tag, p in (("D1", p1), ("D2", p2)):
        p = np.array(p)
        lo, hi = np.percentile(p, 2.5), np.percentile(p, 97.5)
        print(f"{tag}: p_hat={p.mean():+.4f} (true {P_TRUE}) "
              f"std={p.std():.4f} bias={p.mean()-P_TRUE:+.4f} "
              f"CI95=[{lo:+.3f},{hi:+.3f}] width={hi-lo:.4f}")
    # LOCO-city fold stability of p (one noise trial, 7 folds each)
    cities = sorted({r[0] for r in d1})
    for tag, ds in (("D1", d1), ("D2", d2)):
        ps = []
        for held in cities:
            tr = [r for r in ds if r[0] != held]
            lp = synth_fit(tr)
            if lp is not None:
                ps.append(lp)
        ps = np.array(ps)
        print(f"{tag} LOCO fold p: mean={ps.mean():+.3f} "
              f"std_across_folds={ps.std():.3f} "
              f"range=[{ps.min():+.3f},{ps.max():+.3f}]")
    # also: x coverage of D2
    xs1 = [qp / W for _, W, qp in d1]
    xs2 = [qp / W for _, W, qp in d2]
    print(f"x coverage: D1 [{min(xs1):.1f},{max(xs1):.1f}] "
          f"(log-range {math.log10(max(xs1)/min(xs1)):.2f}) | "
          f"D2 [{min(xs2):.1f},{max(xs2):.1f}] "
          f"(log-range {math.log10(max(xs2)/min(xs2)):.2f})")


if __name__ == "__main__":
    main()
