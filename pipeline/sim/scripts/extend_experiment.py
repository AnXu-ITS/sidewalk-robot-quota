"""
extend_experiment.py
====================
Incremental P0 pass that resolves the two ceiling artifacts of the base sweep:

  1. Ceiling saturation: the base robot-flow sweep tops out at 10 robot/min, so
     wide / light cells were reported as "at least 10".  This script runs the
     extended levels ROBOT_FLOWS_EXTENDED = [12, 15, 18, 20] for every cell that
     saturated at the base ceiling, then re-aggregates q_r* over the full flow
     list ROBOT_FLOWS_ALL.
  2. W_min cliff: the minimum robot-operable width was a hard zero at 1.8 m,
     which wrongly zeroed real 1.65 m sidewalks.  This script adds training
     widths NARROW_WIDTHS = [1.6, 1.7] (baseline + full base sweep) so the
     data-calibrated W_min in fit_quota.py lands at ~1.6 m instead of 1.8 m,
     removing the cliff while keeping the safe-side hard zero for W < W_min.

It then re-fits the quota algorithm, re-validates on the held-out widths
(extending the test sweep ceiling too) and re-runs the closed-loop SVR, plus
refreshes the threshold sensitivity, figures and report.

All new simulations APPEND to the existing output CSVs, so the (expensive) base
baseline + sweep are reused unchanged.

Usage:
    python scripts/extend_experiment.py [--n-procs N] [--skip-sim]
"""

import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (PATHS, SIM, CONSTRAINTS, WIDTHS_TRAIN, PED_FLOWS_TRAIN,
                    NARROW_WIDTHS, ROBOT_FLOWS, ROBOT_FLOWS_EXTENDED,
                    ROBOT_FLOWS_ALL, WIDTHS_TEST, PED_FLOWS_TEST,
                    N_SEEDS_SWEEP, N_SEEDS_VALIDATION)
from simulator import evaluate_constraints
from run_batch import run_batch
from ground_truth import case1_cells

L = SIM["L"]

BASE_FLOWS = [q for q in ROBOT_FLOWS if q != 0]          # [1..10]
ALL_FLOWS = [q for q in ROBOT_FLOWS_ALL if q != 0]        # [1..10, 12, 15, 18, 20]


# ---------------------------------------------------------------------------
# small helpers (mean-based pedestrian-service constraint, plan section 5.1)
# ---------------------------------------------------------------------------
def _flow_ok(fr):
    return CONSTRAINTS["outflow_ratio_min"] <= fr <= CONSTRAINTS["outflow_ratio_max"]


def _vbar(base):
    return base["mean_speed"].mean() if len(base) else 0.0


def _base_pass(base):
    if len(base) == 0:
        return False
    dfloor = CONSTRAINTS["density_floor"]
    return (base["mean_density"].mean() <= dfloor and
            _flow_ok(base["flow_ratio"].mean()))


def _pass_mean(sub, vbar, delta_v=None):
    if len(sub) == 0:
        return False
    delta_v = CONSTRAINTS["delta_v"] if delta_v is None else delta_v
    dfloor = CONSTRAINTS["density_floor"]
    mean_Rv = sub["mean_speed"].mean() / vbar if vbar > 0 else 0.0
    return (mean_Rv >= (1.0 - delta_v) and
            _flow_ok(sub["flow_ratio"].mean()) and
            sub["mean_density"].mean() <= dfloor)


def _sat_cells(base_df, sweep_df, cells):
    """Cells whose largest *tested* base flow passed (ceiling unresolved)."""
    out = []
    for W, qp in cells:
        b = base_df[(base_df["W"] == W) & (base_df["qp"] == qp)]
        if not _base_pass(b):
            continue
        vbar = _vbar(b)
        sub = sweep_df[(sweep_df["W"] == W) & (sweep_df["qp"] == qp)]
        tested = [q for q in BASE_FLOWS if len(sub[sub["qr"] == q]) > 0]
        if not tested:
            continue
        top = max(tested)
        if _pass_mean(sub[sub["qr"] == top], vbar):
            out.append((W, qp))
    return out


