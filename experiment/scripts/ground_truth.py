"""
ground_truth.py
===============
Generate the simulation-derived reference quota dataset.

Two-phase procedure (following the plan's section 13-17):

  Phase A - pedestrian-only baselines: for every (W, q_p) cell run q_r = 0
            over N seeds to obtain the reference mean speed vbar and to test
            whether the pedestrian-only state is already acceptable.
  Phase B - Case-1 detection: if the pedestrian-only baseline already violates
            the density / flow-stability floor, the cell is over capacity and
            q_r* = 0 (plan section 17, Case 1) -- no robot sweep is run.
  Phase C - robot-flow sweep: for the remaining cells, sweep q_r in ROBOT_FLOWS
            (excluding 0) and evaluate the pedestrian-first service
            constraints per seed; q_r* = max q_r with Pr(C_p = 1) >= 0.95.

Outputs
-------
  outputs/baseline/baseline_results.csv
  outputs/sweeps/sweep_results.csv
  outputs/quota_labels/quota_dataset.csv    (q_p, W, q_r*, diagnostics)
  outputs/quota_labels/quota_detail.csv     (per (W,qp,qr) pass statistics)
"""

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (PED, WALL, ROBOT, SIM, CONSTRAINTS, PATHS,
                    WIDTHS_TRAIN, PED_FLOWS_TRAIN, ROBOT_FLOWS,
                    N_SEEDS_SWEEP)
from simulator import evaluate_constraints
from run_batch import run_batch

L = SIM["L"]


def build_baseline_scenarios():
    scen = []
    for W in WIDTHS_TRAIN:
        for qp in PED_FLOWS_TRAIN:
            for seed in range(N_SEEDS_SWEEP):
                scen.append((W, L, qp, 0.0, seed, None, None, None))
    return scen


def build_sweep_scenarios(cells):
    """cells: iterable of (W, qp) that passed the baseline."""
    scen = []
    for W, qp in cells:
        for qr in ROBOT_FLOWS:
            if qr == 0:
                continue
            for seed in range(N_SEEDS_SWEEP):
                scen.append((W, L, qp, qr, seed, None, None, None))
    return scen


def case1_cells(baseline_df, dfloor=None, outmin=None):
    """Return the set of (W, qp) whose pedestrian-only state is unacceptable."""
    dfloor = CONSTRAINTS["density_floor"] if dfloor is None else dfloor
    outmin = 0.85 if outmin is None else outmin
    bad = set()
    for (W, qp), g in baseline_df.groupby(["W", "qp"], sort=True):
        mean_density = g["mean_density"].mean()
        mean_flow_ratio = g["flow_ratio"].mean()
        if mean_density > dfloor or mean_flow_ratio < outmin:
            bad.add((W, qp))
    return bad


def derive_quota(baseline_df, sweep_df, delta_v=None, conf=None):
    delta_v = CONSTRAINTS["delta_v"] if delta_v is None else delta_v
    conf = CONSTRAINTS["conf_level"] if conf is None else conf
    outmin = CONSTRAINTS["outflow_ratio_min"]
    dfloor = CONSTRAINTS["density_floor"]

    records = []
    for W in WIDTHS_TRAIN:
        for qp in PED_FLOWS_TRAIN:
            base = baseline_df[(baseline_df["W"] == W) & (baseline_df["qp"] == qp)]
            vbar = base["mean_speed"].mean() if len(base) else 0.0
            mean_density_base = base["mean_density"].mean() if len(base) else 0.0
            mean_fr_base = base["flow_ratio"].mean() if len(base) else 0.0
            base_pass = (mean_density_base <= dfloor) and (mean_fr_base >= 0.85)

            qr_star = 0.0
            above_upper = False
            rows = []
            if base_pass:
                sub_all = sweep_df[(sweep_df["W"] == W) & (sweep_df["qp"] == qp)]
                for qr in [q for q in ROBOT_FLOWS if q != 0]:
                    sub = sub_all[sub_all["qr"] == qr]
                    if len(sub) == 0:
                        continue
                    # mean-based pedestrian-service constraint (plan section 5.1)
                    mean_Rv = float(sub["mean_speed"].mean() / vbar) if vbar > 0 else 0.0
                    mean_flow_ratio = float(sub["flow_ratio"].mean())
                    mean_density = float(sub["mean_density"].mean())
                    pass_mean = (mean_Rv >= (1.0 - delta_v) and
                                 mean_flow_ratio >= outmin and
                                 mean_density <= dfloor)
                    # per-seed pass fraction (reported; noisier at low q_p)
                    flags = [evaluate_constraints(m, vbar, delta_v, outmin,
                                                  dfloor)
                             for m in sub.to_dict("records")]
                    pass_frac = float(np.mean([f["pass"] for f in flags]))
                    rows.append(dict(W=W, qp=qp, qr=qr, pass_frac=pass_frac,
                                     mean_Rv=mean_Rv,
                                     mean_speed=sub["mean_speed"].mean(),
                                     mean_density=mean_density,
                                     mean_flow_ratio=mean_flow_ratio))
                    if pass_mean:
                        qr_star = qr
                if rows and all(r["mean_Rv"] >= (1.0 - delta_v) and
                                r["mean_flow_ratio"] >= outmin and
                                r["mean_density"] <= dfloor for r in rows):
                    above_upper = True

            records.append(dict(
                W=W, qp=qp, vbar=vbar, base_pass=base_pass,
                mean_density_base=mean_density_base, mean_fr_base=mean_fr_base,
                qr_star=qr_star, above_upper=above_upper, row_details=rows,
            ))
    return records


