# -*- coding: utf-8 -*-
"""
audit_archive.py — Ground-Truth Design Audit, Part 2 (evidence from the
archived P1b multicity run: 100 real OSM cells x 2 qp = 200 combos, 30 seeds,
same SUMO 1.27.1 + JuPedSim engine and the same mean-based combo criterion).

Q4: threshold resolution of the qr sweep ladder (0..20 robot/min).
Q5: seed / acceptance-rule stability (29/30 vs 28/30 vs 30/30; 15/20/25 subsamples).
Q6: geometry residual effect (similar W & qp, different qr*).
"""
import numpy as np
import pandas as pd

BASE = r"C:\Users\xuan1\Desktop\UOL学习\配送机器人workbench\archive\2026-09-03_旧实验与旧数据\旧仿真实验\experiment_sumo\outputs\p1_multicity"
DELTA_V = 0.10
OUTMIN, OUTMAX = 0.90, 1.20
DFLOOR = 1.20
LEVELS = [1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 18, 20]


def main():
    base = pd.read_csv(BASE + r"\multicity_baseline.csv")
    sweep = pd.read_csv(BASE + r"\multicity_sweep.csv")
    res = pd.read_csv(BASE + r"\multicity_results.csv")

    vbar = base.groupby("tag")["mean_speed"].mean()
    level_of = {v: i for i, v in enumerate(LEVELS)}

    # per-seed pass at each (tag, qr)
    s = sweep.merge(vbar.rename("vbar"), on="tag")
    s["Rv"] = s["mean_speed"] / s["vbar"]
    s["pass"] = ((s["Rv"] >= 1 - DELTA_V)
                 & (s["flow_ratio"] >= OUTMIN)
                 & (s["flow_ratio"] <= OUTMAX)
                 & (s["mean_density"] <= DFLOOR)).astype(int)
    g = s.groupby(["tag", "qr"]).agg(pass_frac=("pass", "mean"),
                                     mean_Rv=("Rv", "mean"),
                                     n=("pass", "count")).reset_index()

    # ---- Q4 threshold resolution ----
    print("=" * 80)
    print("Q4 — threshold resolution of the qr ladder (archived P1b, 200 combos)")
    print("=" * 80)
    rows = []
    for tag, sub in g.groupby("tag"):
        passed = sub[(sub["pass_frac"] > 0.5) & (sub["n"] >= 30)]
        qr_star = passed["qr"].max() if len(passed) else 0.0
        nxt = sub[sub["qr"] == (qr_star + 1)] if qr_star > 0 else None
        if len(passed):
            marg = passed[passed["qr"] == qr_star]["mean_Rv"].iloc[0] - (1 - DELTA_V)
        else:
            marg = np.nan
        nxt_level = LEVELS[level_of[qr_star] + 1] if qr_star in level_of \
            and level_of[qr_star] + 1 < len(LEVELS) else None
        rows.append(dict(tag=tag, qr_star=qr_star, margin_at_star=marg,
                         nxt_level=nxt_level))
    q4 = pd.DataFrame(rows)
    steps = {l: (LEVELS[i+1]-l) for i, l in enumerate(LEVELS[:-1])}
    print("scan ladder steps:", LEVELS, "-> step sizes:", list(steps.values()))
    in_levels = q4[q4["qr_star"].isin(LEVELS)]
    step_at_star = in_levels["qr_star"].map(lambda l: steps.get(l, 0))
    print(f"qr* values: min={q4.qr_star.min()} max={q4.qr_star.max()} "
          f"(combo count per qr*: {dict(q4.qr_star.value_counts().sort_index())})")
    print(f"quantization: qr* at ladder level -> next gap = "
          f"step_at_star.value_counts().sort_index().to_dict()")
    # how close is the first FAILING level to the pass boundary (near-tie)
    near = []
    for tag, sub in g.groupby("tag"):
        passed = sub[sub["pass_frac"] > 0.5]
        qr_star = passed["qr"].max() if len(passed) else 0.0
        fail = sub[(sub["qr"] > qr_star) & (sub["n"] >= 30)]
        if len(fail):
            f = fail.sort_values("qr").iloc[0]
            near.append(dict(tag=tag, qr_star=qr_star, fail_qr=f["qr"],
                             fail_Rv=f["mean_Rv"], fail_frac=f["pass_frac"]))
    near = pd.DataFrame(near)
    borderline = near[(near["fail_Rv"] >= 0.85) | (near["fail_frac"] >= 0.5)]
    print(f"combos whose boundary sits BETWEEN ladder levels "
          f"(first failing level passes mean_Rv>=0.85 or frac>=0.5): "
          f"{len(borderline)}/{len(near)}")
    print(f"  of those, fail_frac in [0.6,0.97) (true boundary inside the "
          f"step): {int(((borderline.fail_frac>=0.6)&(borderline.fail_frac<0.97)).sum())}")
    # local refinement cost estimate: 1 extra level x 30 seeds per borderline combo
    print(f"local-boundary-refinement cost estimate: {len(borderline)} combos "
          f"x 1 level x 30 seeds = {len(borderline)*30} scenarios "
          f"(vs full-sweep total {len(sweep)} scenarios for 200 combos)")

    # ---- Q5 seed / rule stability ----
    print("\n" + "=" * 80)
    print("Q5 — seed & acceptance-rule stability (same 200 combos)")
    print("=" * 80)
    res_map = dict(zip(res["cell_id"] + "|qp" + res["qp"].astype(int).astype(str),
                       res["qr_star"]))
    for rule in (1.0, 29/30, 28/30):
        changed = 0
        stars = {}
        for tag, sub in g.groupby("tag"):
            passed = sub[(sub["pass_frac"] >= rule - 1e-9) & (sub["n"] >= 30)]
            stars[tag] = passed["qr"].max() if len(passed) else 0.0
        # compare with mean-based qr* from the results file
        for t, v in stars.items():
            if t in res_map and v != res_map[t]:
                changed += 1
        print(f"rule {rule:>6.3f} (>= N/30 pass): combos differing from "
              f"mean-based qr*: {changed}/200")
    # seed subsampling stability
    rng = np.random.default_rng(7)
    tags = sorted(g["tag"].unique())
    stars_full = {}
    for tag, sub in g.groupby("tag"):
        passed = sub[sub["pass_frac"] > 0.5]
        stars_full[tag] = passed["qr"].max() if len(passed) else 0.0
    for k in (15, 20, 25):
        flips = 0
        for _ in range(50):
            for tag in tags:
                sub = sweep[sweep["tag"] == tag]
                idx = rng.choice(sub.index, size=k, replace=False)
                ss = sub.loc[idx]
                ss = ss.assign(vbar=vbar[tag])
                ss = ss.assign(Rv=ss["mean_speed"] / ss["vbar"])
                ss = ss.assign(pass_=((ss["Rv"] >= 1 - DELTA_V)
                                      & (ss["flow_ratio"] >= OUTMIN)
                                      & (ss["flow_ratio"] <= OUTMAX)
                                      & (ss["mean_density"] <= DFLOOR)).astype(int))
                byq = ss.groupby("qr")["pass_"].mean()
                passed = byq[byq > 0.5]
                st = passed.index.max() if len(passed) else 0.0
                if stars_full[tag] != st:
                    flips += 1
        print(f"subsample {k:2d} seeds (50 reps): qr* flips "
              f"{flips} / {50*len(tags)} = {flips/(50*len(tags)):.3%}")

    # ---- Q6 geometry residual ----
    print("\n" + "=" * 80)
    print("Q6 — geometry residual (similar W & qp, different qr*)")
    print("=" * 80)
    r = res.copy()
    r["x"] = r["qp"] / r["W"]
    pairs = []
    for i in range(len(r)):
        for j in range(i + 1, len(r)):
            a, b = r.iloc[i], r.iloc[j]
            if abs(a["W"] - b["W"]) <= 0.15 and abs(a["qp"] - b["qp"]) <= 3:
                dq = abs(a["qr_star"] - b["qr_star"])
                if dq >= 4:
                    pairs.append((a, b, dq))
    print(f"pairs with |dW|<=0.15, |dqp|<=3, |dqr*|>=4: {len(pairs)}")
    for a, b, dq in pairs[:12]:
        print(f"  {a['cell_id'][:28]:28s} W={a['W']:.2f} qp={a['qp']:.0f} "
              f"type={a['type']} sin={a['sinuosity']:.3f} qr*={a['qr_star']:.0f}")
        print(f"  {b['cell_id'][:28]:28s} W={b['W']:.2f} qp={b['qp']:.0f} "
              f"type={b['type']} sin={b['sinuosity']:.3f} qr*={b['qr_star']:.0f}")
    # residual vs type
    fit = r[r["qr_star"] > 0].copy()
    if len(fit) > 10:
        lx = np.log(fit["x"].clip(lower=1e-6))
        ly = np.log((fit["qr_star"] / fit["W"]).clip(lower=1e-6))
        A = np.vstack([np.ones(len(lx)), lx]).T
        (lc, lp), *_ = np.linalg.lstsq(A, ly, rcond=None)
        fit = fit.assign(resid=ly - (lc + lp * lx))
        print(f"pooled fit on archived qr*: c={math_exp(lc):.2f} p={lp:+.3f}")
        print("mean |resid| by type:",
              fit.groupby("type")["resid"].apply(lambda v: float(np.abs(v).mean())).to_dict())
        print("mean |resid| by city (top):",
              fit.groupby("city")["resid"].apply(lambda v: float(np.abs(v).mean())).sort_values(ascending=False).head(4).to_dict())


def math_exp(v):
    return float(np.exp(v))


if __name__ == "__main__":
    main()