def _append_csv(df, csv_path):
    # dedup on the scenario key so the incremental pass is idempotent (safe to
    # re-run a stage after a partial failure)
    keys = ["W", "qp", "qr", "seed"]
    if os.path.exists(csv_path):
        old = pd.read_csv(csv_path)
        df = pd.concat([old, df], ignore_index=True)
        if all(k in df.columns for k in keys):
            df = df.drop_duplicates(subset=keys, keep="last")
            df = df.reset_index(drop=True)
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    df.to_csv(csv_path, index=False)
    return df


# ---------------------------------------------------------------------------
# Step 1: narrow widths (baseline + base sweep)
# ---------------------------------------------------------------------------
def add_narrow_widths(n_procs=None):
    base_csv = os.path.join(PATHS["baseline"], "baseline_results.csv")
    sweep_csv = os.path.join(PATHS["sweeps"], "sweep_results.csv")

    print(f"=== Step 1: narrow widths {NARROW_WIDTHS} (baseline + base sweep) ===")
    base_scen = [(W, L, qp, 0.0, s, None, None, None)
                 for W in NARROW_WIDTHS for qp in PED_FLOWS_TRAIN
                 for s in range(N_SEEDS_SWEEP)]
    base_new = run_batch(base_scen, n_procs=n_procs, label="narrow baseline")
    _append_csv(base_new, base_csv)

    bad = case1_cells(pd.read_csv(base_csv))
    good = [(W, qp) for W in NARROW_WIDTHS for qp in PED_FLOWS_TRAIN
            if (W, qp) not in bad]
    sweep_scen = [(W, L, qp, qr, s, None, None, None)
                  for W, qp in good for qr in BASE_FLOWS
                  for s in range(N_SEEDS_SWEEP)]
    if sweep_scen:
        sweep_new = run_batch(sweep_scen, n_procs=n_procs,
                              label="narrow robot sweep")
        _append_csv(sweep_new, sweep_csv)
    print(f"  narrow cells proceeding to sweep: {len(good)} / "
          f"{len(NARROW_WIDTHS) * len(PED_FLOWS_TRAIN)}")


# ---------------------------------------------------------------------------
# Step 2: ceiling resolution (extended flows for saturated cells)
# ---------------------------------------------------------------------------
def resolve_ceiling(base_csv, sweep_csv, cells, n_seeds, n_procs=None, label="train"):
    base_df = pd.read_csv(base_csv)
    sweep_df = pd.read_csv(sweep_csv)
    sat = _sat_cells(base_df, sweep_df, cells)

    # exclude cells already extended beyond the base ceiling
    to_extend = []
    for W, qp in sat:
        sub = sweep_df[(sweep_df["W"] == W) & (sweep_df["qp"] == qp)]
        top = max([q for q in ALL_FLOWS if len(sub[sub["qr"] == q]) > 0])
        if top <= BASE_FLOWS[-1]:
            to_extend.append((W, qp))

    print(f"=== Step 2: ceiling resolution [{label}] ({len(to_extend)} cells) ===")
    if not to_extend:
        return
    scen = [(W, L, qp, qr, s, None, None, None)
            for W, qp in to_extend for qr in ROBOT_FLOWS_EXTENDED
            for s in range(n_seeds)]
    df = run_batch(scen, n_procs=n_procs, label=f"{label} ceiling")
    _append_csv(df, sweep_csv)


