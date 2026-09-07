# -*- coding: utf-8 -*-
"""Section 5 — formal 30-seed SUMO-JuPedSim sweep on real HK footway polygons.

Frozen protocol (D2 ground_truth.py semantics, adapted to real polygons):
  Phase A  baseline qr=0, 30 seeds per in-domain cell
  Phase B  base_pass = mean-based: mean_density<=1.20 AND 0.90<=mean_flow_ratio<=1.20
  Phase C  robot sweep qr in [1,2,3,4,5,6,8,10,12,15,18,20] x 30 seeds for
           base_pass=1 cells; qr_star = max qr with per-seed pass_frac >= 0.95
           (evaluate_constraints per seed, >=29/30).

OOD cells abstain (frozen runtime returns None); NOT simulated here.

Checkpoint/resume: raw seed-level rows are appended to runs/formal/seed_results.csv;
completed (cell_id, qp, qr, seed) keys are skipped on re-run. Scenario dirs are
removed on success and kept on failure/timeout for diagnosis.
"""
import csv
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
_PIPE = os.path.join(_REPO, "pipeline", "sim", "scripts")
sys.path.insert(0, _PIPE)
sys.path.insert(0, _HERE)

from config import CONSTRAINTS, SIM  # noqa: E402
import simulator as SIM_MOD  # noqa: E402
import hk_smoke_runner as HK  # noqa: E402

RUNS = os.path.join(_HERE, "runs", "formal")
SCEN = os.path.join(_HERE, "scenarios")
os.makedirs(RUNS, exist_ok=True)
os.makedirs(SCEN, exist_ok=True)

ROBOT_FLOWS_ALL = [0, 1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 18, 20]
N_SEEDS = 30
CONF = 0.95
DFLOOR = CONSTRAINTS["density_floor"]
OUTMIN = CONSTRAINTS["outflow_ratio_min"]
OUTMAX = CONSTRAINTS["outflow_ratio_max"]
DELTA_V = CONSTRAINTS["delta_v"]

SEED_CSV = os.path.join(RUNS, "seed_results.csv")
_FIELDS = ["cell_id", "qp", "qr", "seed", "W", "L", "mean_speed", "speed_count",
           "mean_density", "inflow_ped", "outflow_ped", "flow_ratio",
           "timed_out", "wall_s"]


def _load_geometry():
    return json.load(open(os.path.join(_HERE, "sites",
                                       "hk_formal_local_geometry.json"),
                          encoding="utf-8"))


_GEO = _load_geometry()

# cell W lookup (module-level so spawned workers on Windows re-initialise it)
_frz_df = pd.read_csv(os.path.join(_HERE, "sites",
                                   "HONG_KONG_FORMAL_SAMPLE_FREEZE.csv"))
_CELLW = {r.cell_id: float(r.W) for r in _frz_df.itertuples()}


def run_one(task):
    """task = (cell_id, qp, qr, seed). Returns metrics dict."""
    cell_id, qp, qr, seed = task
    g = _GEO[cell_id]
    L = g["L"]
    cl = [tuple(p) for p in g["centerline_local"]]
    poly = g["walkable_polygon_local"]["coordinates"]
    W = _CELLW[cell_id]
    scen_dir = os.path.join(SCEN, f"{cell_id}_qp{int(qp)}_qr{int(qr)}_s{seed}")
    os.makedirs(scen_dir, exist_ok=True)
    t0 = time.time()
    try:
        cfg = HK.build_scenario(scen_dir, W, L, cl, poly, qp, qr, seed)
        log = os.path.join(scen_dir, "sumo.log")
        err = os.path.join(scen_dir, "sumo.err")
        cmd = [HK.SUMO_BIN, "-c", cfg, "--no-warnings", "true",
               "--error-log", err, "--no-duration-log", "true",
               "--ignore-route-errors", "true",
               "--person-device.fcd.probability", "1.0",
               "--person-device.fcd.period", "1.0"]
        with open(log, "w", encoding="utf-8") as lf:
            subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT,
                           timeout=SIM.get("timeout_sec", 300.0))
        m = SIM_MOD._parse(scen_dir, W, SIM, cl)
        metrics = dict(cell_id=cell_id, qp=float(qp), qr=float(qr), seed=int(seed),
                       W=float(W), L=float(L), mean_speed=float(m[0]),
                       speed_count=int(m[1]), mean_density=float(m[2]),
                       inflow_ped=int(m[3]), outflow_ped=int(m[4]),
                       flow_ratio=float(m[5]), timed_out=0,
                       wall_s=round(time.time() - t0, 3))
        shutil.rmtree(scen_dir, ignore_errors=True)
        return metrics
    except subprocess.TimeoutExpired:
        shutil.rmtree(scen_dir, ignore_errors=True)
        return dict(cell_id=cell_id, qp=float(qp), qr=float(qr), seed=int(seed),
                    W=float(W), L=float(L), mean_speed=0.0, speed_count=0,
                    mean_density=99.0, inflow_ped=0, outflow_ped=0,
                    flow_ratio=0.0, timed_out=1,
                    wall_s=round(time.time() - t0, 3))
    except Exception as e:  # keep scenario dir for diagnosis, conservative FAIL
        with open(os.path.join(scen_dir, "FAIL.txt"), "w", encoding="utf-8") as f:
            f.write(str(e))
        return dict(cell_id=cell_id, qp=float(qp), qr=float(qr), seed=int(seed),
                    W=float(W), L=float(L), mean_speed=0.0, speed_count=0,
                    mean_density=99.0, inflow_ped=0, outflow_ped=0,
                    flow_ratio=0.0, timed_out=2,
                    wall_s=round(time.time() - t0, 3))


