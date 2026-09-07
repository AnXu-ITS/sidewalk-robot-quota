# -*- coding: utf-8 -*-
"""v2 small-scale trial — bottleneck-equivalent-rectangle sweep.

Simulates the 9 cells that v2 recovers from OOD as *synthetic rectangles* of
width = W_eff (bottleneck width_p10 for complex-C, clamp-to-3.0 for wide A/B),
length 50 m, using the validated D2 `run_scenario` engine. This is the
"bottleneck-equivalent corridor" approximation — NOT the real junction polygon.

Protocol (same as the frozen D2 semantics):
  baseline qr=0 x 30 seeds -> base_pass (mean-based) -> robot sweep
  [1,2,3,4,5,6,8,10,12,15,18,20] x 30 seeds -> qr* (per-seed >=29/30).
"""
import csv
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_HK = os.path.abspath(os.path.join(_HERE, ".."))
_REPO = os.path.abspath(os.path.join(_HK, "..", ".."))
_PIPE = os.path.join(_REPO, "pipeline", "sim", "scripts")
sys.path.insert(0, _PIPE)

from config import PED, WALL, ROBOT, SIM, CONSTRAINTS  # noqa: E402
import simulator as SIM_MOD  # noqa: E402

RUNS = os.path.join(_HERE, "runs")
os.makedirs(RUNS, exist_ok=True)

ROBOT_FLOWS_ALL = [0, 1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 18, 20]
N_SEEDS = 30
CONF = 0.95
DFLOOR = CONSTRAINTS["density_floor"]
OUTMIN = CONSTRAINTS["outflow_ratio_min"]
OUTMAX = CONSTRAINTS["outflow_ratio_max"]
DELTA_V = CONSTRAINTS["delta_v"]
L = SIM["L"]

SEED_CSV = os.path.join(RUNS, "v2_seed_results.csv")
_FIELDS = ["cell_id", "qp", "qr", "seed", "W", "L", "mean_speed", "speed_count",
           "mean_density", "inflow_ped", "outflow_ped", "flow_ratio",
           "timed_out", "wall_s"]

# deterministic synthetic demand + W_eff for the 9 recovered cells
QP_RECOVERED = {
    "HK-ST-07": 60, "HK-ST-23": 60, "HK-ST-31": 30, "HK-ST-32": 50,
    "HK-ST-14": 30, "HK-ST-17": 40, "HK-ST-20": 20, "HK-ST-26": 30,
    "HK-ST-29": 50,
}


def _load_cells():
    frz = pd.read_csv(os.path.join(_HK, "sites",
                                   "HONG_KONG_FORMAL_SAMPLE_FREEZE.csv"))
    cells = {}
    for r in frz.itertuples():
        if r.cell_id not in QP_RECOVERED:
            continue
        if r.geometry_type == "C":
            W_eff = min(float(r.width_p10), 3.0)
        else:
            W_eff = min(float(r.W), 3.0)
        assert W_eff >= 1.6, f"{r.cell_id} W_eff {W_eff} < 1.6"
        cells[r.cell_id] = dict(W_eff=round(W_eff, 4), qp=QP_RECOVERED[r.cell_id],
                                geometry_type=r.geometry_type,
                                orig_W=float(r.W), width_p10=float(r.width_p10))
    return cells


_CELLS = _load_cells()


def run_one(task):
    cell_id, qp, qr, seed = task
    W_eff = _CELLS[cell_id]["W_eff"]
    t0 = time.time()
    try:
        m = SIM_MOD.run_scenario(W_eff, L, float(qp), float(qr), int(seed),
                                 PED, WALL, ROBOT, SIM)
        m["cell_id"] = cell_id
        m["wall_s"] = round(time.time() - t0, 3)
        return m
    except Exception as e:  # conservative FAIL, keep nothing (run_scenario kept dir)
        return dict(cell_id=cell_id, qp=float(qp), qr=float(qr), seed=int(seed),
                    W=float(W_eff), L=float(L), mean_speed=0.0, speed_count=0,
                    mean_density=99.0, inflow_ped=0, outflow_ped=0,
                    flow_ratio=0.0, timed_out=2,
                    wall_s=round(time.time() - t0, 3))


def _load_done():
    if not os.path.exists(SEED_CSV):
        return set()
    df = pd.read_csv(SEED_CSV)
    return set(zip(df.cell_id, df.qp.astype(int), df.qr.astype(int),
                   df.seed.astype(int)))


def _append(rows):
    new = not os.path.exists(SEED_CSV)
    with open(SEED_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=_FIELDS)
        if new:
            w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in _FIELDS})


def run_phase(tasks, n_procs, label):
    done = _load_done()
    todo = [t for t in tasks if (t[0], int(t[1]), int(t[2]), int(t[3])) not in done]
    print(f"[{label}] {len(todo)} tasks ({len(tasks)-len(todo)} done)", flush=True)
    if not todo:
        return
    t0 = time.time()
    n = 0
    with ProcessPoolExecutor(max_workers=n_procs) as ex:
        futs = [ex.submit(run_one, t) for t in todo]
        buf = []
        for fut in as_completed(futs):
            r = fut.result()
            buf.append(r)
            n += 1
            if len(buf) >= 200:
                _append(buf)
                buf = []
            if n % 200 == 0:
                print(f"  [{label}] {n}/{len(todo)} elapsed "
                      f"{(time.time()-t0)/60:.1f} min", flush=True)
        if buf:
            _append(buf)
    print(f"[{label}] finished in {(time.time()-t0)/60:.1f} min", flush=True)