# ---------------------------------------------------------------------------
# Step 3: re-aggregate the training reference quota dataset
# ---------------------------------------------------------------------------
def aggregate_training():
    print("=== Step 3: re-aggregate training quota dataset ===")
    base_df = pd.read_csv(os.path.join(PATHS["baseline"], "baseline_results.csv"))
    sweep_df = pd.read_csv(os.path.join(PATHS["sweeps"], "sweep_results.csv"))
    delta_v = CONSTRAINTS["delta_v"]
    outmin = CONSTRAINTS["outflow_ratio_min"]
    outmax = CONSTRAINTS["outflow_ratio_max"]
    dfloor = CONSTRAINTS["density_floor"]

    records = []
    detail_rows = []
    for W in WIDTHS_TRAIN:
        for qp in PED_FLOWS_TRAIN:
            b = base_df[(base_df["W"] == W) & (base_df["qp"] == qp)]
            vbar = _vbar(b)
            md = b["mean_density"].mean() if len(b) else 0.0
            mfr = b["flow_ratio"].mean() if len(b) else 0.0
            base_pass = _base_pass(b)
            qr_star = 0.0
            above_upper = False
            if base_pass:
                sub_all = sweep_df[(sweep_df["W"] == W) & (sweep_df["qp"] == qp)]
                tested = [q for q in ALL_FLOWS
                          if len(sub_all[sub_all["qr"] == q]) > 0]
                for qr in tested:
                    sub = sub_all[sub_all["qr"] == qr]
                    mean_Rv = float(sub["mean_speed"].mean() / vbar) if vbar > 0 else 0.0
                    mean_fr = float(sub["flow_ratio"].mean())
                    mean_rho = float(sub["mean_density"].mean())
                    pass_mean = _pass_mean(sub, vbar, delta_v)
                    flags = [evaluate_constraints(m, vbar, delta_v, outmin,
                                                  outmax, dfloor)
                             for m in sub.to_dict("records")]
                    pass_frac = float(np.mean([f["pass"] for f in flags]))
                    detail_rows.append(dict(W=W, qp=qp, qr=qr,
                                            pass_frac=pass_frac, mean_Rv=mean_Rv,
                                            mean_speed=sub["mean_speed"].mean(),
                                            mean_density=mean_rho,
                                            mean_flow_ratio=mean_fr))
                    if pass_mean:
                        qr_star = qr
                if tested:
                    top = max(tested)
                    if _pass_mean(sub_all[sub_all["qr"] == top], vbar, delta_v):
                        above_upper = True
            records.append(dict(W=W, qp=qp, vbar=vbar, base_pass=base_pass,
                                mean_density_base=md, mean_fr_base=mfr,
                                qr_star=qr_star, above_upper=above_upper))

    summary = pd.DataFrame(records)
    detail = pd.DataFrame(detail_rows)
    summary.to_csv(os.path.join(PATHS["quota_labels"], "quota_dataset.csv"),
                   index=False)
    detail.to_csv(os.path.join(PATHS["quota_labels"], "quota_detail.csv"),
                  index=False)

    print("\n=== Reference quota dataset q_r* (rows=qp, cols=W) ===")
    print(summary.pivot(index="qp", columns="W", values="qr_star").to_string())
    n_ceil = int(summary["above_upper"].sum())
    print(f"\n  cells at sweep ceiling (above_upper): {n_ceil}")
    return summary, detail


