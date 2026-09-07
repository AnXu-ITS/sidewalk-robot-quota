# -*- coding: utf-8 -*-
"""Apply the v2 formula + guardrails to the 7 D2 cities (existing ground truth).

No new simulation: D2 qr* is already in data/final/full_reference_dataset.csv.
v2 differs from v1 by (a) clamping W>3.0 to 3.0 and (b) the segmented margin.
D2 cells are synthetic rectangles, so width_p10 == W (bottleneck = the single
corridor width); D2 "type C" == narrow (<1.6 m) and stays OOD.
"""
import os
import sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_REPO, "final_freeze", "src"))
import operational_quota as oq
from v2_quota import V2Quota

MARGIN_BINS = [(1.6, float("inf"), 0.00)]  # delta=0 (utilization-priority decision)
v2 = V2Quota(MARGIN_BINS)
m1 = oq.OperationalQuota()


def geom_of(t, s):
    return dict(type=t, sinuosity=float(s), max_turn_deg=0.0, cum_turn_deg=0.0)


def main():
    d2 = pd.read_csv(os.path.join(_REPO, "data", "final",
                                  "full_reference_dataset.csv"))
    rows = []
    for r in d2.itertuples():
        g = geom_of(r.type, r.sinuosity)
        vbar = float(r.vbar) if not pd.isna(r.vbar) else None
        v1 = m1.quota(float(r.W), float(r.qp), int(r.base_pass), g, vbar)
        v2q = v2.quota(float(r.W), float(r.qp), int(r.base_pass), g, vbar,
                      geometry_type=r.type, width_p10=float(r.W))
        rows.append(dict(city=r.city, W=float(r.W), qp=float(r.qp),
                         type=r.type, base_pass=int(r.base_pass),
                         ref=float(r.qr_star), v1=v1, v2=v2q))
    df = pd.DataFrame(rows)
    df["in_domain_v1"] = df.v1.notna()
    df["in_domain_v2"] = df.v2.notna()
    df["recovered"] = (~df.in_domain_v1) & df.in_domain_v2

    def summ(d, col):
        e = d[col] - d.ref
        pos = d[d.ref > 0]
        u = pos[col] / pos.ref
        return dict(n=len(d), mae=float(np.mean(np.abs(e))),
                    overpred=float(np.mean(e > 0)),
                    util_med=float(np.median(u)) if len(pos) else np.nan)

    print("=== v2 applied to the 7 D2 cities (existing qr*) ===\n")
    cities = ["amsterdam", "melbourne", "newtaipei", "nyc", "taipei",
              "seattle", "taoyuan"]
    for c in cities:
        sub = df[df.city == c]
        d1 = sub[sub.in_domain_v1]
        d2 = sub[sub.in_domain_v2]
        s1 = summ(d1, "v1")
        s2 = summ(d2, "v2")
        n_rec = int(sub.recovered.sum())
        print(f"{c:10s}  v1(n={s1['n']:3d}) MAE={s1['mae']:.2f} "
              f"over={s1['overpred']:.2f} util_med={s1['util_med']:.2f}  |  "
              f"v2(n={s2['n']:3d}, +{n_rec} recov) MAE={s2['mae']:.2f} "
              f"over={s2['overpred']:.2f} util_med={s2['util_med']:.2f}")

    all1 = df[df.in_domain_v1]
    all2 = df[df.in_domain_v2]
    s1 = summ(all1, "v1")
    s2 = summ(all2, "v2")
    print(f"\nALL        v1(n={s1['n']}) MAE={s1['mae']:.2f} over={s1['overpred']:.2f} "
          f"util_med={s1['util_med']:.2f}")
    print(f"           v2(n={s2['n']}) MAE={s2['mae']:.2f} over={s2['overpred']:.2f} "
          f"util_med={s2['util_med']:.2f}")

    # recovered (W>3.0) cells detail
    rec = df[df.recovered]
    print(f"\n=== recovered (W>3.0 -> clamp 3.0) cells: n={len(rec)} ===")
    if len(rec):
        e = rec.v2 - rec.ref
        pos = rec[rec.ref > 0]
        u = pos.v2 / pos.ref
        print(f"  v2 vs qr*: MAE={np.mean(np.abs(e)):.2f} "
              f"overpred={np.mean(e>0):.2f} util_med={np.median(u):.2f}")
        over = rec[rec.v2 > rec.ref]
        if len(over):
            print(f"  overprediction cells: {len(over)} (max +"
                  f"{int((over.v2-over.ref).max())})")
        print(rec[["city", "W", "qp", "type", "ref", "v2"]].round(2)
              .to_string(index=False))

    df.to_csv(os.path.join(_HERE, "v2_d2_7cities.csv"), index=False)
    print("\nwrote algorithm_v2/v2_d2_7cities.csv")


if __name__ == "__main__":
    main()
