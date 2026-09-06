# -*- coding: utf-8 -*-
"""
rescore_seedwise_full.py
========================
Per-seed (Pr(C_p=1) >= 0.95) re-scoring of the synthetic training grid AND the
held-out test grid, followed by a full re-fit / re-validation of the quota
algorithm under the per-seed ground truth, plus a per-seed re-evaluation of the
multi-city external validation set.

Everything is derived from the EXISTING sweep CSVs (no re-simulation):

  1. seedwise labels for the synthetic training grid (8W x 6q_p)
  2. seedwise labels for the held-out test grid   (5W x 7q_p)
  3. re-fit of Models A / B / A-iso with the exact fit_quota procedure
     (x_crit / W_min / C(W) / q_max re-calibrated on the seedwise labels)
  4. held-out scoring against the seedwise test truth
  5. closed-loop SVR under the per-seed pass rule:
     * old (mean-fit) deployed levels, re-scored per-seed  -> "before"
     * new (seedwise-fit) deployed levels, scored from the existing
       closed-loop / sweep CSVs where the exact level exists      -> "after"
       (cells whose new level was never simulated are listed, not guessed)
  6. multi-city (200 combos) re-evaluation on the per-seed labels with the
     P1 model and the new seedwise model (plain / sinuosity-penalized),
     including the Amsterdam cross-city holdout and Type-B / Type-C.

Outputs (all *seedwise* artifacts sit next to their mean-based counterparts):
  outputs/quota_labels/quota_dataset_seedwise.csv
  outputs/validation/test_truth_seedwise.csv
  models/quota_algorithm/quota_params_seedwise.json
  data/processed/fit_metrics_seedwise.csv
  data/processed/quota_predictions_seedwise.csv
  outputs/validation/test_metrics_seedwise.csv
  outputs/validation/svr_seedwise_table.csv
  outputs/validation/svr_seedwise_summary.csv
  outputs/p1_multicity/multicity_seedwise_eval.csv
"""
import json
import os
import re
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (CONSTRAINTS, PATHS, WIDTHS_TRAIN, PED_FLOWS_TRAIN,
                    WIDTHS_TEST, PED_FLOWS_TEST, ROBOT_FLOWS_ALL)  # noqa: E402
from simulator import evaluate_constraints  # noqa: E402
from fit_quota import (fit_power_law, fit_2d_power, isotonic_decreasing,
                       calibrate_x_crit, estimate_capacity,
                       predict_quota)  # noqa: E402

CONF = CONSTRAINTS["conf_level"]        # 0.95 -> >= 29/30 seeds
DELTA_V = CONSTRAINTS["delta_v"]
OUTMIN = CONSTRAINTS["outflow_ratio_min"]
OUTMAX = CONSTRAINTS["outflow_ratio_max"]
DFLOOR = CONSTRAINTS["density_floor"]
Q_MAX = float(max(ROBOT_FLOWS_ALL))
TOL = 1e-9


# ---------------------------------------------------------------------------
# per-seed scoring helpers
# ---------------------------------------------------------------------------
def sweep_pass_frac(sub, vbar):
    """Per-seed pass fraction of a (cell, qr) level: fraction of the 30 seeds
    that individually satisfy speed retention / flow stability / density."""
    n = len(sub)
    if n == 0 or vbar <= 0:
        return float("nan"), 0
    flags = [evaluate_constraints(m, vbar, DELTA_V, OUTMIN, OUTMAX, DFLOOR)
             for m in sub.to_dict("records")]
    npass = int(sum(f["pass"] for f in flags))
    return npass / n, npass


def baseline_pass_frac(sub):
    """Per-seed baseline pass: density + flow stability per seed (speed
    retention is vacuous at q_r = 0)."""
    n = len(sub)
    if n == 0:
        return float("nan"), 0
    ok = ((sub["mean_density"] <= DFLOOR)
          & (sub["flow_ratio"] >= OUTMIN)
          & (sub["flow_ratio"] <= OUTMAX)).to_numpy(bool)
    return float(ok.mean()), int(ok.sum())


