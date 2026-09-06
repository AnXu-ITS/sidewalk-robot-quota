# -*- coding: utf-8 -*-
"""
rescore_seedwise.py  (P2 item 1 / plan-problem #4)
===================================================
Re-derive the reference robot quota q_r* under TWO pass criteria from the
EXISTING sweep CSVs (no re-simulation):

  1. mean-based  (current): a (tag, qr) level passes if the SEED-AVERAGED
     service metrics satisfy the pedestrian-first constraints.
  2. seedwise    (required by the plan): a (tag, qr) level passes only if
     Pr(each seed satisfies the constraint) >= conf_level = 0.95, i.e. at
     least 29/30 seeds individually pass.

Both use the same per-seed constraint:
    R_v = mean_speed / vbar >= 1 - delta_v   (0.90)
    0.90 <= flow_ratio <= 1.20
    mean_density <= 1.20

Outputs (outputs/p1_multicity/):
  rescore_seedwise.csv   per-combo mean_qr_star vs seedwise_qr_star
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (CONSTRAINTS, PATHS)  # noqa: E402

OUT_DIR = os.path.join(PATHS["root"], "outputs", "p1_multicity")
BASE_CSV = os.path.join(OUT_DIR, "multicity_baseline.csv")
SWEEP_CSV = os.path.join(OUT_DIR, "multicity_sweep.csv")

DELTA_V = CONSTRAINTS["delta_v"]
OUTMIN = CONSTRAINTS["outflow_ratio_min"]
OUTMAX = CONSTRAINTS["outflow_ratio_max"]
DFLOOR = CONSTRAINTS["density_floor"]
CONF = CONSTRAINTS["conf_level"]


def seed_ok(rv, fr, dens):
    return (rv >= (1.0 - DELTA_V)) & (fr >= OUTMIN) & (fr <= OUTMAX) \
        & (dens <= DFLOOR)


def main():
    base = pd.read_csv(BASE_CSV)
    sweep = pd.read_csv(SWEEP_CSV)

    # vbar per tag = mean baseline speed (same as fit_multicity)
    vbar = base.groupby("tag", sort=False)["mean_speed"].mean()

    rows = []
    for tag, g in sweep.groupby("tag", sort=True):
        vb = float(vbar.get(tag, 0.0))
        mean_qr = 0.0
        seed_qr = 0.0
        # collect per-level diagnostics
        for qr, sub in g.groupby("qr", sort=True):
            n = len(sub)
            rv = sub["mean_speed"].to_numpy(float) / vb if vb > 0 else \
                np.zeros(n)
            fr = sub["flow_ratio"].to_numpy(float)
            dens = sub["mean_density"].to_numpy(float)
            # mean-based
            if seed_ok(float(rv.mean()), float(fr.mean()), float(dens.mean())):
                mean_qr = max(mean_qr, float(qr))
            # seedwise
            npass = int(seed_ok(rv, fr, dens).sum())
            if npass / n >= CONF:
                seed_qr = max(seed_qr, float(qr))
        rows.append(dict(tag=tag, mean_qr_star=mean_qr, seedwise_qr_star=seed_qr,
                         delta=seed_qr - mean_qr))

    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(OUT_DIR, "rescore_seedwise.csv"), index=False)

    n = len(res)
    changed = int((res["delta"] != 0).sum())
    lower = int((res["delta"] < 0).sum())
    higher = int((res["delta"] > 0).sum())
    print(f"combos swept: {n}")
    print(f"mean_qr_star sum = {res['mean_qr_star'].sum():.0f}, "
          f"seedwise_qr_star sum = {res['seedwise_qr_star'].sum():.0f}")
    print(f"changed combos: {changed} ({lower} lower, {higher} higher)")
    print("\ndelta distribution (seedwise - mean):")
    print(res["delta"].value_counts().sort_index().to_string())
    print("\nlargest reductions:")
    print(res[res["delta"] < 0].sort_values("delta").head(15).to_string(index=False))
    print("\nlargest increases:")
    print(res[res["delta"] > 0].sort_values("delta", ascending=False).head(10)
          .to_string(index=False))

    # non-zero quotas under each criterion
    nz_mean = int((res["mean_qr_star"] > 0).sum())
    nz_seed = int((res["seedwise_qr_star"] > 0).sum())
    print(f"\nnonzero-quota combos: mean={nz_mean}, seedwise={nz_seed}")

    return res


if __name__ == "__main__":
    main()
