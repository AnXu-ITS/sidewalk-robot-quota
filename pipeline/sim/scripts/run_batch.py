"""
run_batch.py
============
Parallel batch runner for the mixed pedestrian--robot flow simulator.

Windows `multiprocessing` (spawn) relies on named-pipe handle duplication that
is unavailable in this environment, so this runner instead launches N
subprocess workers (scripts/worker.py) with stdout/stderr redirected to files
and each writing its own results CSV.  Results are concatenated afterwards.

Each scenario is a list:

    [W, L, qp, qr, seed, v_ref_override, radius_override, bidirectional_split]

where the override values may be null (use config defaults).
"""

import glob
import json
import os
import subprocess
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import PATHS  # noqa: E402

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable


def _serialize(scenarios):
    return [[None if v is None else v for v in s] for s in scenarios]


def run_batch(scenarios, n_procs=None, out_csv=None, label="batch"):
    """Run `scenarios` across `n_procs` subprocess workers."""
    n_procs = n_procs or os.cpu_count()
    total = len(scenarios)
    if total == 0:
        df = pd.DataFrame()
        if out_csv:
            os.makedirs(os.path.dirname(out_csv), exist_ok=True)
            df.to_csv(out_csv, index=False)
        return df
    n_procs = min(n_procs, total)
    print(f"[{label}] {total} scenarios on {n_procs} workers", flush=True)

    tmp_dir = os.path.join(PATHS["root"], "outputs", "_batch_tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    # remove stale part files from a previous run with the same label
    for f in glob.glob(os.path.join(tmp_dir, f"{label}_*")):
        try:
            os.remove(f)
        except OSError:
            pass
    scen_file = os.path.join(tmp_dir, f"{label}_scenarios.json")
    with open(scen_file, "w", encoding="utf-8") as f:
        json.dump(_serialize(scenarios), f)

    chunk = int(np.ceil(total / n_procs))
    procs = []
    part_files = []
    log_files = []
    for i in range(n_procs):
        part_csv = os.path.join(tmp_dir, f"{label}_{i}.csv")
        log_path = os.path.join(tmp_dir, f"{label}_{i}.log")
        logf = open(log_path, "w", encoding="utf-8")
        cmd = [PYTHON, os.path.join(SCRIPT_DIR, "worker.py"),
               scen_file, str(i), str(n_procs), part_csv]
        p = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT)
        procs.append(p)
        part_files.append(part_csv)
        log_files.append((log_path, logf))

    t0 = time.time()
    # poll until all workers finish (report progress from produced CSVs)
    n_workers = len(procs)
    done = [False] * n_workers
    while not all(done):
        for k, p in enumerate(procs):
            if not done[k] and p.poll() is not None:
                done[k] = True
        produced = sum(1 for f in part_files if os.path.exists(f))
        el = time.time() - t0
        print(f"  [{label}] {produced}/{n_workers} workers done "
              f"({el:.0f}s)", flush=True)
        if not all(done):
            time.sleep(15)

    # close log handles and check for failures
    for log_path, logf in log_files:
        logf.close()

    for k, p in enumerate(procs):
        if p.returncode != 0:
            print(f"  ERROR: worker {k} failed (rc={p.returncode}); log:",
                  flush=True)
            with open(log_files[k][0], encoding="utf-8", errors="replace") as f:
                print(f.read(), flush=True)
            raise RuntimeError(f"worker {k} failed")

    dfs = [pd.read_csv(f) for f in part_files
           if os.path.exists(f) and os.path.getsize(f) > 0]
    df = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

    if out_csv:
        os.makedirs(os.path.dirname(out_csv), exist_ok=True)
        df.to_csv(out_csv, index=False)
        print(f"[{label}] wrote {len(df)} rows -> {out_csv}", flush=True)

    print(f"[{label}] finished in {(time.time()-t0)/60:.1f} min", flush=True)
    return df


if __name__ == "__main__":
    scen = [[2.4, 50.0, 40.0, 5.0, 0, None, None, None],
            [2.4, 50.0, 40.0, 5.0, 1, None, None, None]]
    df = run_batch(scen, n_procs=2, label="selftest")
    print(df.to_string())
