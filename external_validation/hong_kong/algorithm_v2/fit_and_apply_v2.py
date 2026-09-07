# -*- coding: utf-8 -*-
"""v2 small-scale trial: apply the v2 rule (margin = 0) to HK + D2 test cities.

Research-owner decision (utilization-priority): the deployment margin Delta is
set to 0 for all widths. The other guardrails (Q_low, C(W), floor) already bound
overprediction to <= +3 on D2, so the additive margin was redundant.

Train cities for any future margin work: amsterdam, melbourne, newtaipei, nyc,
taipei (the frozen held-out test cities seattle + taoyuan are NOT used).
"""
import os
import sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_HK = os.path.abspath(os.path.join(_HERE, ".."))
_REPO = os.path.abspath(os.path.join(_HK, "..", ".."))
sys.path.insert(0, os.path.join(_REPO, "final_freeze", "src"))
sys.path.insert(0, _HERE)
import operational_quota as oq

W_BINS = [(1.6, 2.0), (2.0, 2.4), (2.4, 3.0)]
TRAIN_CITIES = {"amsterdam", "melbourne", "newtaipei", "nyc", "taipei"}
TEST_CITIES = {"seattle", "taoyuan", "hongkong"}

# deterministic synthetic qp for the 9 cells v2 recovers (x = qp / W_eff < 33.33)
QP_RECOVERED = {
    "HK-ST-07": 60, "HK-ST-23": 60, "HK-ST-31": 30, "HK-ST-32": 50,
    "HK-ST-14": 30, "HK-ST-17": 40, "HK-ST-20": 20, "HK-ST-26": 30,
    "HK-ST-29": 50,
}


def interp(x, xs, ys):
    x = float(x)
    if x <= xs[0]:
        return float(ys[0])
    if x >= xs[-1]:
        return float(ys[-1])
    for i in range(len(xs) - 1):
        if xs[i] <= x <= xs[i + 1]:
            t = (x - xs[i]) / (xs[i + 1] - xs[i])
            return ys[i] + t * (ys[i + 1] - ys[i])
    return float(ys[-1])


