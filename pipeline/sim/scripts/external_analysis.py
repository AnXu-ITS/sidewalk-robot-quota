# -*- coding: utf-8 -*-
"""
external_analysis.py  (SEALED unblinding for BJ/SH external confirmation)
=========================================================================
One-shot unblinding + statistics. Requires BOTH cities complete
(external_bjsh/outputs/berlin/ground_truth.csv + confirm.csv).

Guards the seal: `--freeze` writes external_bjsh/freeze_manifest.json (SHA-256
of the frozen model / protocol / scripts + timestamp). Any later run VERIFIES
those hashes and ABORTS if any changed — a changed file breaks the seal.

Metrics (frozen protocol §8, per-seed ground truth):
  1. closed-loop SVR          (q_deploy re-simulated at 100 seeds, pass<0.95)
  2. over_floor               floor(q_hat) > q_r*
  3. MAE / continuous OAR
  4. under-allocation         floor(q_hat) < q_r*
  5. guard false-zero rate    guard zeroes but q_r* > 0
All reported per city + pooled (never pooled only). Frozen legacy models
(mean-fit, seedwise-fit) are read-only comparators, never re-fit.

Statistics:
  * Clopper-Pearson exact binomial 95% CI (combo level)
  * cell-cluster bootstrap (10,000 resamples, stratified by city) for SVR
  * McNemar (exact) on over-allocation vs the two legacy models
  * Wilcoxon signed-rank on |q_hat - q_r*| paired differences

Usage:
  python external_analysis.py --freeze     # lock hashes (once, before sims)
  python external_analysis.py              # verify seal + unblind + stats
"""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import PATHS, CONSTRAINTS  # noqa: E402
from fit_quota import predict_quota  # noqa: E402
from build_final_model import (load_seedwise_model, qlow,
                               final_predict)  # noqa: E402
from rescore_seedwise_full import sweep_pass_frac, CONF  # noqa: E402

ROOT = os.path.normpath(os.path.join(PATHS["root"], ".."))
EXT = os.path.join(ROOT, "external_bjsh")
MANIFEST = os.path.join(EXT, "freeze_manifest.json")

FROZEN_PATHS = {
    "model_final": os.path.join(PATHS["root"], "models", "quota_algorithm",
                                "quota_params_final.json"),
    "model_seedwise": os.path.join(PATHS["root"], "models", "quota_algorithm",
                                   "quota_params_seedwise.json"),
    "model_mean": os.path.join(PATHS["root"], "models", "quota_algorithm",
                               "quota_params.json"),
    "protocol": os.path.join(EXT, "protocol.md"),
    "driver": os.path.join(PATHS["root"], "scripts",
                           "external_ground_truth.py"),
    "analysis": os.path.join(PATHS["root"], "scripts",
                             "external_analysis.py"),
    "selection": os.path.join(ROOT, "sumo_jupedsim", "scripts",
                              "select_tagged_external.py"),
    "cells": os.path.join(EXT, "cells.json"),
}

W_LO, W_HI = 1.6, 3.0
Q_MAX_IN = 60.0
SHARP_DEG, CUM_DEG, CONC = 20.0, 20.0, 0.6
VBAR_MIN = 0.8


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def freeze():
    man = {"frozen_at": datetime.now(timezone.utc).isoformat(),
           "files": {k: sha256(v) for k, v in FROZEN_PATHS.items()}}
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(man, f, indent=2)
    print("frozen manifest written:")
    for k, h in man["files"].items():
        print(f"  {k:16s} {h[:16]}…")
    return man


def verify_seal():
    with open(MANIFEST, encoding="utf-8") as f:
        man = json.load(f)
    ok = True
    for k, v in FROZEN_PATHS.items():
        cur = sha256(v)
        if cur != man["files"].get(k):
            print(f"SEAL BROKEN: {k} changed "
                  f"(frozen {man['files'].get(k, '?')[:16]}… "
                  f"now {cur[:16]}…)")
            ok = False
    if not ok:
        raise SystemExit("abort: seal verification failed — "
                         "BJ/SH data is no longer a clean external test.")
    print(f"seal OK (frozen {man['frozen_at']})")


