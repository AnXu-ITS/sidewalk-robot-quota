# -*- coding: utf-8 -*-
"""
bend_position_sweep.py  (P2 item 3 follow-up)
=============================================
Corner-POSITION x angle sweep to formalize the sharp-corner guard: does the
robot-throughput collapse depend on WHERE the single corner sits along the
corridor (entry / middle / exit), and is there a lower collapse threshold
below the 30 deg tested in bend_sweep.py?

Geometry (50 m arc, single corner):
  entry  5 m + 45 m (corner 5 m after the source)
  middle 25 m + 25 m (corner at midpoint; = bend_sweep)
  exit   45 m + 5 m (corner 5 m before the exit, short stub -> matches the real
          AMS-1351790552 failure, which had a 90 deg turn into a 2.4 m stub)

Grid: theta {0,15,20,30,45,60,75,90} deg x position {middle,entry,exit}
      (0 deg is the straight reference, position-independent) at W=2.5 m,
      q_p=50 ped/min, 30 seeds -> 1 + 7*3 = 22 combos (~40 min at 12 workers).

Usage:
  python bend_position_sweep.py --n-procs 12
  python bend_position_sweep.py --smoke
  python bend_position_sweep.py --skip-sim
"""
import math
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (SIM, CONSTRAINTS, PATHS, ROBOT_FLOWS_ALL,
                    N_SEEDS_SWEEP)  # noqa: E402
from run_batch import run_batch  # noqa: E402

L = SIM["L"]
OUT_DIR = os.path.join(PATHS["root"], "outputs", "bend_position")

DFLOOR = CONSTRAINTS["density_floor"]
DELTA_V = CONSTRAINTS["delta_v"]
OUTMIN = CONSTRAINTS["outflow_ratio_min"]
OUTMAX = CONSTRAINTS["outflow_ratio_max"]
QR_LEVELS = sorted(q for q in ROBOT_FLOWS_ALL if q != 0)
MAX_QR = max(QR_LEVELS)

BEND_ANGLES = [0, 15, 20, 30, 45, 60, 75, 90]
POSITIONS = ["middle", "entry", "exit"]
W_FIX = 2.5
QP = 50
STUB = 5.0


def bend_centerline(theta_deg, pos="middle"):
    if theta_deg <= 0:
        return [[0.0, 0.0], [L, 0.0]]
    th = math.radians(theta_deg)
    if pos == "entry":
        a, b = STUB, L - STUB
    elif pos == "exit":
        a, b = L - STUB, STUB
    else:  # middle
        a = b = L / 2.0
    return [[0.0, 0.0], [a, 0.0], [a + b * math.cos(th), b * math.sin(th)]]


def sinuosity_of(cl):
    arc = sum(math.hypot(cl[i + 1][0] - cl[i][0], cl[i + 1][1] - cl[i][1])
              for i in range(len(cl) - 1))
    chord = math.hypot(cl[-1][0] - cl[0][0], cl[-1][1] - cl[0][1])
    return arc / chord if chord > 0.05 else 1.0


def build_grid():
    grid = []
    for th in BEND_ANGLES:
        positions = POSITIONS if th > 0 else ["middle"]
        for pos in positions:
            cl = bend_centerline(th, pos)
            c = dict(cell_id=f"bp{pos}{th}", city="synthetic", city_code="SYN",
                     type="B", context="synthetic", W_eff=W_FIX,
                     centerline=cl, sinuosity=round(sinuosity_of(cl), 4))
            tag = f"bp{pos}{th}|qp{QP}"
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
    base_csv = os.path.join(OUT_DIR, "bp_baseline.csv")

    grid = build_grid()
    print(f"=== corner-position sweep: {len(BEND_ANGLES)} angles x "
          f"{len(POSITIONS)} positions = {len(grid)} combos, W={W_FIX}, "
          f"qp={QP}, seeds={seeds} ===", flush=True)
    for c, qp, tag in grid:
        print(f"  {tag:22s} W={c['W_eff']} sin={c['sinuosity']}", flush=True)

    # Phase A
    if skip_sim and os.path.exists(base_csv) and os.path.getsize(base_csv) > 0:
        base_df = pd.read_csv(base_csv)
    else:
        scen = [(c["W_eff"], L, float(qp), 0.0, seed, None, None, None,
                 [list(p) for p in c["centerline"]], tag)
                for c, qp, tag in grid for seed in range(seeds)]
        print(f"=== Phase A: {len(scen)} baseline scenarios ===", flush=True)
        base_df = run_batch(scen, n_procs=n_procs, out_csv=base_csv,
                            label="bpposbase")

    vbar, bad = {}, set()
    for tag, g in base_df.groupby("tag", sort=True):
        vbar[tag] = float(g["mean_speed"].mean())
        if g["mean_density"].mean() > DFLOOR or \
                g["flow_ratio"].mean() < 0.85 or \
                g["flow_ratio"].mean() > OUTMAX:
            bad.add(tag)
    good = [(c, qp, tag) for c, qp, tag in grid if tag not in bad]
    print(f"=== Case-1: {len(bad)}; {len(good)} proceed ===", flush=True)

    # Phase B
    active = {tag for _, _, tag in good}
    scen_of = {tag: (c, qp) for c, qp, tag in good}
    parts = []
    for qr in QR_LEVELS:
        part_csv = os.path.join(OUT_DIR, f"bp_sweep_{qr}.csv")
        if skip_sim and os.path.exists(part_csv) and os.path.getsize(part_csv) > 0:
            part = pd.read_csv(part_csv)
        else:
            if not active:
                break
            scen = [(c["W_eff"], L, float(qp), float(qr), seed, None, None,
                     None, [list(p) for p in c["centerline"]], tag)
                    for tag in sorted(active)
                    for c, qp in [scen_of[tag]] for seed in range(seeds)]
            print(f"  --- qr={qr}: {len(scen)} scenarios, {len(active)} "
                  f"active ---", flush=True)
            part = run_batch(scen, n_procs=n_procs, out_csv=part_csv,
                             label=f"bppos_{qr}")
        parts.append(part)
        for tag in list(active):
            sub = part[part["tag"] == tag]
            if len(sub) and not combo_passes(sub, vbar[tag]):
                active.discard(tag)

    sweep_df = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    sweep_df.to_csv(os.path.join(OUT_DIR, "bp_sweep.csv"), index=False)

    qr_star = {tag: 0.0 for tag in [t for _, _, t in grid]}
    for tag, g in sweep_df.groupby("tag", sort=True):
        for qr, sub in g.groupby("qr", sort=True):
            if combo_passes(sub, vbar.get(tag, 0.0)):
                qr_star[tag] = max(qr_star[tag], float(qr))

    rec = []
    for c, qp, tag in grid:
        cid = tag.split("|")[0][2:]          # e.g. "middle30", "entry0"
        pos = "".join(ch for ch in cid if ch.isalpha())
        th = "".join(ch for ch in cid if ch.isdigit())
        rec.append(dict(position=pos, theta=int(th) if th else 0,
                        W=c["W_eff"], sinuosity=c["sinuosity"], qp=qp,
                        qr_star=float(qr_star[tag]),
                        base_pass=tag not in bad))
    res = pd.DataFrame(rec).sort_values(["position", "theta"])
    res.to_csv(os.path.join(OUT_DIR, "bp_results.csv"), index=False)

    print("\n=== corner-position q_r* (rows=theta, cols=position) ===", flush=True)
    piv = res.pivot_table(index="theta", columns="position", values="qr_star")
    print(piv.to_string(), flush=True)
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