def compute_base_pass(df, cell_id):
    g = df[(df.cell_id == cell_id) & (df.qr == 0)]
    if len(g) == 0:
        return False, np.nan, np.nan, np.nan, np.nan
    md = g.mean_density.mean()
    mfr = g.flow_ratio.mean()
    vbar = g.mean_speed.mean()
    inflow = g.inflow_ped.mean()
    base_pass = (md <= DFLOOR) and (OUTMIN <= mfr <= OUTMAX)
    return base_pass, md, mfr, vbar, inflow


def compute_qr_star(df, cell_id, vbar):
    g = df[(df.cell_id == cell_id) & (df.qr > 0)]
    qr_star = 0.0
    rows = []
    for qr in [q for q in ROBOT_FLOWS_ALL if q != 0]:
        sub = g[g.qr == qr]
        if len(sub) == 0:
            continue
        flags = [SIM_MOD.evaluate_constraints(m, vbar, DELTA_V, OUTMIN, OUTMAX,
                                              DFLOOR)
                 for m in sub.to_dict("records")]
        pass_frac = float(np.mean([f["pass"] for f in flags]))
        rows.append(dict(qr=qr, pass_frac=pass_frac,
                         mean_density=sub.mean_density.mean(),
                         mean_flow_ratio=sub.flow_ratio.mean()))
        if pass_frac >= CONF:
            qr_star = float(qr)
    return qr_star, rows


def main(n_procs=12, phase=None):
    cell_ids = list(_CELLS.keys())

    if phase in (None, "baseline"):
        tasks = [(c, _CELLS[c]["qp"], 0, s) for c in cell_ids
                 for s in range(N_SEEDS)]
        run_phase(tasks, n_procs, "baseline")

    df = pd.read_csv(SEED_CSV) if os.path.exists(SEED_CSV) else pd.DataFrame()

    # base_pass + integrity
    records = []
    sweep_cells = []
    for cid in cell_ids:
        bp, md, mfr, vbar, inflow = compute_base_pass(df, cid)
        qp = _CELLS[cid]["qp"]
        expected = float(qp) * 4.0
        if inflow <= 0:
            integrity = "simulation-invalid (inflow=0)"
        elif inflow < 0.8 * expected:
            integrity = f"spawn-degraded (inflow {inflow:.0f}/{expected:.0f})"
        else:
            integrity = "ok"
        records.append(dict(cell_id=cid, qp=qp, W_eff=_CELLS[cid]["W_eff"],
                            geometry_type=_CELLS[cid]["geometry_type"],
                            orig_W=_CELLS[cid]["orig_W"],
                            width_p10=_CELLS[cid]["width_p10"],
                            base_pass=int(bp), mean_density_base=md,
                            mean_flow_ratio_base=mfr, vbar=vbar,
                            mean_inflow_base=inflow, integrity=integrity))
        if bp and integrity == "ok":
            sweep_cells.append((cid, qp))
    summary = pd.DataFrame(records)
    summary.to_csv(os.path.join(RUNS, "v2_baseline_summary.csv"), index=False)
    print(f"\nbase_pass: {summary.base_pass.sum()}/{len(summary)} "
          f"recovered cells pass baseline", flush=True)
    print(summary[["cell_id", "qp", "W_eff", "base_pass", "mean_density_base",
                   "mean_flow_ratio_base", "integrity"]].to_string(index=False))

    if phase in (None, "sweep"):
        tasks = [(cid, qp, qr, s) for cid, qp in sweep_cells
                 for qr in ROBOT_FLOWS_ALL if qr != 0 for s in range(N_SEEDS)]
        run_phase(tasks, n_procs, "sweep")

    df = pd.read_csv(SEED_CSV)

    final = []
    detail_rows = []
    for r in summary.itertuples():
        bp, md, mfr, vbar, inflow = compute_base_pass(df, r.cell_id)
        if bp and r.integrity == "ok":
            qr_star, rows = compute_qr_star(df, r.cell_id, vbar)
            detail_rows += [dict(cell_id=r.cell_id, qp=r.qp, **d) for d in rows]
        elif bp and r.integrity != "ok":
            qr_star = float("nan")
        else:
            qr_star = 0.0
        final.append(dict(cell_id=r.cell_id, qp=r.qp, W_eff=r.W_eff,
                          geometry_type=r.geometry_type, base_pass=int(bp),
                          vbar=vbar, qr_star=qr_star, integrity=r.integrity))
    finaldf = pd.DataFrame(final)
    finaldf.to_csv(os.path.join(RUNS, "v2_reference_qr_star.csv"), index=False)
    if detail_rows:
        pd.DataFrame(detail_rows).to_csv(
            os.path.join(RUNS, "v2_sweep_detail.csv"), index=False)
    print("\n=== v2 reference qr_star ===", flush=True)
    print(finaldf.to_string(index=False), flush=True)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-procs", type=int, default=12)
    ap.add_argument("--phase", choices=["baseline", "sweep"], default=None)
    args = ap.parse_args()
    main(args.n_procs, args.phase)
