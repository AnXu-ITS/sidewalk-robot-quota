# -*- coding: utf-8 -*-
"""
check_multicity.py
==================
Provisional progress viewer for the multi-city ground-truth run
(outputs/p1_multicity/).  Reads whatever baseline + per-q_r-level sweep CSVs
already exist and reports:

  * baseline: combo count + Case-1 (pedestrian-only over-capacity) count;
  * sweep: which q_r levels are complete, rows each;
  * provisional q_r* for combos whose sweep is COMPLETE (i.e. every q_r level
    up to and including their first failure has been written).

Safe to run at any time while `p1_multicity.py` is still going; it never writes.
"""
import glob
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import PATHS, CONSTRAINTS, ROBOT_FLOWS_ALL  # noqa: E402

OUT = os.path.join(PATHS["root"], "outputs", "p1_multicity")
DFLOOR = CONSTRAINTS["density_floor"]
DELTA_V = CONSTRAINTS["delta_v"]
OUTMIN = CONSTRAINTS["outflow_ratio_min"]
OUTMAX = CONSTRAINTS["outflow_ratio_max"]
QR_LEVELS = sorted(q for q in ROBOT_FLOWS_ALL if q != 0)


def combo_passes(sub, vbar):
    if len(sub) == 0 or vbar <= 0:
        return False
    mean_Rv = float(sub["mean_speed"].mean() / vbar)
    fr = float(sub["flow_ratio"].mean())
    dens = float(sub["mean_density"].mean())
    return mean_Rv >= (1.0 - DELTA_V) and OUTMIN <= fr <= OUTMAX and dens <= DFLOOR


def main():
    base_csv = os.path.join(OUT, "multicity_baseline.csv")
    if not os.path.exists(base_csv):
        print("no baseline yet (Phase A still running)")
        return

    base = pd.read_csv(base_csv)
    vbar = {t: float(g["mean_speed"].mean()) for t, g in base.groupby("tag")}
    bad = {t for t, g in base.groupby("tag")
           if g["mean_density"].mean() > DFLOOR
           or g["flow_ratio"].mean() < 0.85
           or g["flow_ratio"].mean() > OUTMAX}
    print(f"baseline: {len(base)} rows, {len(vbar)} combos, "
          f"{len(bad)} Case-1 (over-capacity -> q_r*=0)")

    # load whatever sweep levels exist
    parts = {}
    for qr in QR_LEVELS:
        p = os.path.join(OUT, f"multicity_sweep_{qr}.csv")
        if os.path.exists(p) and os.path.getsize(p) > 0:
            parts[qr] = pd.read_csv(p)
    done_qr = sorted(parts)
    print(f"sweep levels complete: {done_qr} "
          f"({'..'.join(map(str, [done_qr[0], done_qr[-1]])) if done_qr else 'none'})")

    if not parts:
        return

    all_tags = set(vbar) | set().union(*[set(p["tag"]) for p in parts.values()])
    rows = []
    for tag in sorted(all_tags):
        # provisional qr*: highest qr that still passes, over COMPLETE levels;
        # a combo is "final" only if its first failure is among done levels.
        qr_star = 0.0
        final = False
        for qr in done_qr:
            if qr not in parts or tag not in set(parts[qr]["tag"]):
                continue
            sub = parts[qr][parts[qr]["tag"] == tag]
            if combo_passes(sub, vbar.get(tag, 0.0)):
                qr_star = max(qr_star, float(qr))
            else:
                final = True   # saw a failure -> sweep complete for this combo
                break
        rows.append((tag, qr_star, final))

    df = pd.DataFrame(rows, columns=["tag", "qr_star_prov", "final"])
    df = df[df["final"]]  # only combos whose sweep already finished
    print(f"\nprovisional q_r* for {len(df)}/200 combos with complete sweeps:")
    if len(df):
        print(df.sort_values("qr_star_prov", ascending=False)
              .to_string(index=False))


if __name__ == "__main__":
    main()