def _load_done():
    if not os.path.exists(SEED_CSV):
        return set()
    df = pd.read_csv(SEED_CSV)
    return set(zip(df.cell_id, df.qp.astype(int), df.qr.astype(int), df.seed.astype(int)))


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
    print(f"[{label}] {len(todo)} tasks to run "
          f"({len(tasks) - len(todo)} already done)")
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
                el = time.time() - t0
                print(f"  [{label}] {n}/{len(todo)} done, "
                      f"elapsed {el/60:.1f} min")
        if buf:
            _append(buf)
    print(f"[{label}] finished in {(time.time()-t0)/60:.1f} min")


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
                         mean_flow_ratio=sub.flow_ratio.mean(),
                         mean_speed=sub.mean_speed.mean()))
        if pass_frac >= CONF:
            qr_star = float(qr)
    return qr_star, rows


def main(n_procs=12, phase=None):
    mat = pd.read_csv(os.path.join(_HERE, "sites", "HONG_KONG_EXPERIMENT_MATRIX.csv"))
    indom = mat[mat.status == "in-domain (full protocol)"]

    # Phase A: baselines
    if phase in (None, "baseline"):
        tasks = [(r.cell_id, int(r.qp), 0, s)
                 for r in indom.itertuples() for s in range(N_SEEDS)]
        run_phase(tasks, n_procs, "baseline")

    df = pd.read_csv(SEED_CSV) if os.path.exists(SEED_CSV) else pd.DataFrame()

    # Phase B: base_pass + decide sweep cells
    records = []
    sweep_cells = []
    for r in indom.itertuples():
        bp, md, mfr, vbar, inflow = compute_base_pass(df, r.cell_id)
        expected = float(r.qp) * 4.0  # qp ped/min x 4 min measure window
        if inflow <= 0:
            integrity = "simulation-invalid (inflow=0)"
        elif inflow < 0.8 * expected:
            integrity = f"spawn-degraded (inflow {inflow:.0f}/{expected:.0f})"
        else:
            integrity = "ok"
        records.append(dict(cell_id=r.cell_id, qp=int(r.qp), W=r.W, vbar=vbar,
                            base_pass=int(bp), mean_density_base=md,
                            mean_flow_ratio_base=mfr, mean_inflow_base=inflow,
                            expected_inflow=expected, integrity=integrity))
        if bp and integrity == "ok":
            sweep_cells.append((r.cell_id, int(r.qp)))
    summary = pd.DataFrame(records)
    summary.to_csv(os.path.join(RUNS, "baseline_summary.csv"), index=False)
    print(f"\nbase_pass: {summary.base_pass.sum()}/{len(summary)} in-domain cells "
          f"pass baseline")
    print(summary[summary.base_pass == 0][["cell_id", "qp", "W",
                                           "mean_density_base",
                                           "mean_flow_ratio_base"]].to_string(index=False))
    print("\nspawn-integrity (excluded from sweep if not 'ok'):")
    print(summary[summary.integrity != "ok"][["cell_id", "qp", "mean_inflow_base",
                                              "expected_inflow",
                                              "integrity"]].to_string(index=False))

    # Phase C: sweeps
    if phase in (None, "sweep"):
        tasks = [(cid, qp, qr, s) for cid, qp in sweep_cells
                 for qr in ROBOT_FLOWS_ALL if qr != 0 for s in range(N_SEEDS)]
        run_phase(tasks, n_procs, "sweep")

    df = pd.read_csv(SEED_CSV)

    # aggregate qr_star (per-seed >=29/30) + detail
    final = []
    detail_rows = []
    integrity_map = {r.cell_id: r.integrity for r in summary.itertuples()}
    for r in indom.itertuples():
        bp, md, mfr, vbar, inflow = compute_base_pass(df, r.cell_id)
        integrity = integrity_map.get(r.cell_id, "ok")
        if bp and integrity == "ok":
            qr_star, rows = compute_qr_star(df, r.cell_id, vbar)
            detail_rows += [dict(cell_id=r.cell_id, qp=int(r.qp), **d) for d in rows]
        elif bp and integrity != "ok":
            qr_star, rows = float("nan"), []  # spurious pass -> invalid, not 0
        else:
            qr_star, rows = 0.0, []
        final.append(dict(cell_id=r.cell_id, qp=int(r.qp), W=r.W,
                          base_pass=int(bp), vbar=vbar, qr_star=qr_star,
                          integrity=integrity))
    finaldf = pd.DataFrame(final)
    finaldf.to_csv(os.path.join(RUNS, "hk_reference_qr_star.csv"), index=False)
    if detail_rows:
        pd.DataFrame(detail_rows).to_csv(
            os.path.join(RUNS, "hk_sweep_detail.csv"), index=False)
    print("\n=== reference qr_star (ground truth) ===")
    print(finaldf.to_string(index=False))
    print("\nwrote baseline_summary.csv, hk_reference_qr_star.csv, "
          "hk_sweep_detail.csv, seed_results.csv")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-procs", type=int, default=12)
    ap.add_argument("--phase", choices=["baseline", "sweep"], default=None)
    args = ap.parse_args()
    main(args.n_procs, args.phase)