# ---------------------------------------------------------------------------
# Step 5: re-validate on held-out widths (extend test ceiling, score, SVR)
# ---------------------------------------------------------------------------
def revalidate_test(n_procs=None):
    print("=== Step 5: extend test ceiling + re-validate ===")
    base_csv = os.path.join(PATHS["validation"], "test_baseline.csv")
    sweep_csv = os.path.join(PATHS["validation"], "test_sweep.csv")
    cells = [(W, qp) for W in WIDTHS_TEST for qp in PED_FLOWS_TEST]

    resolve_ceiling(base_csv, sweep_csv, cells, N_SEEDS_VALIDATION,
                    n_procs=n_procs, label="test")

    import validate
    import fit_quota
    from closed_loop_safe import main as closed_loop_main

    base_df = pd.read_csv(base_csv)
    sweep_df = pd.read_csv(sweep_csv)

    truth = pd.DataFrame(validate.derive_test_quota(base_df, sweep_df, cells))
    x_crit, W_min, A, B, iso, C_knots, q_max = validate.load_model()

    qp = truth["qp"].to_numpy(float)
    W = truth["W"].to_numpy(float)
    qr_true = truth["qr_star"].to_numpy(float)

    results = {}
    for key, name, params in [("A", "Model A", A), ("B", "Model B", B),
                              ("A-iso", "Model A-iso", iso)]:
        pred = fit_quota.predict_quota(qp, W, key, params, x_crit, W_min,
                                       C_knots, q_max)
        truth[f"pred_{key}"] = pred
        err = pred - qr_true
        over = np.maximum(0.0, err)
        under = np.maximum(0.0, -err)
        results[key] = dict(model=name, MAE=float(np.mean(np.abs(err))),
                            RMSE=float(np.sqrt(np.mean(err ** 2))),
                            mean_over=float(over.mean()),
                            max_over=float(over.max()),
                            mean_under=float(under.mean()),
                            OAR=float(np.mean(pred > qr_true)))
        print(f"  {name:24s} MAE={results[key]['MAE']:6.3f} "
              f"RMSE={results[key]['RMSE']:6.3f} OAR={results[key]['OAR']:5.3f} "
              f"mean_over={results[key]['mean_over']:5.3f} "
              f"max_over={results[key]['max_over']:5.3f} "
              f"mean_under={results[key]['mean_under']:5.3f}")

    truth.to_csv(os.path.join(PATHS["validation"], "test_truth.csv"),
                 index=False)
    pd.DataFrame([r for r in results.values()]).to_csv(
        os.path.join(PATHS["validation"], "test_metrics.csv"), index=False)

    # ---- closed-loop SVR for Model A (rounded to 0.5) --------------------
    print("\n=== closed-loop SVR (Model A rounded 0.5) ===")
    delta_v = CONSTRAINTS["delta_v"]
    outmin = CONSTRAINTS["outflow_ratio_min"]
    outmax = CONSTRAINTS["outflow_ratio_max"]
    dfloor = CONSTRAINTS["density_floor"]

    svr_scen = []
    for _, row in truth.iterrows():
        if not row["base_pass"]:
            continue
        qhat = max(0.0, round(float(row["pred_A"]) * 2.0) / 2.0)
        for s in range(N_SEEDS_VALIDATION):
            svr_scen.append((row["W"], L, row["qp"], qhat, s, None, None, None))
    svr_csv = os.path.join(PATHS["validation"], "closed_loop.csv")
    svr_df = run_batch(svr_scen, n_procs=n_procs, out_csv=svr_csv,
                       label="closed-loop A")

    svr_rows = []
    for _, trow in truth.iterrows():
        if not trow["base_pass"]:
            continue
        Wv, qpv, vbar = trow["W"], trow["qp"], trow["vbar"]
        qhat = max(0.0, round(float(trow["pred_A"]) * 2.0) / 2.0)
        sub = svr_df[(svr_df["W"] == Wv) & (svr_df["qp"] == qpv)]
        flags = [evaluate_constraints(m, vbar, delta_v, outmin, outmax, dfloor)
                 for m in sub.to_dict("records")]
        pf = float(np.mean([f["pass"] for f in flags]))
        mean_Rv = float(np.mean([f["Rv"] for f in flags]))
        mean_fr = float(sub["flow_ratio"].mean())
        mean_rho = float(sub["mean_density"].mean())
        viol = not (mean_Rv >= (1.0 - delta_v) and outmin <= mean_fr <= outmax
                    and mean_rho <= dfloor)
        svr_rows.append(dict(W=Wv, qp=qpv, q_hat=qhat,
                             qr_star=trow["qr_star"], pass_frac=pf,
                             violated=viol, mean_Rv=mean_Rv))
    svr_table = pd.DataFrame(svr_rows)
    svr = float(svr_table["violated"].mean()) if len(svr_table) else float("nan")
    print(f"  SVR (Model A rounded 0.5) = {svr:.4f} "
          f"({int(svr_table['violated'].sum())}/{len(svr_table)} feasible cells)")
    svr_table.to_csv(os.path.join(PATHS["validation"], "svr_table.csv"),
                     index=False)

    # ---- closed-loop SVR for safe-side variants (A-floor, A-iso) ---------
    print("\n=== closed-loop SVR (safe-side variants) ===")
    closed_loop_main(n_procs=n_procs)

    return truth, svr_table, results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-procs", type=int, default=None)
    ap.add_argument("--skip-sim", action="store_true",
                    help="reuse existing CSVs (aggregate + fit + validate only)")
    args = ap.parse_args()
    np_ = args.n_procs

    if not args.skip_sim:
        add_narrow_widths(np_)
        resolve_ceiling(os.path.join(PATHS["baseline"], "baseline_results.csv"),
                        os.path.join(PATHS["sweeps"], "sweep_results.csv"),
                        [(W, qp) for W in WIDTHS_TRAIN for qp in PED_FLOWS_TRAIN],
                        N_SEEDS_SWEEP, n_procs=np_, label="train")

    aggregate_training()

    import fit_quota
    fit_quota.fit_and_save()

    revalidate_test(n_procs=np_)

    # refresh secondary outputs (threshold sensitivity is cheap; figures/report
    # read the updated CSVs)
    import sensitivity
    sensitivity.rederive_thresholds()
    import figures
    figures.main()
    import calibration
    calibration.main()
    import report
    report.main()

    print("\n=== P0 extension complete ===")


if __name__ == "__main__":
    main()