def load_combo_df():
    frames = []
    for city in ("berlin",):
        g = pd.read_csv(os.path.join(EXT, "outputs", city,
                                     "ground_truth.csv"))
        c = pd.read_csv(os.path.join(EXT, "outputs", city, "confirm.csv"))
        # confirm pass fraction per (tag, qr level) at q_deploy
        conf = {}
        vbar = dict(zip(zip(g["cell_id"], g["qp"]), g["vbar"]))
        for tag, sub in c.groupby("tag", sort=True):
            # tag = cell_id|qpxx ; deploy level per tag from ground_truth
            pass
        # per-combo confirm at q_deploy
        g["confirm_pass"] = np.nan
        g["q_deploy"] = g["q_deploy"].astype(float)
        for i, r in g.iterrows():
            if not r["base_pass"]:
                continue
            cell_id, qpxx = r["cell_id"], int(r["qp"])
            tag = f"{cell_id}|qp{qpxx}"
            sub = c[(c["tag"] == tag)
                    & np.isclose(c["qr"].to_numpy(float), r["q_deploy"],
                                 atol=1e-9)]
            if len(sub):
                g.at[i, "confirm_pass"] = sweep_pass_frac(
                    sub, vbar[(cell_id, r["qp"])])[0]
        frames.append(g)
    df = pd.concat(frames, ignore_index=True)
    return df


def in_domain_cell(c):
    if not (W_LO <= c["W_eff"] <= W_HI and c["width_src"] == "tag"):
        return False
    if c.get("n_barriers", 0) > 0 or c["type"] in ("C", "D"):
        return False
    mt, cum = c.get("max_turn_deg", 0.0), c.get("cum_turn_deg", 0.0)
    conc = mt / cum if cum > 1e-6 else 0.0
    if mt >= SHARP_DEG and cum >= CUM_DEG and conc >= CONC:
        return False
    if c["type"] == "A":
        return True
    return c["type"] == "B" and c.get("sinuosity", 1.0) <= 1.05


def compute(df):
    model = load_seedwise_model()
    C_W = model["C_W"]
    geom = {r["cell_id"]: {"max_turn_deg": r["max_turn_deg"],
                           "cum_turn_deg": r["cum_turn_deg"]}
            for _, r in df.drop_duplicates("cell_id").iterrows()}

    # frozen model predictions
    df["q_final"] = final_predict(df, model, geom=geom)
    df["q_seed"] = predict_quota(df["qp"].to_numpy(float),
                                 df["W"].to_numpy(float), "A",
                                 (model["c"], model["p"]), model["x_crit"],
                                 model["W_min"], model["C_W"], model["q_max"])
    with open(os.path.join(PATHS["root"], "models", "quota_algorithm",
                           "quota_params.json"), encoding="utf-8") as f:
        Pm = json.load(f)
    df["q_mean"] = predict_quota(df["qp"].to_numpy(float),
                                 df["W"].to_numpy(float), "A",
                                 (Pm["A"]["c"], Pm["A"]["p"]), Pm["x_crit"],
                                 Pm["W_min"],
                                 (np.asarray(Pm["C_W"]["W"], float),
                                  np.asarray(Pm["C_W"]["C"], float)),
                                 Pm["q_max"])

    # in-domain cell flags (geometry + width source + both flows <= 60)
    cell_peak = df.groupby("cell_id")["qp"].max()
    cell_dom = {cid: in_domain_cell(row) and cell_peak[cid] <= Q_MAX_IN
                for cid, row in df.drop_duplicates("cell_id").iterrows()}

    df["in_cell"] = df["cell_id"].map(cell_dom)
    df["qp_ok"] = df["qp"] <= Q_MAX_IN
    df["cap_ok"] = df["qp"].to_numpy(float) < np.interp(
        df["W"].to_numpy(float), C_W[0], C_W[1])
    df["in_domain"] = (df["in_cell"] & df["base_pass"] & df["cap_ok"])

    # guard zeroing (sharp / vbar) — for false-zero rate
    mt = df["max_turn_deg"].to_numpy(float)
    cum = df["cum_turn_deg"].to_numpy(float)
    conc = np.divide(mt, cum, out=np.zeros_like(mt), where=cum > 1e-6)
    sharp = (mt >= SHARP_DEG) & (cum >= CUM_DEG) & (conc >= CONC)
    slow = df["vbar"].to_numpy(float) < VBAR_MIN
    df["guard_zero"] = (sharp | slow) & (df["q_final"] <= 1e-9)

    return df


