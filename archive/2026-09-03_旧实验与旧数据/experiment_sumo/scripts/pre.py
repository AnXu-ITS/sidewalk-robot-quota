"""
pre.py
======
Pedestrian Replacement Equivalent (PRE) analysis.

The robot is NOT a "special pedestrian".  This stage quantifies how many
pedestrians one robot is worth, in the same spirit as the traffic-engineering
PCU (passenger-car unit):

    PRE(q_p, W, split) = D_s(robot) / D_s(ped)

with the *marginal* speed-retention impacts (q_r -> 0):

    D_s(robot) = v_bar(q_p, W) - mean_speed(q_p, W, q_r = 1)   [m/s per robot/min]
    D_s(ped)   = (v_bar(q_p, W) - v_bar(q_p + 10, W)) / 10     [m/s per ped/min]

so that "1 robot ~= PRE pedestrians".  PRE is reported as a function of
sidewalk width W, pedestrian flow q_p, and the directional split, i.e. the
robot-equivalent is NOT a constant but a surface.

Inputs
------
  outputs/baseline/baseline_results.csv   (split = 0.5)
  outputs/sweeps/sweep_results.csv        (split = 0.5)

Outputs
-------
  outputs/sensitivity/pre_surface.csv     PRE(q_p, W) at split = 0.5
  outputs/sensitivity/pre_summary.csv     width-averaged PRE ("1 robot ~= X ped")
  outputs/sensitivity/pre_split.csv       PRE vs directional split (0.3/0.5/0.7)
"""

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (PATHS, SIM, WIDTHS_TRAIN, PED_FLOWS_TRAIN)
from run_batch import run_batch

L = SIM["L"]


def compute_pre(base_df, sweep_df, split_label):
    """Return a DataFrame of PRE(q_p, W) for one directional split."""
    rows = []
    for W in WIDTHS_TRAIN:
        for qp in PED_FLOWS_TRAIN:
            base = base_df[(base_df["W"] == W) & (base_df["qp"] == qp)]
            if len(base) == 0:
                continue
            vbar = float(base["mean_speed"].mean())

            # marginal robot impact: 1 robot/min (q_r = 1), 30-seed mean
            rob = sweep_df[(sweep_df["W"] == W) & (sweep_df["qp"] == qp) &
                           (sweep_df["qr"] == 1.0)]
            if len(rob) == 0:
                continue
            drobot = vbar - float(rob["mean_speed"].mean())   # m/s per robot/min

            # marginal pedestrian impact: forward diff over the 10-ped/min grid
            if qp + 10 in PED_FLOWS_TRAIN:
                nxt = base_df[(base_df["W"] == W) & (base_df["qp"] == qp + 10)]
                vbar_next = float(nxt["mean_speed"].mean())
                dped = (vbar - vbar_next) / 10.0
            elif qp - 10 in PED_FLOWS_TRAIN:
                prv = base_df[(base_df["W"] == W) & (base_df["qp"] == qp - 10)]
                vbar_prev = float(prv["mean_speed"].mean())
                dped = (vbar_prev - vbar) / 10.0
            else:
                continue

            pre = drobot / dped if dped > 1e-6 else np.nan
            rows.append(dict(W=W, qp=qp, vbar=vbar,
                             drobot=drobot, dped=dped, PRE=pre))
    df = pd.DataFrame(rows)
    df["split"] = split_label
    return df


def _run_split(split, n_procs, out_tag):
    """Baseline + q_r=1 sweep at one directional split, for the PRE marginals."""
    scen = []
    for W in WIDTHS_TRAIN:
        for qp in PED_FLOWS_TRAIN:
            for seed in range(30):
                scen.append((W, L, qp, 0.0, seed, None, None, split))
                scen.append((W, L, qp, 1.0, seed, None, None, split))
    out_csv = os.path.join(PATHS["sensitivity"], f"pre_raw_{out_tag}.csv")
    return run_batch(scen, n_procs=n_procs, out_csv=out_csv,
                     label=f"pre split {split}")


def main(n_procs=None, do_split_sensitivity=True):
    base_df = pd.read_csv(os.path.join(PATHS["baseline"], "baseline_results.csv"))
    sweep_df = pd.read_csv(os.path.join(PATHS["sweeps"], "sweep_results.csv"))

    frames = [compute_pre(base_df, sweep_df, SIM["bidirectional_split"])]

    if do_split_sensitivity:
        for split in (0.3, 0.7):
            raw = _run_split(split, n_procs, f"{split:.1f}")
            b = raw[raw["qr"] == 0.0]
            s = raw[raw["qr"] == 1.0]
            frames.append(compute_pre(b, s, split))

    surf = pd.concat(frames, ignore_index=True)

    # surface at the base split
    base_split = SIM["bidirectional_split"]
    surf_base = surf[surf["split"] == base_split]
    surf_csv = os.path.join(PATHS["sensitivity"], "pre_surface.csv")
    surf_base.drop(columns=["split"]).to_csv(surf_csv, index=False)

    # width-averaged summary: "1 robot ~= X pedestrians at width W"
    summ = (surf_base.groupby("W")["PRE"].mean().reset_index()
            .rename(columns={"PRE": "PRE_mean"}))
    summ_csv = os.path.join(PATHS["sensitivity"], "pre_summary.csv")
    summ.to_csv(summ_csv, index=False)

    # full surface across splits
    split_csv = os.path.join(PATHS["sensitivity"], "pre_split.csv")
    surf.to_csv(split_csv, index=False)

    print("\n=== PRE surface at split = %.1f (rows = qp, cols = W) ===" % base_split)
    piv = surf_base.pivot(index="qp", columns="W", values="PRE")
    print(piv.round(2).to_string())
    print("\n=== width-averaged PRE (1 robot ~= X pedestrians) ===")
    for _, r in summ.iterrows():
        print(f"  W = {r['W']:.1f} m  ->  1 robot ~= {r['PRE_mean']:.2f} pedestrians")
    if do_split_sensitivity:
        print("\n=== PRE vs directional split (width-averaged) ===")
        sp = surf.groupby(["split", "W"])["PRE"].mean().reset_index()
        print(sp.pivot(index="W", columns="split", values="PRE").round(2).to_string())
    print(f"\nwrote {surf_csv}, {summ_csv}, {split_csv}")
    return surf, summ


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-procs", type=int, default=None)
    ap.add_argument("--no-split-sensitivity", action="store_true")
    args = ap.parse_args()
    main(n_procs=args.n_procs, do_split_sensitivity=not args.no_split_sensitivity)
