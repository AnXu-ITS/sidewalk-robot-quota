# -*- coding: utf-8 -*-
"""
cross_engine.py
===============
Cross-engine consistency table (P2 item 2 / RQ4): put the quota frontiers of
the two dynamics engines side by side and argue that the quota ALGORITHM is
engine-robust in *structure* even though its *parameters* are engine-specific.

Engines:
  1. experiment/            Python social-force model (hard-core discs + repulsion)
  2. experiment_sumo/       SUMO 1.27.1 + JuPedSim CollisionFreeSpeedModel (0.48 m disc)

Both produce a reference quota dataset with identical schema:
    W, qp, vbar, base_pass, mean_density_base, mean_fr_base, qr_star, above_upper

This script:
  1. restricts to the COMMON (W x qp) grid so the comparison is apples-to-apples;
  2. prints the side-by-side frontier + the JuPedSim/social-force ratio;
  3. re-fits Model A (c, p), x_crit and W_min on EACH engine with the SAME
     procedure as experiment/scripts/fit_quota.py (log-linear on qr*>0);
  4. quantifies the structural agreement (Spearman rank correlation of the
     frontiers) vs the parameter gap (amplitude c and exponent p ratios);
  5. checks the deployment "floor" safety on each engine.

Outputs (experiment_sumo/outputs/cross_engine/):
  cross_engine_frontier.csv  (common-grid side-by-side)
  cross_engine_summary.csv   (fitted params + agreement metrics)
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", ".."))
SF_CSV = os.path.join(ROOT, "experiment", "outputs", "quota_labels",
                      "quota_dataset.csv")
JP_CSV = os.path.join(ROOT, "experiment_sumo", "outputs", "quota_labels",
                      "quota_dataset.csv")
OUT_DIR = os.path.join(ROOT, "experiment_sumo", "outputs", "cross_engine")


def load(csv):
    df = pd.read_csv(csv)
    df = df.rename(columns=str.strip)
    return df


def fit_model_a(df):
    """Replicate experiment/scripts/fit_quota.py: (c,p) log-linear, x_crit, W_min."""
    qp = df["qp"].to_numpy(float)
    W = df["W"].to_numpy(float)
    qr = df["qr_star"].to_numpy(float)
    base_pass = df["base_pass"].to_numpy(bool)
    x = qp / W
    y = qr / W

    x_crit = float(x[base_pass].max()) if base_pass.any() else 0.0
    W_min = float(df.loc[df["qr_star"] > 0, "W"].min()) \
        if (df["qr_star"] > 0).any() else 0.0

    mask = (x > 0) & (y > 0)
    if mask.sum() < 2:
        c, p = np.nan, np.nan
    else:
        p, logc = np.polyfit(np.log(x[mask]), np.log(y[mask]), 1)
        c = float(np.exp(logc))
    return c, float(p), x_crit, W_min


def spearman(a, b):
    return float(pd.Series(a).corr(pd.Series(b), method="spearman"))


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    sf = load(SF_CSV)
    jp = load(JP_CSV)

    # ---- common grid ----
    key = ["W", "qp"]
    sf_c = sf.drop_duplicates(key).set_index(key)["qr_star"]
    jp_c = jp.drop_duplicates(key).set_index(key)["qr_star"]
    common = sf_c.index.intersection(jp_c.index)
    sf_c = sf_c.loc[common]
    jp_c = jp_c.loc[common]
    Ws = sorted(set(i[0] for i in common))
    qps = sorted(set(i[1] for i in common))

    print("=== side-by-side q_r* frontier (common grid) ===")
    print("social-force (experiment/):")
    print("       " + " ".join(f"{int(q):>4}" for q in qps))
    for w in Ws:
        print(f"{w:5.1f}  " + " ".join(f"{sf_c.get((w, q), 0):4.0f}" for q in qps))
    print("\nJuPedSim (experiment_sumo/):")
    print("       " + " ".join(f"{int(q):>4}" for q in qps))
    for w in Ws:
        print(f"{w:5.1f}  " + " ".join(f"{jp_c.get((w, q), 0):4.0f}" for q in qps))
    print("\nratio JuPedSim / social-force ('.' = 0/0, 'INF' = /0):")
    print("       " + " ".join(f"{int(q):>5}" for q in qps))
    for w in Ws:
        row = []
        for q in qps:
            a, b = sf_c.get((w, q), 0.0), jp_c.get((w, q), 0.0)
            if a == 0 and b == 0:
                row.append("   .")
            elif a == 0:
                row.append(" INF")
            else:
                row.append(f"{b / a:4.1f}")
        print(f"{w:5.1f}  " + " ".join(row))

    # ---- re-fit on the common grid (same procedure, both engines) ----
    sf_fit = sf.set_index(key)
    jp_fit = jp.set_index(key)
    c_sf, p_sf, xc_sf, wmin_sf = fit_model_a(sf_fit.loc[common].reset_index())
    c_jp, p_jp, xc_jp, wmin_jp = fit_model_a(jp_fit.loc[common].reset_index())

    sf_v = sf_c.to_numpy(float)
    jp_v = jp_c.to_numpy(float)
    rho = spearman(sf_v, jp_v)
    ratio_amp = c_jp / c_sf if c_sf else np.nan

    # ---- deployment "floor" safety: floor(q_hat) <= q_r* ? ----
    def floor_safety(c, p, xc, wmin, wv, qpv, qrv):
        x = np.asarray(qpv) / np.asarray(wv)
        pred = np.zeros_like(x)
        m = (x < xc) & (np.asarray(wv) >= wmin)
        pred[m] = np.asarray(wv)[m] * c * (x[m] ** p)
        floor = np.floor(pred)
        n = len(qrv)
        over = int(np.sum(floor > np.asarray(qrv)))
        under = int(np.sum(np.asarray(qrv) - floor > 0))
        return n, over, under

    wv = [i[0] for i in common]
    qpv = [i[1] for i in common]
    qrv_sf = sf_c.to_numpy(float)
    qrv_jp = jp_c.to_numpy(float)
    n_sf, over_sf, under_sf = floor_safety(c_sf, p_sf, xc_sf, wmin_sf,
                                           wv, qpv, qrv_sf)
    n_jp, over_jp, under_jp = floor_safety(c_jp, p_jp, xc_jp, wmin_jp,
                                           wv, qpv, qrv_jp)

    print("\n=== re-fitted params on the COMMON grid (same procedure) ===")
    print(f"{'engine':14s} {'c':>8s} {'p':>8s} {'x_crit':>7s} {'W_min':>6s}")
    print(f"{'social-force':14s} {c_sf:8.3f} {p_sf:8.3f} {xc_sf:7.1f} {wmin_sf:6.1f}")
    print(f"{'JuPedSim':14s} {c_jp:8.3f} {p_jp:8.3f} {xc_jp:7.1f} {wmin_jp:6.1f}")
    print(f"\namplitude ratio c_JuPedSim/c_sf = {ratio_amp:.2f}x")
    print(f"exponent ratio p_JuPedSim/p_sf = {p_jp / p_sf:.2f}x")
    print(f"Spearman rank correlation of the two frontiers = {rho:.3f}")
    print(f"\nfloor(q_hat) safety on common grid:"
          f"\n  social-force: {n_sf} pts, {over_sf} over-alloc, {under_sf} under-alloc"
          f"\n  JuPedSim    : {n_jp} pts, {over_jp} over-alloc, {under_jp} under-alloc")

    # ---- save ----
    rows = []
    for w, q in common:
        rows.append(dict(W=w, qp=q, qr_star_sf=sf_c[(w, q)],
                         qr_star_jp=jp_c[(w, q)]))
    pd.DataFrame(rows).sort_values(["W", "qp"]).to_csv(
        os.path.join(OUT_DIR, "cross_engine_frontier.csv"), index=False)
    pd.DataFrame([dict(engine="social-force", c=c_sf, p=p_sf, x_crit=xc_sf,
                       W_min=wmin_sf, floor_over=over_sf, floor_under=under_sf),
                  dict(engine="JuPedSim", c=c_jp, p=p_jp, x_crit=xc_jp,
                       W_min=wmin_jp, floor_over=over_jp, floor_under=under_jp)]).to_csv(
        os.path.join(OUT_DIR, "cross_engine_summary.csv"), index=False)
    print(f"\nwrote {OUT_DIR}")


if __name__ == "__main__":
    main()