def seedwise_labels(baseline_df, sweep_df, cells):
    """Derive q_r* under the per-seed rule for a (W, q_p) grid.

    A level passes only if >= CONF of its seeds individually satisfy all three
    pedestrian-first constraints; q_r* = max passing swept level.
    """
    recs = []
    for (W, qp) in cells:
        base = baseline_df[(baseline_df["W"] == W) & (baseline_df["qp"] == qp)]
        vbar = float(base["mean_speed"].mean()) if len(base) else 0.0
        bfrac, bn = baseline_pass_frac(base)
        base_pass = bool(bfrac >= CONF)
        qr_star = 0.0
        above_upper = False
        fracs = {}
        if base_pass:
            sub_all = sweep_df[(sweep_df["W"] == W) & (sweep_df["qp"] == qp)]
            for qr in sorted(sub_all["qr"].unique()):
                frac, _ = sweep_pass_frac(sub_all[sub_all["qr"] == qr], vbar)
                fracs[float(qr)] = frac
                if frac >= CONF:
                    qr_star = max(qr_star, float(qr))
            above_upper = bool(fracs) and all(f >= CONF for f in fracs.values())
        recs.append(dict(W=W, qp=qp, vbar=vbar, base_pass=base_pass,
                         base_pass_frac=bfrac, qr_star=qr_star,
                         above_upper=above_upper))
    return pd.DataFrame(recs)


# ---------------------------------------------------------------------------
# re-fit (exact fit_quota procedure, seedwise labels)
# ---------------------------------------------------------------------------
def refit(df):
    qp = df["qp"].to_numpy(float)
    W = df["W"].to_numpy(float)
    qr = df["qr_star"].to_numpy(float)
    base_pass = df["base_pass"].to_numpy(bool)
    x = qp / W
    y = qr / W

    x_crit = calibrate_x_crit(qp, W, base_pass)
    W_min = float(df.loc[df["qr_star"] > 0, "W"].min()) \
        if (df["qr_star"] > 0).any() else 0.0
    C_knots = estimate_capacity(df)
    c, p = fit_power_law(x, y)
    a, m, n = fit_2d_power(qp, W, qr)
    bounds, vals = isotonic_decreasing(x, y)

    models = {
        "A": (c, p), "B": (a, m, n), "A-iso": (bounds, vals),
    }
    rows = []
    for key, params in models.items():
        pred = predict_quota(qp, W, key, params, x_crit, W_min, C_knots,
                             Q_MAX)
        df[f"pred_{key}"] = pred
        err = pred - qr
        over = np.maximum(0.0, err)
        under = np.maximum(0.0, -err)
        rows.append(dict(model=key,
                         MAE=float(np.mean(np.abs(err))),
                         RMSE=float(np.sqrt(np.mean(err ** 2))),
                         mean_over=float(over.mean()),
                         max_over=float(over.max()),
                         mean_under=float(under.mean()),
                         OAR=float(np.mean(pred > qr))))
    fit_metrics = pd.DataFrame(rows)
    params_out = {
        "criterion": "per-seed (Pr(C_p=1) >= 0.95, >= 29/30 seeds)",
        "x_crit": x_crit, "W_min": W_min,
        "C_W": {"W": [float(w) for w in C_knots[0]],
                "C": [float(c_) for c_ in C_knots[1]]},
        "q_max": Q_MAX,
        "A": {"c": c, "p": p},
        "B": {"a": a, "m": m, "n": n},
        "A-iso": {"bounds": [[float(lo), float(hi)] for lo, hi in bounds],
                  "vals": [float(v) for v in vals]},
    }
    return df, fit_metrics, params_out, x_crit, W_min, C_knots


# ---------------------------------------------------------------------------
# multi-city helpers
# ---------------------------------------------------------------------------
def load_p1_model():
    with open(os.path.join(PATHS["models"], "quota_params_p1.json"),
              encoding="utf-8") as f:
        P = json.load(f)
    return dict(x_crit=P["x_crit"], W_min=P["W_min"],
                C_W=(np.asarray(P["C_W"]["W"], float),
                     np.asarray(P["C_W"]["C"], float)),
                q_max=P["q_max"], c=P["A"]["c"], p=P["A"]["p"])


