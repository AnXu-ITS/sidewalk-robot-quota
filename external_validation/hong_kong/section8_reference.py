# -*- coding: utf-8 -*-
"""Assemble HONG_KONG_REFERENCE_DATASET.csv (the external-test ground truth).

Merges the sweep-derived qr* (runs/formal/hk_reference_qr_star.csv) for the
18 in-domain cells with the 14 OOD cells (qr*=None, abstained). One row per
cell (the frozen sample unit), plus qp/x and the width/geometry used by the
frozen gate.
"""
import os

import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
SITES = os.path.join(_HERE, "sites")
RUNS = os.path.join(_HERE, "runs", "formal")


def main():
    frz = pd.read_csv(os.path.join(SITES, "HONG_KONG_FORMAL_SAMPLE_FREEZE.csv"))
    mat = pd.read_csv(os.path.join(SITES, "HONG_KONG_EXPERIMENT_MATRIX.csv"))
    qr = pd.read_csv(os.path.join(RUNS, "hk_reference_qr_star.csv"))
    qr_map = {r.cell_id: r for r in qr.itertuples()}

    rows = []
    for r in mat.itertuples():
        cell = frz[frz.cell_id == r.cell_id].iloc[0]
        rec = dict(cell_id=r.cell_id, W=float(cell.W),
                   geometry_type=cell.geometry_type,
                   sinuosity=float(cell.sinuosity), qp=(int(r.qp)
                                                         if r.qp == r.qp else None),
                   x=(round(r.x, 4) if r.x == r.x else None),
                   applicability=cell.applicability_status)
        if r.qp is None or r.qp != r.qp:
            rec.update(dict(base_pass=None, vbar=None, qr_star=None,
                            integrity="OOD/abstain"))
        else:
            q = qr_map.get(r.cell_id)
            rec.update(dict(
                base_pass=(int(q.base_pass) if q is not None else None),
                vbar=(round(float(q.vbar), 4) if q is not None and q.vbar == q.vbar
                      else None),
                qr_star=(float(q.qr_star) if q is not None and q.qr_star == q.qr_star
                         else None),
                integrity=(q.integrity if q is not None else "n/a")))
        rows.append(rec)
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(SITES, "HONG_KONG_REFERENCE_DATASET.csv"), index=False)
    print(df.to_string(index=False))
    print(f"\nwrote HONG_KONG_REFERENCE_DATASET.csv ({len(df)} rows)")


if __name__ == "__main__":
    main()