def main():
    m1 = oq.OperationalQuota()
    c, p = m1.c, m1.p
    QW, QQ, CW, CC = m1.QW, m1.QQ, m1.CW, m1.CC

    def full_quota(W, qp, base_pass, geom, vbar, margin):
        if int(base_pass) == 0:
            return 0.0
        if qp > m1.qp_max:
            return None
        x = qp / W
        if x >= m1.x_crit:
            return 0.0
        if qp >= interp(W, CW, CC):
            return 0.0
        mt = float(geom.get("max_turn_deg", 0.0))
        cum = float(geom.get("cum_turn_deg", 0.0))
        conc = (mt / cum) if cum > 1e-6 else 0.0
        if mt >= m1.sharp["max_turn_min_deg"] and \
           cum >= m1.sharp["cum_turn_min_deg"] and \
           conc >= m1.sharp["concentration_min"]:
            return 0.0
        if vbar is not None and float(vbar) < m1.vbar_min:
            return 0.0
        q = c * W * (x ** p)
        q = max(0.0, q - margin)
        q = min(q, interp(W, QW, QQ))
        q = min(q, m1.q_max)
        return float(np.floor(q))

    def geom_of(t, s):
        return dict(type=t, sinuosity=float(s), max_turn_deg=0.0,
                    cum_turn_deg=0.0)

    # ---- D2 in-domain, split train/test cities ----
    d2 = pd.read_csv(os.path.join(_REPO, "data", "final",
                                  "full_reference_dataset.csv"))
    d2rows = []
    for r in d2.itertuples():
        g = geom_of(r.type, r.sinuosity)
        oper = m1.quota(float(r.W), float(r.qp), int(r.base_pass), g,
                        float(r.vbar) if not pd.isna(r.vbar) else None)
        if oper is None:
            continue
        d2rows.append(dict(city=r.city, W=float(r.W), qp=float(r.qp),
                           base_pass=int(r.base_pass), geom=g,
                           vbar=float(r.vbar) if not pd.isna(r.vbar) else None,
                           ref=float(r.qr_star)))
    d2d = pd.DataFrame(d2rows)

    # ---- margin = 0 (utilization-priority decision; fixed, NOT fitted) ----
    margin_bins = [(1.6, float("inf"), 0.0)]
    print("=== margin = 0.0 (utilization-priority; fixed, not fitted) ===")

    def margin_for(W):
        for lo, hi, d in margin_bins:
            if lo <= W < hi:
                return d
        return margin_bins[-1][2]

    def v2_quota(W, qp, base_pass, geom, vbar, gtype, p10):
        gtype = str(gtype).upper()
        if gtype == "C":
            We = float(p10 if p10 is not None else W)
        else:
            We = float(W)
        We = min(We, 3.0)  # clamp wide to 3.0 for ALL types
        if We < 1.6:
            return None
        # type-B sinuosity gate (unchanged from frozen): sinuous B stays OOD
        if gtype == "B" and float(geom.get("sinuosity", 0.0)) > 1.05:
            return None
        return full_quota(We, qp, base_pass, geom, vbar, margin_for(We))

    # ---- HK: freeze + matrix + reference ----
    frz = pd.read_csv(os.path.join(_HK, "sites",
                                   "HONG_KONG_FORMAL_SAMPLE_FREEZE.csv"))
    mat = pd.read_csv(os.path.join(_HK, "sites",
                                   "HONG_KONG_EXPERIMENT_MATRIX.csv"))
    qr = pd.read_csv(os.path.join(_HK, "runs", "formal",
                                  "hk_reference_qr_star.csv"))
    qr_map = {r.cell_id: r for r in qr.itertuples()}

    qp_of = {}
    for r in mat.itertuples():
        if r.qp is not None and r.qp == r.qp:
            qp_of[r.cell_id] = r.qp
    qp_of.update(QP_RECOVERED)

    out = []
    for _, cell in frz.iterrows():
        cid = cell.cell_id
        qp = qp_of.get(cid)
        if qp is None:
            continue
        geom = dict(type=cell.geometry_type, sinuosity=float(cell.sinuosity),
                    max_turn_deg=float(cell.max_turn_deg),
                    cum_turn_deg=float(cell.cum_turn_deg))
        q = qr_map.get(cid)
        vbar = float(q.vbar) if (q is not None and q.vbar == q.vbar) else None
        ref = float(q.qr_star) if (q is not None and q.qr_star == q.qr_star) \
            else None
        excl = (q is not None and q.integrity != "ok") or (q is None)
        v1 = m1.quota(float(cell.W), float(qp), 1, geom, vbar)
        v2 = v2_quota(float(cell.W), float(qp), 1, geom, vbar,
                      cell.geometry_type, float(cell.width_p10))
        out.append(dict(cell_id=cid, W=cell.W, width_p10=cell.width_p10,
                        geometry_type=cell.geometry_type, qp=qp, ref=ref,
                        v1=v1, v2=v2, has_ref=ref is not None,
                        spawn_excluded=bool(excl),
                        integrity=(q.integrity if q is not None else "OOD")))
    res = pd.DataFrame(out)

    # ---- coverage ----
    ood_cells = set(frz[frz.applicability_status.str.contains("OOD", na=False)]
                    .cell_id)
    recov = res[res.cell_id.isin(ood_cells)]
    recov_in = recov[recov.v2.notna()]
    narrow_still = [c for c in sorted(ood_cells) if c not in set(res.cell_id)]
    print("\n=== coverage ===")
    print(f"  OOD cells: {len(ood_cells)}")
    print(f"  v2 recovers: {len(recov_in)}  {sorted(recov_in.cell_id.tolist())}")
    print(f"  v2 still narrow-OOD (<1.6m): {len(narrow_still)}  {narrow_still}")

    # ---- v1 vs v2 on cells with ground truth (13 valid + D2 test cities) ----
    valid = res[(~res.spawn_excluded) & (res.ref.notna())].copy()
    valid["e1"] = valid.v1 - valid.ref
    valid["e2"] = valid.v2 - valid.ref
    def summ(d, ecol):
        e = d[ecol]
        pos = d[d.ref > 0]
        u = (pos.v2 / pos.ref) if ecol == "e2" else (pos.v1 / pos.ref)
        return dict(mae=float(np.mean(np.abs(e))),
                    over=float(np.mean(e > 0)),
                    util_med=float(np.median(u)) if len(pos) else np.nan,
                    util_mean=float(np.mean(u)) if len(pos) else np.nan)
    print("\n=== HK 13 valid cells: v1 vs v2 ===")
    print(valid[["cell_id", "W", "qp", "ref", "v1", "v2"]].to_string(index=False))
    s1 = summ(valid, "e1"); s2 = summ(valid, "e2")
    print(f"\n  v1: MAE={s1['mae']:.2f} overpred={s1['over']:.3f} "
          f"util_med={s1['util_med']:.3f} util_mean={s1['util_mean']:.3f}")
    print(f"  v2: MAE={s2['mae']:.2f} overpred={s2['over']:.3f} "
          f"util_med={s2['util_med']:.3f} util_mean={s2['util_mean']:.3f}")

    # ---- v2 on D2 test cities (seattle, taoyuan) ----
    print("\n=== v2 on D2 held-out test cities (seattle, taoyuan) ===")
    for city in ["seattle", "taoyuan"]:
        sub = d2d[d2d.city == city].copy()
        sub["v2"] = [v2_quota(r.W, r.qp, r.base_pass, r.geom, r.vbar,
                              r.geom.get("type"), None) for r in sub.itertuples()]
        e = sub.v2 - sub.ref
        pos = sub[sub.ref > 0]
        u = pos.v2 / pos.ref
        print(f"  {city}: n={len(sub)} MAE={np.mean(np.abs(e)):.2f} "
              f"overpred={np.mean(e>0):.3f} util_med={np.median(u):.3f}")

    print("\n=== v2 quotas for recovered cells (no ground truth yet) ===")
    print(recov_in[["cell_id", "W", "width_p10", "geometry_type", "qp", "v2"]]
          .to_string(index=False))

    res.to_csv(os.path.join(_HERE, "v2_hk_quotas.csv"), index=False)
    print("\nwrote algorithm_v2/v2_hk_quotas.csv")


if __name__ == "__main__":
    main()