def main(n_procs=None, skip_sim=False):
    base_csv = os.path.join(PATHS["baseline"], "baseline_results.csv")
    sweep_csv = os.path.join(PATHS["sweeps"], "sweep_results.csv")

    if skip_sim and os.path.exists(base_csv):
        base_df = pd.read_csv(base_csv)
        sweep_df = pd.read_csv(sweep_csv) if os.path.exists(sweep_csv) else pd.DataFrame()
        print("=== Reusing existing baseline/sweep CSVs (skip_sim) ===")
    else:
        # ---- Phase A: baselines ------------------------------------------
        print("=== Phase A: pedestrian-only baselines ===")
        base_scen = build_baseline_scenarios()
        base_df = run_batch(base_scen, n_procs=n_procs, out_csv=base_csv,
                            label="baseline")

        # ---- Phase B: Case-1 detection ------------------------------------
        bad = case1_cells(base_df)
        good = [(W, qp) for W in WIDTHS_TRAIN for qp in PED_FLOWS_TRAIN
                if (W, qp) not in bad]
        print(f"=== Phase B: {len(bad)} over-capacity cells (q_r*=0); "
              f"{len(good)} cells proceed to robot sweep ===")
        for W, qp in sorted(bad):
            print(f"  Case-1: W={W} qp={qp}")

        # ---- Phase C: robot sweep ----------------------------------------
        sweep_df = pd.DataFrame()
        if good:
            print("=== Phase C: robot-flow sweep ===")
            sweep_scen = build_sweep_scenarios(good)
            sweep_df = run_batch(sweep_scen, n_procs=n_procs, out_csv=sweep_csv,
                                 label="robot sweep")
        else:
            print("=== Phase C: skipped (no feasible cells) ===")

    # ---- aggregate --------------------------------------------------------
    records = derive_quota(base_df, sweep_df)
    summary = pd.DataFrame([{k: r[k] for k in
                             ("W", "qp", "vbar", "base_pass",
                              "mean_density_base", "mean_fr_base",
                              "qr_star", "above_upper")} for r in records])
    detail_rows = [d for r in records for d in r["row_details"]]
    detail = pd.DataFrame(detail_rows)

    quota_csv = os.path.join(PATHS["quota_labels"], "quota_dataset.csv")
    detail_csv = os.path.join(PATHS["quota_labels"], "quota_detail.csv")
    summary.to_csv(quota_csv, index=False)
    detail.to_csv(detail_csv, index=False)

    print("\n=== Reference quota dataset q_r* (rows=qp, cols=W) ===")
    piv = summary.pivot(index="qp", columns="W", values="qr_star")
    print(piv.to_string())
    print(f"\nwrote {quota_csv} and {detail_csv}")
    return summary, detail, records


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-procs", type=int, default=None)
    ap.add_argument("--skip-sim", action="store_true",
                    help="reuse existing baseline/sweep CSVs (aggregate only)")
    args = ap.parse_args()
    main(n_procs=args.n_procs, skip_sim=args.skip_sim)
