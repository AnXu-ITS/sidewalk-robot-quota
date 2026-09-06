# -*- coding: utf-8 -*-
"""
external_ground_truth.py  (frozen BJ/SH external confirmation driver)
=====================================================================
Run the SUMO-JuPedSim baseline + ascending robot sweep for the frozen
Beijing/Shanghai external cells (external_bjsh/cells.json), under the PER-SEED
criterion (Pr(C_p=1) >= 0.95), the contiguous-pass rule, identical seed lists
across both cities, and a 100-seed confirmation at q_deploy and q_deploy +/- 1.

SEALED: this driver simulates and derives the ground truth ONLY. It computes no
model statistics (SVR / MAE / OAR). Unblinding happens later in
external_analysis.py once BOTH cities are complete. It does, however, compute
q_deploy = floor(q_hat) of the FROZEN final model (quota_params_final.json) so
the 100-seed confirmation levels can be generated during the run.

Frozen protocol values (external_bjsh/protocol.md):
  * seeds sweep/baseline = 0..29 ; confirmation = 0..99  (identical BJ & SH)
  * per-seed pass: >= 29/30 (sweep) or >= 95/100 (confirm) seeds individually
    satisfy R_v>=0.90 AND 0.90<=flow_ratio<=1.20 AND density<=1.20
  * q_r* = max CONTIGUOUS passing level from 0 (ascending early-stop sweep
    makes contiguity automatic; an explicit assertion guards it)
  * two flow levels per cell: normal = round(mean(q_p_off)),
    peak = round(mean(q_p_peak))  (POI priors, tier A)

Usage:
  python external_ground_truth.py --city beijing  --n-procs 24
  python external_ground_truth.py --city shanghai --n-procs 24

Outputs (external_bjsh/outputs/<city>/):
  baseline.csv  sweep.csv  confirm.csv  ground_truth.csv  completeness.log
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (SIM, CONSTRAINTS, PATHS, ROBOT_FLOWS_ALL)  # noqa: E402
from simulator import evaluate_constraints  # noqa: E402
from run_batch import run_batch  # noqa: E402
from build_final_model import (load_seedwise_model, qlow,
                               final_predict)  # noqa: E402

L = SIM["L"]
ROOT = os.path.normpath(os.path.join(PATHS["root"], ".."))
EXT = os.path.join(ROOT, "external_bjsh")
CELLS_JSON = os.path.join(EXT, "cells.json")

CONF = CONSTRAINTS["conf_level"]
DELTA_V = CONSTRAINTS["delta_v"]
OUTMIN = CONSTRAINTS["outflow_ratio_min"]
OUTMAX = CONSTRAINTS["outflow_ratio_max"]
DFLOOR = CONSTRAINTS["density_floor"]

SEEDS = list(range(30))          # frozen: 0..29
CONFIRM_SEEDS = list(range(100))  # frozen: 0..99
QR_LEVELS = sorted(q for q in ROBOT_FLOWS_ALL if q != 0)
MAX_QR = max(QR_LEVELS)

CITY_CODE = {"berlin": "BER"}


def flow_levels(c):
    lo = round(float(np.mean(c["q_p_off"])))
    hi = round(float(np.mean(c["q_p_peak"])))
    return sorted({lo, hi})


def per_seed_pass(sub, vbar):
    n = len(sub)
    if n == 0 or vbar <= 0:
        return 0.0
    flags = [evaluate_constraints(m, vbar, DELTA_V, OUTMIN, OUTMAX, DFLOOR)
             for m in sub.to_dict("records")]
    return float(sum(f["pass"] for f in flags) / n)


def baseline_ok(sub):
    n = len(sub)
    if n == 0:
        return False
    ok = ((sub["mean_density"] <= DFLOOR)
          & (sub["flow_ratio"] >= OUTMIN)
          & (sub["flow_ratio"] <= OUTMAX)).to_numpy(bool)
    return float(ok.mean()) >= CONF


def main(city, n_procs=None, seeds=None, limit=None, out_dir=None,
         cells_json=CELLS_JSON):
    seeds = seeds if seeds is not None else SEEDS
    code = CITY_CODE[city]
    out_dir = out_dir or os.path.join(EXT, "outputs", city)
    os.makedirs(out_dir, exist_ok=True)
    model = load_seedwise_model()

    with open(cells_json, encoding="utf-8") as f:
        cells = [c for c in json.load(f)["cells"] if c["city"] == city]
    if limit:
        cells = cells[:limit]
    grid = []
    for c in cells:
        for qp in flow_levels(c):
            grid.append((c, qp, f"{c['cell_id']}|qp{qp}"))
    all_tags = {t for _, _, t in grid}
    print(f"=== {city}: {len(cells)} cells x 2 flows = {len(grid)} combos, "
          f"seeds={seeds} ===", flush=True)

    log = [f"{city} grid: {len(cells)} cells, {len(grid)} combos"]

    # ---- Phase A: baselines (30 seeds) ----------------------------------
    base_csv = os.path.join(out_dir, "baseline.csv")
    base_scen = []
    for c, qp, tag in grid:
        cl = [list(p) for p in c["centerline"]]
        for seed in range(seeds):
            base_scen.append((c["W_eff"], L, float(qp), 0.0, seed,
                              None, None, None, cl, tag))
    base_df = run_batch(base_scen, n_procs=n_procs, out_csv=base_csv,
                        label=f"{city}-base")
    log.append(f"baseline: {len(base_df)} rows")

    vbar, bad = {}, set()
    for tag, g in base_df.groupby("tag", sort=True):
        vbar[tag] = float(g["mean_speed"].mean())
        if not baseline_ok(g):
            bad.add(tag)
    good = [g for g in grid if g[2] not in bad]
    log.append(f"Case-1 (baseline per-seed fail): {len(bad)} combos; "
               f"{len(good)} proceed")

    # ---- Phase B: ascending early-stop sweep (30 seeds, per-seed) -------
    sweep_csv = os.path.join(out_dir, "sweep.csv")
    active = {tag for _, _, tag in good}
    scen_of = {tag: (c, qp) for c, qp, tag in good}
    parts = []
    for qr in QR_LEVELS:
        if not active:
            break
        scen = []
        for tag in sorted(active):
            c, qp = scen_of[tag]
            cl = [list(p) for p in c["centerline"]]
            for seed in range(seeds):
                scen.append((c["W_eff"], L, float(qp), float(qr), seed,
                             None, None, None, cl, tag))
        part = run_batch(scen, n_procs=n_procs, out_csv=None,
                         label=f"{city}-sweep{qr}")
        parts.append(part)
        for tag in list(active):
            sub = part[part["tag"] == tag]
            if len(sub) and per_seed_pass(sub, vbar[tag]) < CONF:
                active.discard(tag)  # first failure -> stop (contiguity)
    sweep_df = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    sweep_df.to_csv(sweep_csv, index=False)
    log.append(f"sweep: {len(sweep_df)} rows, stopped at qr={QR_LEVELS[len(parts)-1] if parts else 0}")

    # ---- q_r* = max contiguous passing level (assert contiguity) --------
    qr_star = {t: 0.0 for t in all_tags}
    for tag, g in sweep_df.groupby("tag", sort=True):
        passed = []
        for qr, sub in g.groupby("qr", sort=True):
            passed.append(per_seed_pass(sub, vbar.get(tag, 0.0)) >= CONF)
        # contiguous: every level below the first failure must have passed
        for i in range(1, len(passed)):
            assert passed[i] <= passed[i - 1], \
                f"contiguity violation in {tag} at level index {i}"
        qr_star[tag] = float(QR_LEVELS[sum(passed) - 1]) if any(passed) else 0.0

    # ---- q_deploy from the FROZEN final model ----------------------------
    geom = {c["cell_id"]: {"max_turn_deg": c.get("max_turn_deg", 0.0),
                           "cum_turn_deg": c.get("cum_turn_deg", 0.0)}
            for c in cells}
    q_deploy = {}
    for c, qp, tag in grid:
        row = pd.DataFrame([{"cell_id": c["cell_id"], "qp": float(qp),
                             "W": c["W_eff"], "vbar": vbar.get(tag, 0.0)}])
        q_hat = float(final_predict(row, model, geom=geom)[0])
        q_deploy[tag] = float(np.floor(q_hat))

    # ---- Phase C: 100-seed confirmation at q_deploy +/- 1 ----------------
    confirm_seeds = CONFIRM_SEEDS if seeds == SEEDS else list(range(seeds))
    confirm_csv = os.path.join(out_dir, "confirm.csv")
    c_scen = []
    c_tags = []
    for c, qp, tag in grid:
        if tag in bad:
            continue  # Case-1: no robot admitted, nothing to confirm
        levels = sorted({max(0.0, q_deploy[tag] - 1), q_deploy[tag],
                         q_deploy[tag] + 1})
        cl = [list(p) for p in c["centerline"]]
        for lvl in levels:
            for seed in confirm_seeds:
                c_scen.append((c["W_eff"], L, float(qp), float(lvl), seed,
                               None, None, None, cl, tag))
    if c_scen:
        c_df = run_batch(c_scen, n_procs=n_procs, out_csv=confirm_csv,
                         label=f"{city}-confirm")
    else:
        c_df = pd.DataFrame()
        c_df.to_csv(confirm_csv, index=False)
    log.append(f"confirm: {len(c_df)} rows (q_deploy +/- 1, 100 seeds)")

    # ---- ground-truth manifest -------------------------------------------
    rec = []
    for c, qp, tag in grid:
        b = base_df[base_df["tag"] == tag]
        rec.append(dict(
            cell_id=c["cell_id"], city=c["city"], city_code=c.get("city_code"),
            group=c.get("group"), type=c["type"], context=c["context"],
            W=round(c["W_eff"], 3), width_src=c.get("width_src"),
            sinuosity=round(c.get("sinuosity", 1.0), 4),
            max_turn_deg=c.get("max_turn_deg", 0.0),
            cum_turn_deg=c.get("cum_turn_deg", 0.0),
            qp=qp, vbar=round(float(b["mean_speed"].mean()), 3) if len(b) else 0.0,
            base_pass=tag not in bad,
            qr_star=float(qr_star[tag]),
            q_deploy=q_deploy.get(tag, 0.0),
            above_upper=bool(qr_star[tag] >= MAX_QR)))
    res = pd.DataFrame(rec).sort_values(["cell_id", "qp"])
    res.to_csv(os.path.join(out_dir, "ground_truth.csv"), index=False)

    log.append(f"ground_truth: {len(res)} combos")
    with open(os.path.join(out_dir, "completeness.log"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(log) + "\n")
    print("\n".join(log), flush=True)
    print(f"wrote {out_dir}", flush=True)
    return res


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", required=True, choices=["berlin"])
    ap.add_argument("--n-procs", type=int, default=None)
    ap.add_argument("--seeds", type=int, default=None,
                    help="seeds per level (default 30); 2 for smoke")
    ap.add_argument("--limit", type=int, default=None,
                    help="run only the first N cells (smoke testing)")
    ap.add_argument("--out-dir", default=None,
                    help="override output dir (smoke runs must NOT write to "
                         "external_bjsh/outputs/<city>)")
    ap.add_argument("--cells", default=CELLS_JSON,
                    help="override cells.json path (smoke)")
    args = ap.parse_args()
    main(args.city, n_procs=args.n_procs, seeds=args.seeds, limit=args.limit,
         out_dir=args.out_dir, cells_json=args.cells)