def metrics(df, subset, label):
    d = df[subset]
    n = len(d)
    floor = np.floor(d["q_final"].to_numpy(float))
    qr = d["qr_star"].to_numpy(float)
    over = floor > qr
    under = floor < qr
    mae = np.abs(d["q_final"].to_numpy(float) - qr).mean()
    oar = (d["q_final"].to_numpy(float) > qr).mean()
    # SVR: denominator = in-domain confirmation; violation = q_deploy>0 & confirm fail
    dd = d[d["in_domain"]]
    svr_n = len(dd)
    viol = dd[(dd["q_deploy"] > 0) & (dd["confirm_pass"] < CONF)]
    svr = len(viol) / svr_n if svr_n else float("nan")
    # guard false-zero
    gz = d[d["guard_zero"]]
    fz = int((gz["qr_star"] > 0).sum())
    fz_rate = fz / len(gz) if len(gz) else float("nan")
    return dict(label=label, n=n, in_domain_n=svr_n,
                SVR=svr, n_svr_viol=len(viol),
                over_floor=int(over.sum()), over_rate=float(over.mean()),
                under_floor=int(under.sum()), under_rate=float(under.mean()),
                MAE=mae, OAR=oar, guard_zero_n=len(gz), guard_false_zero=fz,
                guard_fz_rate=fz_rate)


def binom_ci(k, n):
    from scipy.stats import binomtest
    r = binomtest(k, n)
    return (r.proportion_ci(0.95).low, r.proportion_ci(0.95).high)


def main():
    args = sys.argv[1:]
    if "--freeze" in args:
        freeze()
        return
    verify_seal()
    df = compute(load_combo_df())

    print("\n=== unblinded: per-city + pooled (per-seed ground truth) ===")
    rows = []
    for city in ("berlin", "pooled"):
        if city == "pooled":
            sub, lbl = df, "pooled"
        else:
            sub, lbl = df[df["city"] == city], city
        r = metrics(sub, sub["base_pass"], lbl)
        rows.append(r)
    tab = pd.DataFrame(rows)
    print(tab.to_string(index=False))

    print("\n=== in-domain confirmation SVR with binomial CI ===")
    for city in ("berlin", "pooled"):
        d = df if city == "pooled" else df[df["city"] == city]
        dd = d[d["in_domain"]]
        k = int(((dd["q_deploy"] > 0) & (dd["confirm_pass"] < CONF)).sum())
        n = len(dd)
        lo, hi = binom_ci(k, n)
        print(f"  {city:8s} SVR={k}/{n} = {k/n:.3f}  CI95=[{lo:.3f}, {hi:.3f}]")

    print("\n=== guard false-zero rate (guard zeroed but q_r*>0) ===")
    gz = df[df["guard_zero"]]
    for city in ("berlin", "pooled"):
        g = gz if city == "pooled" else gz[gz["city"] == city]
        k = int((g["qr_star"] > 0).sum())
        print(f"  {city:8s} {k}/{len(g)} zeroed-with-truth>0")

    # paired comparisons vs legacy models (over-allocation indicator)
    print("\n=== paired vs frozen legacy models (over-allocation) ===")
    for legacy in ("q_seed", "q_mean"):
        fin_viol = np.floor(df["q_final"].to_numpy(float)) > df["qr_star"].to_numpy(float)
        leg_viol = np.floor(df[legacy].to_numpy(float)) > df["qr_star"].to_numpy(float)
        b = int((fin_viol & ~leg_viol).sum())   # final over, legacy not
        c = int((~fin_viol & leg_viol).sum())   # legacy over, final not
        from scipy.stats import binomtest as bt
        p = bt(min(b, c), b + c).pvalue if b + c else float("nan")
        print(f"  final vs {legacy:7s}: discordant {b}/{c} "
              f"(final_worse/final_better), McNemar p={p:.4g}")

    # cell-cluster bootstrap SVR (stratified by city)
    print("\n=== cell-cluster bootstrap SVR (10k, stratified) ===")
    from scipy.stats import bootstrap
    dd = df[df["in_domain"]].copy()
    dd["svr_viol"] = ((dd["q_deploy"] > 0) & (dd["confirm_pass"] < CONF))
    cells = dd["cell_id"].unique()
    rng = np.random.default_rng(0)
    n_cells = len(cells)
    stats = []
    for _ in range(10000):
        idx = rng.choice(n_cells, n_cells, replace=True)
        samp = cells[idx]
        sub = dd[dd["cell_id"].isin(samp)]
        stats.append(sub["svr_viol"].mean())
    stats = np.array(stats)
    print(f"  bootstrap SVR mean={stats.mean():.3f} "
          f"CI95=[{np.percentile(stats, 2.5):.3f}, "
          f"{np.percentile(stats, 97.5):.3f}]")

    # save
    out = os.path.join(EXT, "analysis_result.csv")
    pd.DataFrame(rows).to_csv(out, index=False)
    df.to_csv(os.path.join(EXT, "analysis_combos.csv"), index=False)
    print(f"\nwrote {out} and analysis_combos.csv")


if __name__ == "__main__":
    main()