def mc_evaluate(df, model, penalty="none"):
    qp = df["qp"].to_numpy(float)
    W = df["W"].to_numpy(float)
    if penalty == "sinuosity" and "sinuosity" in df.columns:
        W = W / df["sinuosity"].to_numpy(float).clip(min=1.0)
    pred = predict_quota(qp, W, "A", (model["c"], model["p"]),
                         model["x_crit"], model["W_min"], model["C_W"],
                         model["q_max"])
    qr = df["qr_star"].to_numpy(float)
    over_floor = int((np.floor(pred) > qr).sum())
    over_round = int(((np.round(pred * 2) / 2) > qr).sum())
    return dict(n=len(df), MAE=float(np.mean(np.abs(pred - qr))),
                OAR=float(np.mean(pred > qr)), over_floor=over_floor,
                over_round=over_round)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main():
    # ---- 1. seedwise labels: training + test grids --------------------------
    base_df = pd.read_csv(os.path.join(PATHS["baseline"], "baseline_results.csv"))
    sweep_df = pd.read_csv(os.path.join(PATHS["sweeps"], "sweep_results.csv"))
    tbase_df = pd.read_csv(os.path.join(PATHS["validation"], "test_baseline.csv"))
    tsweep_df = pd.read_csv(os.path.join(PATHS["validation"], "test_sweep.csv"))

    train_cells = [(W, qp) for W in WIDTHS_TRAIN for qp in PED_FLOWS_TRAIN]
    test_cells = [(W, qp) for W in WIDTHS_TEST for qp in PED_FLOWS_TEST]
    train_sw = seedwise_labels(base_df, sweep_df, train_cells)
    test_sw = seedwise_labels(tbase_df, tsweep_df, test_cells)

    mean_train = pd.read_csv(os.path.join(PATHS["quota_labels"],
                                          "quota_dataset.csv"))
    mean_test = pd.read_csv(os.path.join(PATHS["validation"], "test_truth.csv"))

    print("=" * 74)
    print("STEP 1/5  per-seed reference quota labels (training grid)")
    print("=" * 74)
    piv = train_sw.pivot(index="qp", columns="W", values="qr_star")
    print(piv.to_string())
    print(f"\nsum qr* : mean-based {mean_train['qr_star'].sum():.0f}  "
          f"->  per-seed {train_sw['qr_star'].sum():.0f}")
    print(f"nonzero : mean-based {(mean_train['qr_star']>0).sum()}  "
          f"->  per-seed {(train_sw['qr_star']>0).sum()}")
    print(f"base_pass per-seed fails: "
          f"{int((~train_sw['base_pass']).sum())} cell(s)")

    print("\n" + "=" * 74)
    print("STEP 2/5  per-seed reference quota labels (held-out test grid)")
    print("=" * 74)
    cmp = mean_test[["W", "qp", "qr_star"]].merge(
        test_sw[["W", "qp", "qr_star"]], on=["W", "qp"],
        suffixes=("_mean", "_seed"))
    cmp["delta"] = cmp["qr_star_seed"] - cmp["qr_star_mean"]
    print(cmp.to_string(index=False))
    print(f"\nsum qr* : mean-based {mean_test['qr_star'].sum():.0f}  "
          f"->  per-seed {test_sw['qr_star'].sum():.0f}")
    print(f"feasible (base_pass) : mean-based {(mean_test['base_pass']).sum()}  "
          f"->  per-seed {(test_sw['base_pass']).sum()}")

    # ---- 3. re-fit ----------------------------------------------------------
    print("\n" + "=" * 74)
    print("STEP 3/5  re-fit on per-seed labels (fit_quota procedure)")
    print("=" * 74)
    train_fit, fit_metrics, params_out, x_crit, W_min, C_knots = refit(
        train_sw.copy())
    print(fit_metrics.to_string(index=False))
    print(f"\nx_crit = {x_crit:.2f} ped/min/m   W_min = {W_min:.2f} m")
    print("C(W): W = " + ", ".join(f"{w:.2f}" for w in C_knots[0])
          + " ; C = " + ", ".join(f"{c:.1f}" for c in C_knots[1]))
    print(f"Model A: c={params_out['A']['c']:.4f} p={params_out['A']['p']:.4f}")
    print(f"Model B: a={params_out['B']['a']:.4f} m={params_out['B']['m']:.4f} "
          f"n={params_out['B']['n']:.4f}")

    train_sw.to_csv(os.path.join(PATHS["quota_labels"],
                                 "quota_dataset_seedwise.csv"), index=False)
    train_fit.to_csv(os.path.join(PATHS["processed"],
                                  "quota_predictions_seedwise.csv"),
                     index=False)
    fit_metrics.to_csv(os.path.join(PATHS["processed"],
                                    "fit_metrics_seedwise.csv"), index=False)
    with open(os.path.join(PATHS["models"], "quota_params_seedwise.json"),
              "w", encoding="utf-8") as f:
        json.dump(params_out, f, indent=2)

    # ---- 4. held-out validation ---------------------------------------------
    print("\n" + "=" * 74)
    print("STEP 4/5  held-out validation vs per-seed test truth")
    print("=" * 74)
    qp_t = test_sw["qp"].to_numpy(float)
    W_t = test_sw["W"].to_numpy(float)
    qr_t = test_sw["qr_star"].to_numpy(float)
    test_rows = []
    for key, params in [("A", (params_out["A"]["c"], params_out["A"]["p"])),
                        ("B", (params_out["B"]["a"], params_out["B"]["m"],
                               params_out["B"]["n"])),
                        ("A-iso", (params_out["A-iso"]["bounds"],
                                   params_out["A-iso"]["vals"]))]:
        pred = predict_quota(qp_t, W_t, key, params, x_crit, W_min, C_knots,
                             Q_MAX)
        test_sw[f"pred_{key}"] = pred
        err = pred - qr_t
        over = np.maximum(0.0, err)
        under = np.maximum(0.0, -err)
        test_rows.append(dict(model=key, MAE=float(np.mean(np.abs(err))),
                              RMSE=float(np.sqrt(np.mean(err ** 2))),
                              mean_over=float(over.mean()),
                              max_over=float(over.max()),
                              mean_under=float(under.mean()),
                              OAR=float(np.mean(pred > qr_t))))
    test_metrics = pd.DataFrame(test_rows)
    print(test_metrics.to_string(index=False))
    test_sw.to_csv(os.path.join(PATHS["validation"], "test_truth_seedwise.csv"),
                   index=False)
    test_metrics.to_csv(os.path.join(PATHS["validation"],
                                     "test_metrics_seedwise.csv"),
                        index=False)

    # ---- 5. closed-loop SVR under the per-seed rule -------------------------
    print("\n" + "=" * 74)
    print("STEP 5/5  closed-loop SVR under the per-seed pass rule")
    print("=" * 74)
    cl_round = pd.read_csv(os.path.join(PATHS["validation"], "closed_loop.csv"))
    cl_floor = pd.read_csv(os.path.join(PATHS["validation"],
                                        "closed_loop_A-floor.csv"))
    cl_iso = pd.read_csv(os.path.join(PATHS["validation"],
                                      "closed_loop_A-iso.csv"))
    cl_new_path = os.path.join(PATHS["validation"],
                               "closed_loop_seedwise_new.csv")
    cl_new = pd.read_csv(cl_new_path) if os.path.exists(cl_new_path) else None

    mean_params = json.load(open(os.path.join(PATHS["models"],
                                              "quota_params.json"),
                                 encoding="utf-8"))
    mean_x = mean_params["x_crit"]; mean_wmin = mean_params["W_min"]
    mean_C = (np.asarray(mean_params["C_W"]["W"], float),
              np.asarray(mean_params["C_W"]["C"], float))

    def level_rows(src_df, Wv, qpv, level):
        sub = src_df[(src_df["W"] == Wv) & (src_df["qp"] == qpv)]
        return sub[np.isclose(sub["qr"].to_numpy(float), level, atol=TOL)]

    variants = [
        # name, model source, deployed-level fn, preferred data, sweep fallback
        ("old A-round (mean-fit)", "old", lambda p: round(p * 2) / 2,
         cl_round, True),
        ("old A-floor (mean-fit)", "old", lambda p: np.floor(p),
         cl_floor, True),
        ("old A-iso   (mean-fit)", "old", lambda p: p, cl_iso, False),
        ("new A-round (seed-fit)", "new", lambda p: round(p * 2) / 2,
         cl_round, True),
        ("new A-floor (seed-fit)", "new", lambda p: np.floor(p),
         cl_floor, True),
        ("new A-iso   (seed-fit)", "new", lambda p: p, cl_iso, False),
    ]
    summary_rows = []
    table_rows = []
    for vname, vsrc, lvl, src_csv, sweep_fb in variants:
        if vsrc == "old":
            px, pwmin, pC = mean_x, mean_wmin, mean_C
            pA = (mean_params["A"]["c"], mean_params["A"]["p"])
            pB = None
            piso = (mean_params["A-iso"]["bounds"],
                    mean_params["A-iso"]["vals"])
        else:
            px, pwmin, pC = x_crit, W_min, C_knots
            pA = (params_out["A"]["c"], params_out["A"]["p"])
            pB = None
            piso = (params_out["A-iso"]["bounds"],
                    params_out["A-iso"]["vals"])
        key = "A" if "round" in vname or "floor" in vname else "A-iso"
        params = pA if key == "A" else piso
        pred_all = predict_quota(qp_t, W_t, key, params, px, pwmin, pC, Q_MAX)

        viol = unscored = scored = 0
        for i, (_, trow) in enumerate(test_sw.iterrows()):
            if not trow["base_pass"]:
                continue  # Case-1: pre-existing violation, algorithm zeros it
            Wv, qpv = trow["W"], trow["qp"]
            level = float(lvl(float(pred_all[i])))
            vbar = float(trow["vbar"])
            frac = None
            if level <= 0:
                frac = 1.0  # no robot: baseline passes per-seed by definition
            else:
                sub = level_rows(src_csv, Wv, qpv, level)
                if len(sub):
                    frac, _ = sweep_pass_frac(sub, vbar)
                elif vsrc == "new" and cl_new is not None:
                    sub2 = level_rows(cl_new, Wv, qpv, level)
                    if len(sub2):
                        frac, _ = sweep_pass_frac(sub2, vbar)
                if frac is None and sweep_fb and float(level) == np.floor(level):
                    sub2 = level_rows(tsweep_df, Wv, qpv, level)
                    if len(sub2):
                        frac, _ = sweep_pass_frac(sub2, vbar)
            if frac is None:
                unscored += 1
                table_rows.append(dict(variant=vname, W=Wv, qp=qpv,
                                       level=level, qr_star=trow["qr_star"],
                                       pass_frac=None, scored=False))
                continue
            scored += 1
            bad = frac < CONF
            viol += int(bad)
            table_rows.append(dict(variant=vname, W=Wv, qp=qpv, level=level,
                                   qr_star=trow["qr_star"], pass_frac=frac,
                                   violated=bad, scored=True))
        svr = viol / scored if scored else float("nan")
        summary_rows.append(dict(variant=vname, SVR=svr, n_viol=viol,
                                 n_scored=scored, n_unscored=unscored))
        print(f"{vname:26s} SVR={svr:.4f}  ({viol}/{scored} scored, "
              f"{unscored} unscored)")

    svr_table = pd.DataFrame(table_rows)
    svr_table.to_csv(os.path.join(PATHS["validation"], "svr_seedwise_table.csv"),
                     index=False)
    pd.DataFrame(summary_rows).to_csv(
        os.path.join(PATHS["validation"], "svr_seedwise_summary.csv"),
        index=False)

    # ---- 6. multi-city per-seed re-evaluation ------------------------------
    print("\n" + "=" * 74)
    print("Multi-city (200 combos) on per-seed labels")
    print("=" * 74)
    mc = pd.read_csv(os.path.join(PATHS["root"], "outputs", "p1_multicity",
                                  "multicity_results.csv"))
    rsw = pd.read_csv(os.path.join(PATHS["root"], "outputs", "p1_multicity",
                                   "rescore_seedwise.csv"))
    mc_base = pd.read_csv(os.path.join(PATHS["root"], "outputs",
                                       "p1_multicity",
                                       "multicity_baseline.csv"))

    def parse_tag(tag):
        m = re.match(r"^(.*)\|qp(\d+)$", str(tag))
        return (m.group(1), int(m.group(2))) if m else (None, None)

    rsw["cell_id"], rsw["qp_int"] = zip(*rsw["tag"].map(parse_tag))
    mc = mc.merge(rsw[["cell_id", "qp_int", "seedwise_qr_star"]],
                  left_on=["cell_id", "qp"], right_on=["cell_id", "qp_int"],
                  how="left")
    mc["qr_star"] = mc["seedwise_qr_star"].fillna(0.0)

    # per-seed baseline re-check on the real cells (Case-1 under per-seed)
    bfrac = {}
    for tag, g in mc_base.groupby("tag", sort=False):
        bfrac[tag] = baseline_pass_frac(g)[0]
    mc["tag"] = mc["cell_id"] + "|qp" + mc["qp"].astype(int).astype(str)
    mc["base_frac"] = mc["tag"].map(bfrac)
    mc.loc[mc["base_frac"].notna() & (mc["base_frac"] < CONF), "qr_star"] = 0.0

    p1 = load_p1_model()
    seed_model = dict(x_crit=x_crit, W_min=W_min, C_W=C_knots, q_max=Q_MAX,
                      c=params_out["A"]["c"], p=params_out["A"]["p"])

    # combined re-fit on seedwise labels (synthetic + real), P1 capacity
    syn_sw = train_sw.rename(columns={})[["W", "qp", "qr_star"]].copy()
    real_sw = mc[["W", "qp", "qr_star"]].copy()
    comb_sw = pd.concat([syn_sw, real_sw], ignore_index=True)
    comb_c, comb_p = fit_power_law(comb_sw["qp"].to_numpy(float) /
                                   comb_sw["W"].to_numpy(float),
                                   comb_sw["qr_star"].to_numpy(float) /
                                   comb_sw["W"].to_numpy(float))
    comb_model = dict(x_crit=p1["x_crit"], W_min=p1["W_min"], C_W=p1["C_W"],
                      q_max=p1["q_max"], c=comb_c, p=comb_p)
    print(f"combined re-fit (seedwise syn+real): c={comb_c:.4f} p={comb_p:.4f}")

    eval_rows = []
    subsets = [("all real", mc),
               ("amsterdam", mc[mc["city"] == "amsterdam"]),
               ("type B", mc[mc["type"] == "B"]),
               ("type C", mc[mc["type"] == "C"])]
    models = [("P1 model (mean-fit)", p1),
              ("seedwise-fit", seed_model),
              ("combined re-fit (seedwise)", comb_model)]
    for sname, sub in subsets:
        for mname, mdl in models:
            for pen in ("none", "sinuosity"):
                m = mc_evaluate(sub, mdl, pen)
                eval_rows.append(dict(subset=sname, model=mname, penalty=pen,
                                      **m))
                print(f"  {sname:10s} {mname:26s} pen={pen:9s} "
                      f"MAE={m['MAE']:.3f} OAR={m['OAR']:.3f} "
                      f"over_floor={m['over_floor']}/{m['n']} "
                      f"over_round={m['over_round']}/{m['n']}")
    pd.DataFrame(eval_rows).to_csv(
        os.path.join(PATHS["root"], "outputs", "p1_multicity",
                     "multicity_seedwise_eval.csv"),
        index=False)

    print("\nwrote all *seedwise* artifacts (params / metrics / labels / "
          "svr / multicity eval).")


if __name__ == "__main__":
    main()
