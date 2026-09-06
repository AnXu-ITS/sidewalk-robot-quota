# -*- coding: utf-8 -*-
"""
close_loop_seedwise.py
======================
Re-simulate the NEW seedwise-fit deployed levels (A-round / A-floor) for the
held-out cells whose level was never simulated (listed as `scored=False` in
svr_seedwise_table.csv), then merge the per-seed pass fractions back into that
table and print the updated per-variant SVR.

The full per-seed pipeline (rescore_seedwise_full.py) picks up the produced
CSV (outputs/validation/closed_loop_seedwise_new.csv) as an extra data source,
so re-running it afterwards reproduces all final artifacts.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import PATHS, SIM, N_SEEDS_VALIDATION  # noqa: E402
from run_batch import run_batch  # noqa: E402
from rescore_seedwise_full import sweep_pass_frac, CONF  # noqa: E402

L = SIM["L"]
TABLE = os.path.join(PATHS["validation"], "svr_seedwise_table.csv")
OUT_CSV = os.path.join(PATHS["validation"], "closed_loop_seedwise_new.csv")
TARGETS = {"new A-floor (seed-fit)", "new A-round (seed-fit)"}
TOL = 1e-9


def main(n_procs=None):
    tab = pd.read_csv(TABLE)
    need = tab[(~tab["scored"]) & tab["variant"].isin(TARGETS)]
    cells = need[["W", "qp", "level"]].drop_duplicates()
    print(f"re-simulating {len(cells)} (cell, level) combos, "
          f"{len(cells) * N_SEEDS_VALIDATION} scenarios")

    scen = []
    for _, r in cells.iterrows():
        for s in range(N_SEEDS_VALIDATION):
            scen.append([float(r["W"]), L, float(r["qp"]), float(r["level"]),
                         s, None, None, None])
    df = run_batch(scen, n_procs=n_procs, out_csv=OUT_CSV,
                   label="seedwise closed-loop")

    # ---- merge per-seed scores ------------------------------------------
    truth = pd.read_csv(os.path.join(PATHS["validation"],
                                     "test_truth_seedwise.csv"))
    vbar = dict(zip(zip(truth["W"], truth["qp"]), truth["vbar"]))

    n_filled = 0
    for idx, row in tab.iterrows():
        if row["scored"] or row["variant"] not in TARGETS:
            continue
        sub = df[(df["W"] == row["W"]) & (df["qp"] == row["qp"])
                 & np.isclose(df["qr"].to_numpy(float), row["level"],
                              atol=TOL)]
        if len(sub):
            frac, _ = sweep_pass_frac(sub, vbar[(row["W"], row["qp"])])
            tab.at[idx, "pass_frac"] = frac
            tab.at[idx, "violated"] = bool(frac < CONF)
            tab.at[idx, "scored"] = True
            n_filled += 1
    tab.to_csv(TABLE, index=False)
    print(f"merged {n_filled} rows ({len(cells) * 1} combos)")

    print("\n=== per-seed closed-loop SVR (after gap closure) ===")
    for vname, g in tab[tab["scored"]].groupby("variant", sort=False):
        viol = int(g["violated"].sum())
        svr = viol / len(g)
        print(f"{vname:26s} SVR={svr:.4f}  ({viol}/{len(g)} scored)")
    for vname, g in tab[~tab["scored"]].groupby("variant", sort=False):
        if len(g):
            print(f"{vname:26s} still unscored: {len(g)}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-procs", type=int, default=None)
    args = ap.parse_args()
    main(n_procs=args.n_procs)
