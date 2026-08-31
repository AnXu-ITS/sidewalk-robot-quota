# -*- coding: utf-8 -*-
"""
bend_sweep.py
=============
Controlled bend-angle x width mini-experiment to calibrate the sharp-corner
threshold for the quota algorithm (P2 follow-up).

Geometry: a symmetric V-bend, 25 m + 25 m arc, turning by theta at the midpoint
(0 deg = straight).  Sweeps robot flow ascending (early-stopped) to derive
q_r* per (theta, W) at a fixed pedestrian flow qp=50 (the flow where the real
Amsterdam sharp-corner cell AMS-1351790552 collapsed to q_r*=0).

Grid: theta in {0,30,45,60,75,90} x W in {2.0,2.5,3.0} x qp=50 x 30 seeds
     = 18 combos (~1 h at 12 workers).

Usage:
  python bend_sweep.py --n-procs 12
  python bend_sweep.py --smoke
  python bend_sweep.py --skip-sim        # re-derive q_r* from existing CSVs

Outputs (outputs/bend_sweep/):
  bend_baseline.csv, bend_sweep_{qr}.csv, bend_results.csv
"""
import math
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (PED, WALL, ROBOT, SIM, CONSTRAINTS, PATHS,
                    ROBOT_FLOWS_ALL, N_SEEDS_SWEEP)  # noqa: E402
from run_batch import run_batch  # noqa: E402

L = SIM["L"]
OUT_DIR = os.path.join(PATHS["root"], "outputs", "bend_sweep")

DFLOOR = CONSTRAINTS["density_floor"]
DELTA_V = CONSTRAINTS["delta_v"]
OUTMIN = CONSTRAINTS["outflow_ratio_min"]
OUTMAX = CONSTRAINTS["outflow_ratio_max"]
QR_LEVELS = sorted(q for q in ROBOT_FLOWS_ALL if q != 0)
MAX_QR = max(QR_LEVELS)

BEND_ANGLES = [0, 30, 45, 60, 75, 90]
WIDTHS = [2.0, 2.5, 3.0]
QP = 50


def bend_centerline(theta_deg):
    """Symmetric V-bend: 25 m + 25 m arc turning by theta_deg at midpoint."""
    a = b = L / 2.0
    if theta_deg <= 0:
        return [[0.0, 0.0], [L, 0.0]]
    th = math.radians(theta_deg)
    return [[0.0, 0.0], [a, 0.0], [a + b * math.cos(th), b * math.sin(th)]]


def sinuosity_of(cl):
    arc = sum(math.hypot(cl[i + 1][0] - cl[i][0], cl[i + 1][1] - cl[i][1])
              for i in range(len(cl) - 1))
    chord = math.hypot(cl[-1][0] - cl[0][0], cl[-1][1] - cl[0][1])
    return arc / chord if chord > 0.05 else 1.0


def build_grid():
    grid = []
    for th in BEND_ANGLES:
        for W in WIDTHS:
            cl = bend_centerline(th)
            c = dict(cell_id=f"bend{th}W{W}", city="synthetic", city_code="SYN",
                     type="B", context="synthetic", W_eff=W,
                     centerline=cl, sinuosity=round(sinuosity_of(cl), 4))
            tag = f"bend{th}W{W}|qp{QP}"
            grid.append((c, QP, tag))
    return grid


def flow_ok(fr):
    return OUTMIN <= fr <= OUTMAX


def combo_passes(sub, vbar):
    if len(sub) == 0 or vbar <= 0:
        return False
    mean_Rv = float(sub["mean_speed"].mean() / vbar)
    fr = float(sub["flow_ratio"].mean())
    dens = float(sub["mean_density"].mean())
    return mean_Rv >= (1.0 - DELTA_V) and flow_ok(fr) and dens <= DFLOOR


