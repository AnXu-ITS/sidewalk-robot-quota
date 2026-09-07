# -*- coding: utf-8 -*-
"""Section 6 — zero-refit external prediction using the FROZEN runtime.

For every cell in the frozen sample: nominal law, frozen Q80 operational rule,
base_pass guard, OOD/fallback. Reads the simulation-derived ground truth
(runs/formal/hk_reference_qr_star.csv) and writes
sites/HONG_KONG_EXTERNAL_PREDICTIONS.csv. No parameter is re-fit.
"""
import math
import os
import sys

import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, os.path.join(_REPO, "final_freeze", "src"))

import operational_quota as oq  # noqa: E402

SITES = os.path.join(_HERE, "sites")
RUNS = os.path.join(_HERE, "runs", "formal")


def main():
    m = oq.OperationalQuota()
    frz = pd.read_csv(os.path.join(SITES, "HONG_KONG_FORMAL_SAMPLE_FREEZE.csv"))
    mat = pd.read_csv(os.path.join(SITES, "HONG_KONG_EXPERIMENT_MATRIX.csv"))
    qr_star = pd.read_csv(os.path.join(RUNS, "hk_reference_qr_star.csv"))

    qr_map = {(r.cell_id, int(r.qp)): r for r in qr_star.itertuples()}

    rows = []
    for r in mat.itertuples():
        cell = frz[frz.cell_id == r.cell_id].iloc[0]
        geom = dict(type=cell.geometry_type, sinuosity=float(cell.sinuosity),
                    max_turn_deg=float(cell.max_turn_deg),
                    cum_turn_deg=float(cell.cum_turn_deg))
        W = float(cell.W)
        rec = dict(cell_id=r.cell_id, W=W, geometry_type=cell.geometry_type,
                   sinuosity=cell.sinuosity, qp=r.qp, x=round(r.x, 4) if r.x else None,
                   status=r.status)
        if r.qp is None or math.isnan(r.qp):
            # OOD -> abstain
            rec.update(dict(base_pass=None, vbar=None, qr_star_ref=None,
                            nominal=None, nominal_floored=None,
                            operational=None, outcome="OOD/abstain (None)"))
            rows.append(rec)
            continue
        qp = int(r.qp)
        q = qr_map.get((r.cell_id, qp))
        base_pass = int(q.base_pass) if q is not None else None
        vbar = float(q.vbar) if q is not None else None
        ref = float(q.qr_star) if q is not None else None
        integrity = (getattr(q, "integrity", "ok") if q is not None else "ok")
        excluded = integrity != "ok"
        # frozen runtime (zero-refit)
        oper = m.quota(W, qp, base_pass, geom, vbar)
        # nominal law (no margin, for the margin-effect analysis)
        x = qp / W
        nominal = m.c * W * (x ** m.p)
        nominal_floored = float(math.floor(nominal))
        if excluded:
            # reference invalid (spawn/flow failure) -> no metric, keep frozen
            # prediction only for transparency
            rec.update(dict(
                base_pass=base_pass, vbar=round(vbar, 4) if vbar is not None else None,
                qr_star_ref=None, nominal=round(nominal, 4),
                nominal_floored=nominal_floored, operational=oper,
                excluded=True, integrity=integrity,
                outcome=f"excluded (spawn-integrity): {integrity}"))
        else:
            rec.update(dict(
                base_pass=base_pass, vbar=round(vbar, 4) if vbar is not None else None,
                qr_star_ref=ref, nominal=round(nominal, 4),
                nominal_floored=nominal_floored, operational=oper,
                excluded=False, integrity=integrity,
                outcome=("OOD/abstain (None)" if oper is None
                         else ("base_pass=0 -> 0" if base_pass == 0
                               else ("zero-guard -> 0" if oper == 0.0
                                     else "operational")))))
        rows.append(rec)

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(SITES, "HONG_KONG_EXTERNAL_PREDICTIONS.csv"), index=False)
    print(df.to_string(index=False))
    print(f"\nwrote HONG_KONG_EXTERNAL_PREDICTIONS.csv ({len(df)} rows)")


if __name__ == "__main__":
    main()
