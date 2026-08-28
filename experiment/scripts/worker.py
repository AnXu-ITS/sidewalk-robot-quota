"""
worker.py
=========
Single subprocess worker: runs a strided slice of scenarios (round-robin
assignment for load balance) through the simulator and writes raw per-seed
metrics to a CSV.

Invoked by run_batch.py (which avoids Python multiprocessing because its
Windows spawn path relies on named pipes that are unavailable here).

Usage:
    python worker.py <scenarios.json> <worker_index> <n_workers> <out.csv>
"""

import json
import os
import sys

import numpy as np
import pandas as pd

# single-thread BLAS inside each worker to avoid oversubscription
for _k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_k] = "1"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import PED, WALL, ROBOT, SIM  # noqa: E402
from simulator import run_scenario  # noqa: E402


def main():
    scenarios_file = sys.argv[1]
    widx = int(sys.argv[2])
    nw = int(sys.argv[3])
    out_csv = sys.argv[4]

    with open(scenarios_file, "r", encoding="utf-8") as f:
        scen = json.load(f)

    results = []
    for s in scen[widx::nw]:
        W, L, qp, qr, seed, vref, rad, split = s
        m = run_scenario(W, L, qp, qr, seed, PED, WALL, ROBOT, SIM,
                         bidirectional_split=split,
                         v_ref_override=vref,
                         radius_override=rad)
        results.append(m)

    df = pd.DataFrame(results)
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    df.to_csv(out_csv, index=False)
    print(f"worker {widx} wrote {len(df)} rows -> {out_csv}", flush=True)


if __name__ == "__main__":
    main()
