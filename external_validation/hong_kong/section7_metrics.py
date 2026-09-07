# -*- coding: utf-8 -*-
"""Section 7 — external validation metrics.

Compares the zero-refit frozen operational quota (and nominal law) against the
simulation ground truth qr_star for in-domain HK cells. CIs are computed with a
CELL-LEVEL cluster bootstrap (all flow combos of a cell are correlated; seeds are
not independent city samples). OOD cells are reported as abstentions, never as
numeric zero, and never silently dropped from the overall stats.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
SITES = os.path.join(_HERE, "sites")
RUNS = os.path.join(_HERE, "runs", "formal")
RNG = np.random.default_rng(20260814)
N_BOOT = 2000


def bootstrap_cell(df, metric_fn, n_boot=N_BOOT, rng=RNG):
    cells = df.cell_id.unique()
    n = len(cells)
    ests = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        sample = pd.concat([df[df.cell_id == c] for c in cells[idx]])
        ests.append(metric_fn(sample))
    return np.array(ests)


def pct_ci(arr, alpha=0.05):
    return np.percentile(arr, [100 * alpha / 2, 100 * (1 - alpha / 2)])


def main():
    pred = pd.read_csv(os.path.join(SITES, "HONG_KONG_EXTERNAL_PREDICTIONS.csv"))
    # in-domain combos with a numeric prediction AND a valid reference (not
    # spawn-degraded, not OOD)
    _excl = pred.excluded.fillna(False).astype(bool)
    indom = pred[(pred.operational.notna()) & (~_excl)].copy()
    excl = pred[_excl].copy() if "excluded" in pred else pd.DataFrame()
    # OOD combos (abstained)
    ood = pred[pred.operational.isna()].copy()

    # ---- core error metrics (operational quota vs qr_star) ----
    def mae(df):
        return float(np.mean(np.abs(df.operational - df.qr_star_ref)))

    def rmse(df):
        return float(np.sqrt(np.mean((df.operational - df.qr_star_ref) ** 2)))

    def medae(df):
        return float(np.median(np.abs(df.operational - df.qr_star_ref)))

    def over_rate(df):
        d = df.operational - df.qr_star_ref
        return float(np.mean(d > 0))

    def over_mean_pos(df):
        d = df.operational - df.qr_star_ref
        return float(np.mean(d[d > 0])) if (d > 0).any() else 0.0

    def over_max_pos(df):
        d = df.operational - df.qr_star_ref
        return float(np.max(d)) if len(d) else 0.0

    def loss_mean(df):
        d = df.qr_star_ref - df.operational
        return float(np.mean(d[d > 0])) if (d > 0).any() else 0.0

    def util_median(df):
        u = df.operational / df.qr_star_ref.replace(0, np.nan)
        return float(np.median(u.dropna())) if u.dropna().size else np.nan

    def zero_rate(df):
        return float(np.mean(df.operational == 0))

    metrics = {}
    for name, fn in [("mae", mae), ("rmse", rmse), ("median_abs_err", medae),
                     ("overprediction_rate", over_rate),
                     ("mean_positive_overpred", over_mean_pos),
                     ("max_positive_overpred", over_max_pos),
                     ("mean_conservative_loss", loss_mean),
                     ("median_utilization", util_median),
                     ("feasible_zeroing_rate", zero_rate)]:
        est = fn(indom)
        lo, hi = pct_ci(bootstrap_cell(indom, fn))
        metrics[name] = dict(estimate=round(est, 4),
                             ci95=[round(lo, 4), round(hi, 4)])
        print(f"{name:26s} = {est:8.4f}  [95% CI {lo:.4f}, {hi:.4f}]")

    # ---- same for the NOMINAL law (no margin) to isolate margin effect ----
    indom2 = indom.assign(operational=indom.nominal_floored)
    mae_nom = mae(indom2)
    over_nom = over_rate(indom2)
    print(f"\nnominal (no margin): MAE={mae_nom:.4f}, "
          f"overprediction_rate={over_nom:.4f} "
          f"(vs operational MAE={mae(indom):.4f}, "
          f"overpred={over_rate(indom):.4f})")

    # ---- feasibility / OOD ----
    baseline_fail = int((indom.base_pass == 0).sum())
    zero_guard = int(((indom.base_pass == 1) & (indom.operational == 0)).sum())
    print(f"\nbaseline-failure cells (base_pass=0): {baseline_fail} / {len(indom)}")
    print(f"zero-guard cells (base_pass=1 but operational=0): {zero_guard}")
    print(f"spawn-excluded combos (integrity gate): {len(excl)}")
    print(f"OOD cells (abstained, None): {len(ood)} / {len(pred)} total combos")
    print(f"in-domain sweep-valid combos: {len(indom)} / {len(pred)}")

    # ---- per-width / per-x / per-geometry ----
    indom["wbin"] = pd.cut(indom.W, [1.5, 2.0, 2.4, 3.01],
                           labels=["narrow(1.6-2.0)", "mid(2.0-2.4)", "wide(2.4-3.0)"])
    indom["xbin"] = pd.cut(indom.x, [0, 8, 15, 22, 34],
                           labels=["x<8", "8-15", "15-22", "22-33"])
    groups = {}
    for key, col in [("width", "wbin"), ("x", "xbin"), ("geometry", "geometry_type")]:
        grp = indom.groupby(col, observed=True).apply(
            lambda d: pd.Series(dict(n=len(d), mae=mae(d), rmse=rmse(d),
                                     over_rate=over_rate(d),
                                     mean_oper=d.operational.mean(),
                                     mean_ref=d.qr_star_ref.mean())))
        print(f"\n--- per-{key} ---")
        print(grp.round(3).to_string())
        groups[key] = grp.reset_index().to_dict("records")

    # ---- D2 seven-city transfer comparison (in-domain) ----
    d2 = pd.read_csv(os.path.join(_REPO, "data", "final",
                                  "full_reference_dataset.csv"))
    # D2 operational quota vs D2 qr_star (in-domain rows only)
    sys.path.insert(0, os.path.join(_REPO, "final_freeze", "src"))
    import operational_quota as oq
    m = oq.OperationalQuota()
    d2_rows = []
    for r in d2.itertuples():
        geom = dict(type=r.type, sinuosity=float(r.sinuosity),
                    max_turn_deg=float(getattr(r, "max_turn_deg", 0.0)),
                    cum_turn_deg=float(getattr(r, "cum_turn_deg", 0.0)))
        oper = m.quota(float(r.W), float(r.qp), int(r.base_pass), geom,
                       float(r.vbar) if not pd.isna(r.vbar) else None)
        if oper is not None:
            d2_rows.append(dict(city=r.city, W=r.W, qp=r.qp, oper=oper,
                                ref=float(r.qr_star)))
    d2df = pd.DataFrame(d2_rows)
    d2_mae = float(np.mean(np.abs(d2df.oper - d2df.ref)))
    d2_rmse = float(np.sqrt(np.mean((d2df.oper - d2df.ref) ** 2)))
    d2_over = float(np.mean(d2df.oper - d2df.ref > 0))
    transfer = dict(d2_in_domain_n=len(d2df), d2_mae=round(d2_mae, 4),
                    d2_rmse=round(d2_rmse, 4), d2_overpred=round(d2_over, 4),
                    hk_mae=round(mae(indom), 4), hk_rmse=round(rmse(indom), 4),
                    hk_overpred=round(over_rate(indom), 4),
                    mae_gap=round(mae(indom) - d2_mae, 4),
                    rmse_gap=round(rmse(indom) - d2_rmse, 4))
    print(f"\n=== D2 (7-city in-domain) vs HK external ===")
    print(json.dumps(transfer, indent=2))

    # HONG_KONG_CITY_TRANSFER_COMPARISON.csv — per-city D2 + HK external
    city_rows = d2df.groupby("city").apply(
        lambda d: pd.Series(dict(n=len(d), mae=float(np.mean(np.abs(d.oper - d.ref))),
                                 rmse=float(np.sqrt(np.mean((d.oper - d.ref) ** 2))),
                                 overpred_rate=float(np.mean(d.oper - d.ref > 0)))))
    city_rows = city_rows.reset_index()
    hk_row = pd.DataFrame([dict(city="hongkong", n=len(indom),
                                mae=mae(indom), rmse=rmse(indom),
                                overpred_rate=over_rate(indom))])
    city_rows = pd.concat([city_rows, hk_row], ignore_index=True)
    city_rows.to_csv(os.path.join(SITES, "HONG_KONG_CITY_TRANSFER_COMPARISON.csv"),
                     index=False)
    print("\nwrote HONG_KONG_CITY_TRANSFER_COMPARISON.csv")
    print(city_rows.round(4).to_string(index=False))

    out = dict(metrics=metrics, nominal=dict(mae=round(mae_nom, 4),
                                             overpred_rate=round(over_nom, 4)),
               feasibility=dict(baseline_fail=baseline_fail, zero_guard=zero_guard,
                                n_spawn_excluded=int(len(excl)),
                                n_in_domain=int(len(indom)),
                                n_ood=int(len(ood)), n_total=int(len(pred))),
               per_group=groups, d2_transfer=transfer)
    with open(os.path.join(RUNS, "hk_external_metrics.json"), "w",
              encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False, default=str)
    print("\nwrote runs/formal/hk_external_metrics.json")


if __name__ == "__main__":
    main()
