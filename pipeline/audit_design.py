# -*- coding: utf-8 -*-
"""
audit_design.py — Ground-Truth Design Audit, Part 1.
Q1/Q2/Q3: design-table analysis of the current 280 combos (x = q_p/W coverage,
confounding) + synthetic identifiability test comparing 2/3/4 q_p-level designs.
Q7: structural leakage (same-source cells, LOO-city feasibility).
"""
import json
import math
import random
from collections import Counter, defaultdict

import numpy as np

CELLS = r"C:\Users\xuan1\Desktop\UOL学习\配送机器人workbench\pipeline\cells\selected_cells.json"

# final model (per-seed refit) for the pseudo-ground-truth generator
C_TRUE, P_TRUE = 27.166, -0.9334
X_CRIT = 33.33        # capacity boundary (qp/W)
Q_MAX = 20.0          # scan ceiling
SIGMA = 1.5           # robot/min residual noise (historical training MAE ~1.3-1.5)
RNG = np.random.default_rng(42)


def main():
    data = json.load(open(CELLS, encoding="utf-8"))
    cells = data["cells"]
    combos = []
    for c in cells:
        for qp in c["q_p_peak"]:
            combos.append(dict(cell=c, qp=qp, x=qp / c["W_eff"], W=c["W_eff"]))
    print("=" * 80)
    print("Q1/Q2/Q3 — current 280-combo design table")
    print("=" * 80)
    xs = sorted(co["x"] for co in combos)
    qps = sorted(co["qp"] for co in combos)
    ws = sorted(co["W"] for co in combos)
    def pct(a, q):
        return a[min(len(a) - 1, int(q * (len(a) - 1)))]
    print(f"n combos: {len(combos)}")
    print(f"q_p: min={qps[0]:.1f} p10={pct(qps,.1):.1f} p25={pct(qps,.25):.1f} "
          f"med={pct(qps,.5):.1f} p75={pct(qps,.75):.1f} p90={pct(qps,.9):.1f} "
          f"max={qps[-1]:.1f} ped/min")
    print(f"W:   min={ws[0]:.2f} p10={pct(ws,.1):.2f} p25={pct(ws,.25):.2f} "
          f"med={pct(ws,.5):.2f} p75={pct(ws,.75):.2f} p90={pct(ws,.9):.2f} "
          f"max={ws[-1]:.2f} m")
    print(f"x=q_p/W: min={xs[0]:.2f} p10={pct(xs,.1):.2f} p25={pct(xs,.25):.2f} "
          f"med={pct(xs,.5):.2f} p75={pct(xs,.75):.2f} p90={pct(xs,.9):.2f} "
          f"max={xs[-1]:.2f} ped/min/m (log10 range "
          f"{math.log10(xs[-1]/xs[0]):.2f} decades)")
    # per-cell level ratio
    ratios = [c["q_p_peak"][1] / c["q_p_peak"][0] for c in cells
              if c["q_p_peak"][0] > 0]
    print(f"per-cell qp ratio hi/lo: min={min(ratios):.2f} med="
          f"{sorted(ratios)[len(ratios)//2]:.2f} max={max(ratios):.2f}")
    # x regime coverage vs x_crit
    lo = sum(1 for x in xs if x < 5)
    mid = sum(1 for x in xs if 5 <= x < 20)
    hi = sum(1 for x in xs if 20 <= x < X_CRIT)
    crit = sum(1 for x in xs if X_CRIT <= x < X_CRIT * 1.25)
    over = sum(1 for x in xs if x >= X_CRIT * 1.25)
    print(f"x regime counts (x_crit={X_CRIT}): <5:{lo} 5-20:{mid} "
          f"20-33:{hi} 33-41.7:{crit} >=41.7:{over}")
    # largest log-gap between consecutive x values
    lxs = [math.log10(x) for x in xs if x > 0]
    gaps = sorted((b - a for a, b in zip(lxs, lxs[1:])), reverse=True)
    print(f"largest log10 gaps in x: {[round(g,2) for g in gaps[:5]]}")
    # ---- Q3 confounding
    print("\n--- Q3 width-flow confounding ---")
    W = np.array(ws); Q = np.array(qps); X = np.array(xs)
    print(f"corr(W, qp) = {np.corrcoef(W, Q)[0,1]:+.3f}  "
          f"corr(W, x) = {np.corrcoef(W, X)[0,1]:+.3f}  "
          f"corr(qp, x) = {np.corrcoef(Q, X)[0,1]:+.3f}")
    bins = [(0, 1.6, "narrow<1.6"), (1.6, 2.4, "mid 1.6-2.4"),
            (2.4, 3.5, "wide 2.4-3.5"), (3.5, 99, "xwide>=3.5")]
    for lo_, hi_, name in bins:
        sub = [x for x, w in zip(xs, ws) if lo_ <= w < hi_]
        if sub:
            print(f"  {name:12s} n={len(sub):3d} x range "
                  f"[{min(sub):5.1f}, {max(sub):5.1f}] "
                  f"median={np.median(sub):5.1f}")
    # ---- Q7 structural leakage
    print("\n--- Q7 structural (same-source / LOO) ---")
    src = Counter(c["way_id"] for c in cells)
    multi = {k: v for k, v in src.items() if v > 1}
    print(f"cells per source feature: max={max(src.values())} "
          f"(sources with >1 cell: {len(multi)})")
    by_city = Counter(c["city"] for c in cells)
    print("cells per city:", dict(by_city))
    print("LOO-city feasibility: 5 train cities -> 5 folds "
          "(each train 80 cells / hold-out 20) + external Seattle/Taoyuan 40")
    tw = [c for c in cells if c["city"] in ("taipei", "newtaipei", "taoyuan")]
    print(f"same-source NLMA cells in train AND test: "
          f"{sum(1 for c in tw if c['split']=='train')} train, "
          f"{sum(1 for c in tw if c['split']=='test')} test "
          f"(shared survey methodology = soft leakage)")

    # ================= Q1 synthetic identifiability =================
    print("\n" + "=" * 80)
    print("Q1 — synthetic identifiability of p under 2/3/4-level designs")
    print("=" * 80)
    designs = {}
    for c in cells:
        qlo, qhi = c["q_p_peak"]
        designs.setdefault("D2", []).append((c["W_eff"], [qlo, qhi]))
        qmid = math.sqrt(qlo * qhi)
        designs.setdefault("D3", []).append((c["W_eff"], [qlo, qmid, qhi]))
        q1 = qlo * (qhi / qlo) ** (1 / 3)
        q2 = qlo * (qhi / qlo) ** (2 / 3)
        designs.setdefault("D4", []).append((c["W_eff"], [qlo, q1, q2, qhi]))

    def gen_and_fit(W, qps, n_trials=400):
        p_hats, n_used, n_cens = [], [], 0
        for _ in range(n_trials):
            rows = []
            for w, qlist in zip(W, qps):
                for q in qlist:
                    x = q / w
                    if x >= X_CRIT:
                        n_cens += 1
                        continue
                    mu = w * C_TRUE * x ** P_TRUE
                    if mu >= Q_MAX:      # above scan ceiling -> censored
                        n_cens += 1
                        continue
                    y = round(mu) + RNG.normal(0, SIGMA)
                    if y <= 0:
                        y = 0.5
                    rows.append((x, y / w))
            if len(rows) < 10:
                continue
            lx = np.log([r[0] for r in rows])
            ly = np.log([r[1] for r in rows])
            A = np.vstack([np.ones(len(lx)), lx]).T
            (lc, lp), *_ = np.linalg.lstsq(A, ly, rcond=None)
            p_hats.append(lp)
            n_used.append(len(rows))
        p_hats = np.array(p_hats)
        return dict(p_mean=float(p_hats.mean()), p_std=float(p_hats.std()),
                    p_bias=float(p_hats.mean() - P_TRUE),
                    ci95=(float(np.percentile(p_hats, 2.5)),
                          float(np.percentile(p_hats, 97.5))),
                    ci_width=float(np.percentile(p_hats, 97.5)
                                   - np.percentile(p_hats, 2.5)),
                    n_fit_pts=float(np.mean(n_used)),
                    n_censored=n_cens // n_trials)

    for dname in ("D2", "D3", "D4"):
        Ws = [w for w, _ in designs[dname]]
        qps = [q for _, q in designs[dname]]
        n_total = sum(len(q) for q in qps)
        r = gen_and_fit(Ws, qps)
        print(f"{dname}: combos={n_total}, usable~{r['n_fit_pts']:.0f}/trial, "
              f"censored~{r['n_censored']}/trial")
        print(f"   p_hat = {r['p_mean']:+.3f} (true {P_TRUE:+.3f}, "
              f"bias {r['p_bias']:+.3f}, std {r['p_std']:.3f})")
        print(f"   95% CI = [{r['ci95'][0]:+.3f}, {r['ci95'][1]:+.3f}] "
              f"width {r['ci_width']:.3f}")
    print("(D3/D4 add log-spaced levels between each cell's lo/hi; "
          "same 140 cells, +1/+2 sweep levels per cell)")


if __name__ == "__main__":
    main()