def main(n_procs=None, skip_sim=False, seeds=N_SEEDS_SWEEP):
    os.makedirs(OUT_DIR, exist_ok=True)
    base_csv = os.path.join(OUT_DIR, "bend_baseline.csv")
    sweep_csv = os.path.join(OUT_DIR, "bend_sweep.csv")

    grid = build_grid()
    all_tags = {tag for _, _, tag in grid}
    print(f"=== bend sweep grid: {len(BEND_ANGLES)} angles x {len(WIDTHS)} "
          f"widths = {len(grid)} combos, qp={QP}, seeds={seeds} ===", flush=True)
    for c, qp, tag in grid:
        print(f"  {tag:20s} theta={tag.split('W')[0][4:]:>3s}deg "
              f"W={c['W_eff']} sin={c['sinuosity']}", flush=True)

    # ---- Phase A: baselines ----
    if skip_sim and os.path.exists(base_csv) and os.path.getsize(base_csv) > 0:
        base_df = pd.read_csv(base_csv)
        print("=== reusing baseline CSV ===", flush=True)
    else:
        base_scen = []
        for c, qp, tag in grid:
            cl = [list(p) for p in c["centerline"]]
            for seed in range(seeds):
                base_scen.append((c["W_eff"], L, float(qp), 0.0, seed,
                                  None, None, None, cl, tag))
        print(f"=== Phase A: {len(base_scen)} baseline scenarios ===", flush=True)
        base_df = run_batch(base_scen, n_procs=n_procs, out_csv=base_csv,
                            label="bendbase")

    vbar, bad = {}, set()
    for tag, g in base_df.groupby("tag", sort=True):
        vbar[tag] = float(g["mean_speed"].mean())
        if g["mean_density"].mean() > DFLOOR or \
                g["flow_ratio"].mean() < 0.85 or \
                g["flow_ratio"].mean() > OUTMAX:
            bad.add(tag)
    good = [(c, qp, tag) for c, qp, tag in grid if tag not in bad]
    print(f"=== Case-1 (over capacity): {len(bad)}; {len(good)} proceed ===",
          flush=True)

    # ---- Phase B: ascending sweep ----
    active = {tag for _, _, tag in good}
    scen_of = {tag: (c, qp) for c, qp, tag in good}
    sweep_parts = []
    for qr in QR_LEVELS:
        part_csv = os.path.join(OUT_DIR, f"bend_sweep_{qr}.csv")
        if skip_sim and os.path.exists(part_csv) and os.path.getsize(part_csv) > 0:
            part = pd.read_csv(part_csv)
        else:
            if not active:
                print(f"  qr={qr}: no active combos, stop", flush=True)
                break
            scen = []
            for tag in sorted(active):
                c, qp = scen_of[tag]
                cl = [list(p) for p in c["centerline"]]
                for seed in range(seeds):
                    scen.append((c["W_eff"], L, float(qp), float(qr), seed,
                                 None, None, None, cl, tag))
            print(f"  --- qr={qr}: {len(scen)} scenarios, "
                  f"{len(active)} active ---", flush=True)
            part = run_batch(scen, n_procs=n_procs, out_csv=part_csv,
                             label=f"bendsweep_{qr}")
        sweep_parts.append(part)
        for tag in list(active):
            sub = part[part["tag"] == tag]
            if len(sub) and not combo_passes(sub, vbar[tag]):
                active.discard(tag)

    sweep_df = pd.concat(sweep_parts, ignore_index=True) if sweep_parts \
        else pd.DataFrame()
    sweep_df.to_csv(sweep_csv, index=False)

    # ---- derive q_r* ----
    qr_star = {tag: 0.0 for tag in all_tags}
    for tag, g in sweep_df.groupby("tag", sort=True):
        for qr, sub in g.groupby("qr", sort=True):
            if combo_passes(sub, vbar.get(tag, 0.0)):
                qr_star[tag] = max(qr_star[tag], float(qr))

    rec = []
    for c, qp, tag in grid:
        base = base_df[base_df["tag"] == tag]
        rec.append(dict(
            theta=int(tag.split("W")[0][4:]), W=c["W_eff"],
            sinuosity=c["sinuosity"], qp=qp,
            vbar=round(float(base["mean_speed"].mean()), 3) if len(base) else 0.0,
            base_pass=tag not in bad,
            qr_star=float(qr_star[tag]),
            above_upper=bool(qr_star[tag] >= MAX_QR)))
    res = pd.DataFrame(rec).sort_values(["W", "theta"])
    res_csv = os.path.join(OUT_DIR, "bend_results.csv")
    res.to_csv(res_csv, index=False)

    print("\n=== bend q_r* (rows=theta, cols=W) ===", flush=True)
    piv = res.pivot_table(index="theta", columns="W", values="qr_star")
    print(piv.to_string(), flush=True)
    print(f"wrote {res_csv}", flush=True)
    return res


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-procs", type=int, default=None)
    ap.add_argument("--skip-sim", action="store_true")
    ap.add_argument("--seeds", type=int, default=N_SEEDS_SWEEP)
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()
    if args.smoke:
        args.seeds = 3
    main(n_procs=args.n_procs, skip_sim=args.skip_sim, seeds=args.seeds)
