# -*- coding: utf-8 -*-
"""Assemble the v2 comparison report (run after v2_sweep.py finishes)."""
import os
import sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_HK = os.path.abspath(os.path.join(_HERE, ".."))
_REPO = os.path.abspath(os.path.join(_HK, "..", ".."))

RUNS = os.path.join(_HERE, "runs")
V1_REF = os.path.join(_HK, "runs", "formal", "hk_reference_qr_star.csv")
V2_QUOTAS = os.path.join(_HERE, "v2_hk_quotas.csv")
V2_REF = os.path.join(RUNS, "v2_reference_qr_star.csv")


def summ(d, ecol):
    e = d[ecol]
    pos = d[d.ref > 0]
    u = pos.v2 / pos.ref if ecol == "e2" else pos.v1 / pos.ref
    return dict(n=len(d),
                mae=float(np.mean(np.abs(e))),
                rmse=float(np.sqrt(np.mean(e ** 2))),
                overpred=float(np.mean(e > 0)),
                mean_err=float(np.mean(e)),
                util_med=float(np.median(u)) if len(pos) else np.nan,
                util_mean=float(np.mean(u)) if len(pos) else np.nan)


def main():
    q = pd.read_csv(V2_QUOTAS)

    # 13 valid cells (frozen v1 ground truth)
    v1ref = pd.read_csv(V1_REF)
    valid = q[(q.ref.notna()) & (~q.spawn_excluded)].copy()

    # 8 recovered cells (v2 sweep ground truth). HK-ST-32 is B-wide but
    # sinuosity 1.0635 > 1.05, so the unchanged type-B sinuosity gate keeps it
    # OOD — excluded here.
    RECOVERED = {"HK-ST-07", "HK-ST-14", "HK-ST-17", "HK-ST-20", "HK-ST-23",
                 "HK-ST-26", "HK-ST-29", "HK-ST-31"}
    if os.path.exists(V2_REF):
        v2ref = pd.read_csv(V2_REF)
        recov = q[q.cell_id.isin(RECOVERED)].copy()
        recov = recov.drop(columns=["ref", "integrity"], errors="ignore")
        recov = recov.merge(v2ref[["cell_id", "qr_star", "integrity"]],
                            on="cell_id", how="left")
        recov = recov.rename(columns={"qr_star": "ref"})
    else:
        recov = pd.DataFrame()

    print("=== v2 report ===")
    print("\n[1] 13 valid cells — v1 vs v2")
    valid["e1"] = valid.v1 - valid.ref
    valid["e2"] = valid.v2 - valid.ref
    s1 = summ(valid, "e1"); s2 = summ(valid, "e2")
    print(f"  v1: MAE={s1['mae']:.2f} RMSE={s1['rmse']:.2f} overpred={s1['overpred']:.3f} "
          f"util_med={s1['util_med']:.3f}")
    print(f"  v2: MAE={s2['mae']:.2f} RMSE={s2['rmse']:.2f} overpred={s2['overpred']:.3f} "
          f"util_med={s2['util_med']:.3f}")

    if len(recov):
        recov["e2"] = recov.v2 - recov.ref
        sr = summ(recov, "e2")
        print("\n[2] 8 recovered cells — v2 quota vs qr* (ground truth)")
        show = recov[["cell_id", "geometry_type", "width_p10", "qp", "v2", "ref",
                      "integrity"]].copy()
        print(show.to_string(index=False))
        print(f"\n  v2: MAE={sr['mae']:.2f} RMSE={sr['rmse']:.2f} "
              f"overpred={sr['overpred']:.3f} util_med={sr['util_med']:.3f}")
        over = recov[recov.e2 > 0]
        if len(over):
            print("  OVERPREDICTION cells (v2 > qr*, unsafe):")
            print(over[["cell_id", "v2", "ref"]].to_string(index=False))

        # combined 22 cells
        both = pd.concat([valid[["cell_id", "ref", "v2"]],
                          recov[["cell_id", "ref", "v2"]]], ignore_index=True)
        both["e2"] = both.v2 - both.ref
        sb = summ(both, "e2")
        print("\n[3] combined 21 cells (13 valid + 8 recovered) — v2")
        print(f"  MAE={sb['mae']:.2f} RMSE={sb['rmse']:.2f} overpred={sb['overpred']:.3f} "
              f"util_med={sb['util_med']:.3f} util_mean={sb['util_mean']:.3f}")

        out = pd.concat([valid[["cell_id", "ref", "v1", "v2"]],
                         recov[["cell_id", "ref", "v2"]]], ignore_index=True)
        out.to_csv(os.path.join(_HERE, "v2_full_comparison.csv"), index=False)
        print("\nwrote algorithm_v2/v2_full_comparison.csv")


if __name__ == "__main__":
    main()
