# -*- coding: utf-8 -*-
"""
base_pass_monotonicity.py  (offline, no SUMO)

Tests whether baseline feasibility can be represented as a monotonic
pedestrian-flow threshold per sidewalk (pass pattern 1,1,...,1,0,0,...,0).

Input: a reference CSV with one row per (cell, q_p) and columns
       cell_id, city, W, qp, qr_star (optionally type, L, x, base_pass).
       * If a `base_pass` column is present, it is used directly.
       * Otherwise a PROXY is derived from qr_star:
             qr_star > 0  => base_pass = 1   (a positive quota requires a
                                               passing pedestrian-only baseline)
             qr_star = 0  => base_pass UNKNOWN (could be 0 OR 1)

Because qr_star=0 does not identify base_pass, two things are reported
separately and honestly:
  (a) qr_star monotonicity (non-increasing in q_p)  -- computable, related.
  (b) POTENTIAL base_pass reversals = cells with qr_star(low)=0 AND
      qr_star(high)>0, which are the ONLY candidates for a true base_pass
      non-monotonicity under the proxy.

No SUMO, no re-fitting.
"""
import argparse
import os
from collections import defaultdict

import pandas as pd


def bp(r):
    """Direct base_pass if present, else proxy (1 or None/unknown)."""
    if "base_pass" in r and pd.notna(r.get("base_pass")):
        return int(r["base_pass"]), "direct"
    qr = r.get("qr_star")
    if pd.isna(qr):
        return None, "unknown"
    if float(qr) > 0:
        return 1, "proxy(qr_star>0=>1)"
    return None, "proxy(qr_star=0=>unknown)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--out-dir", default=".")
    args = ap.parse_args()

    df = pd.read_csv(args.input)
    os.makedirs(args.out_dir, exist_ok=True)

    # ---- per-(cell, qp) ledger -------------------------------------------
    rows = []
    for _, r in df.iterrows():
        v, src = bp(r)
        rows.append(dict(
            cell_id=r["cell_id"], city=r.get("city"),
            W=r.get("W"), L=r.get("L"), type=r.get("type"),
            qp=r["qp"], x=r.get("x"), qr_star=r.get("qr_star"),
            base_pass=v, base_pass_source=src))
    ledger = pd.DataFrame(rows)
    ledger.to_csv(os.path.join(args.out_dir, "base_pass_by_cell.csv"), index=False)

    # ---- per-cell analysis ------------------------------------------------
    cells = defaultdict(list)
    for _, r in ledger.iterrows():
        cells[r["cell_id"]].append(r)

    audit_rows, thresh_rows = [], []
    n_multi = n_qr_mono = n_qr_viol = 0
    n_potential_reversal = 0
    n_direct_mono = n_direct_viol = n_direct_undecidable = 0
    pot_cells = []

    for cid, recs in cells.items():
        recs = sorted(recs, key=lambda r: r["qp"])
        qps = [r["qp"] for r in recs]
        qrs = [r["qr_star"] for r in recs]
        bps = [r["base_pass"] for r in recs]
        city, typ = recs[0]["city"], recs[0]["type"]

        if len(recs) < 2:
            audit_rows.append(dict(cell_id=cid, city=city, type=typ,
                                   W=recs[0]["W"], n_qp=1, qr_star_monotonic=None,
                                   potential_base_pass_reversal=None,
                                   pattern="", note="single qp level"))
            continue
        n_multi += 1

        # (a) qr_star monotonicity (non-increasing in q_p)
        qr_vals = [float(q) if pd.notna(q) else float('nan') for q in qrs]
        qr_mono = all(a >= b or pd.isna(a) or pd.isna(b)
                      for a, b in zip(qr_vals, qr_vals[1:]))
        if qr_mono:
            n_qr_mono += 1
        else:
            n_qr_viol += 1

        # (b) POTENTIAL base_pass reversal: qr_star(low)=0 and qr_star(high)>0
        potential = False
        for a, b in zip(qrs, qrs[1:]):
            if pd.notna(a) and float(a) == 0 and pd.notna(b) and float(b) > 0:
                potential = True
        if potential:
            n_potential_reversal += 1
            pot_cells.append((cid, city, typ))

        # (c) direct base_pass monotonicity if a base_pass column was present
        direct = None
        if all(pd.notna(b) for b in bps):
            direct = all(a >= b for a, b in zip(bps, bps[1:]))
            if direct:
                n_direct_mono += 1
            else:
                n_direct_viol += 1
        else:
            n_direct_undecidable += 1

        pattern = "".join(("1" if pd.notna(b) and b == 1
                           else ("0" if pd.notna(b) else "?")) for b in bps)
        audit_rows.append(dict(cell_id=cid, city=city, type=typ, W=recs[0]["W"],
                               n_qp=len(recs),
                               qr_star_monotonic=qr_mono,
                               potential_base_pass_reversal=potential,
                               direct_base_pass_monotonic=direct,
                               pattern=pattern))

        last_pass = max((qps[i] for i in range(len(qps))
                         if pd.notna(qrs[i]) and float(qrs[i]) > 0), default=None)
        first_fail = min((qps[i] for i in range(len(qps))
                          if pd.notna(qrs[i]) and float(qrs[i]) == 0), default=None)
        thresh_rows.append(dict(
            cell_id=cid, city=city, W=recs[0]["W"], L=recs[0]["L"], type=typ,
            qp_last_pass=last_pass, qp_first_fail=first_fail,
            threshold_interval=("[%s, %s)" % (last_pass, first_fail)
                                if last_pass is not None and first_fail is not None
                                else None),
            n_tested_qp_levels=len(recs),
            note="PROXY interval from qr_star; NOT a base_pass point threshold."))

    audit = pd.DataFrame(audit_rows)
    audit.to_csv(os.path.join(args.out_dir, "base_pass_monotonicity_audit.csv"),
                 index=False)
    pd.DataFrame(thresh_rows).to_csv(
        os.path.join(args.out_dir, "sidewalk_baseline_thresholds.csv"), index=False)

    print("=" * 72)
    print("base_pass monotonicity audit — %s" % args.input)
    print("=" * 72)
    print(f"total (cell, qp) rows        : {len(df)}")
    print(f"total cells                  : {len(cells)}")
    print(f"cells with >=2 qp levels     : {n_multi}")
    print(f"qr_star monotonic (non-incr) : {n_qr_mono}")
    print(f"qr_star non-monotonic        : {n_qr_viol}")
    print(f"POTENTIAL base_pass reversals: {n_potential_reversal} "
          f"(qr_star low=0 & high>0)")
    if pot_cells:
        print("  candidate cells:", pot_cells)
    print(f"direct base_pass: mono={n_direct_mono} viol={n_direct_viol} "
          f"undecidable={n_direct_undecidable}")
    print("wrote base_pass_by_cell.csv | base_pass_monotonicity_audit.csv | "
          "sidewalk_baseline_thresholds.csv")


if __name__ == "__main__":
    main()
