# -*- coding: utf-8 -*-
"""
build_final_model.py
====================
Build and evaluate the FINAL guarded quota model (paper's production model).

Two-layer architecture (admissibility -> level -> deployment):

  Layer 1  admissibility (is ANY robot admitted at all?)
     W < W_min (1.6)                        -> 0   [geometric: robot disc + passing space]
     x = q_p/W >= x_crit (33.33)            -> 0   [pedestrian-only over-capacity]
     q_p >= C(W)                            -> 0   [W-dependent robot-admissible capacity]
     concentrated sharp corner              -> 0   [max_turn>=20 AND cum_turn>=20 AND
                                                    max_turn/cum_turn>=0.6; bend-sweep
                                                    + position-sweep calibrated]
     pedestrian-only vbar < 0.8 m/s         -> 0   [absolute LOS floor; closes the
                                                    relative-criterion artifact]
  Layer 2  level
     q_hat = min( W * c * x^p , Q_low(W) )        [power law + low-flow ceiling]
     Q_low(W) = per-seed reference plateau at q_p = 10 (training grid), piecewise
                linear: the corridor's finite robot throughput in nearly-empty
                conditions; removes the x -> 0 divergence of the power law.
     capped at q_max = 20 (verified sweep ceiling)
  Layer 3  deployment
     q_deploy = floor(q_hat)                      [safe-side integer]

The sharp-corner / vbar guards only fire on real geometries (synthetic cells are
straight); Q_low and the admissibility rules fire everywhere.  No threshold here
is tuned on the 200 multi-city combos: Q_low comes from training labels, the
corner/speed guards from the P2 mini-experiments (bend_sweep / position_sweep).

Evaluation: training fit metrics, held-out metrics + closed-loop per-seed SVR
(re-simulating any deployed level missing from the existing CSVs, inline), and
the 200-combo multi-city re-evaluation with a guard-activation ledger.

Outputs:
  models/quota_algorithm/quota_params_final.json
  data/processed/fit_metrics_final.csv
  outputs/validation/test_metrics_final.csv
  outputs/validation/svr_final_table.csv / svr_final_summary.csv
  outputs/validation/closed_loop_final_gap.csv   (only if new levels needed)
  outputs/p1_multicity/multicity_final_eval.csv
"""
import json
import os
import re
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import PATHS, SIM, N_SEEDS_VALIDATION  # noqa: E402
from fit_quota import predict_quota  # noqa: E402
from rescore_seedwise_full import sweep_pass_frac, CONF  # noqa: E402
from run_batch import run_batch  # noqa: E402

L = SIM["L"]
TOL = 1e-9

SHARP_DEG = 20.0
CONC_RATIO = 0.6
VBAR_MIN = 0.8

# Q_low(W): per-seed reference plateau at q_p=10 (training grid, monotone)
QLOW_W = np.array([1.5, 1.6, 1.7, 1.8, 2.1, 2.4, 2.7, 3.0], float)
QLOW_Q = np.array([0.0, 5.0, 6.0, 8.0, 10.0, 18.0, 20.0, 20.0], float)


def load_seedwise_model():
    with open(os.path.join(PATHS["models"], "quota_params_seedwise.json"),
              encoding="utf-8") as f:
        P = json.load(f)
    return dict(x_crit=P["x_crit"], W_min=P["W_min"],
                C_W=(np.asarray(P["C_W"]["W"], float),
                     np.asarray(P["C_W"]["C"], float)),
                q_max=P["q_max"], c=P["A"]["c"], p=P["A"]["p"])


def qlow(W):
    return np.interp(np.asarray(W, float), QLOW_W, QLOW_Q)


def final_predict(df, model, geom=None):
    """geom: dict cell_id -> {max_turn_deg, cum_turn_deg} for real cells."""
    qp = df["qp"].to_numpy(float)
    W = df["W"].to_numpy(float)
    base = predict_quota(qp, W, "A", (model["c"], model["p"]),
                         model["x_crit"], model["W_min"], model["C_W"],
                         model["q_max"])
    pred = np.minimum(base, qlow(W))
    if geom is not None:
        mt = np.asarray([float(geom[c].get("max_turn_deg", 0.0))
                         for c in df["cell_id"]], float)
        cum = np.asarray([float(geom[c].get("cum_turn_deg", 0.0))
                          for c in df["cell_id"]], float)
        conc = np.divide(mt, cum, out=np.zeros_like(mt), where=cum > 1e-6)
        sharp = (mt >= SHARP_DEG) & (cum >= SHARP_DEG) & (conc >= CONC_RATIO)
        pred = np.where(sharp, 0.0, pred)
    if "vbar" in df.columns:
        pred = np.where(df["vbar"].to_numpy(float) < VBAR_MIN, 0.0, pred)
    return pred


def metrics(pred, qr):
    err = pred - qr
    over = np.maximum(0.0, err)
    under = np.maximum(0.0, -err)
    return dict(MAE=float(np.mean(np.abs(err))),
                RMSE=float(np.sqrt(np.mean(err ** 2))),
                mean_over=float(over.mean()), max_over=float(over.max()),
                mean_under=float(under.mean()),
                OAR=float(np.mean(pred > qr)),
                over_floor=int((np.floor(pred) > qr).sum()),
                under_floor=int((np.floor(pred) < qr).sum()))


# ---------------------------------------------------------------------------
def main():
    model = load_seedwise_model()

    # ---- 1. training fit metrics -------------------------------------------
    train = pd.read_csv(os.path.join(PATHS["quota_labels"],
                                     "quota_dataset_seedwise.csv"))
    train["pred_final"] = final_predict(train, model)
    tr = metrics(train["pred_final"].to_numpy(float),
                 train["qr_star"].to_numpy(float))
    tr["model"] = "A-final"
    tr_df = pd.DataFrame([tr])
    oldA = train[["W", "qp", "qr_star"]].merge(
        pd.read_csv(os.path.join(PATHS["processed"],
                                 "quota_predictions_seedwise.csv"))[
            ["W", "qp", "pred_A"]], on=["W", "qp"])
    trA = metrics(oldA["pred_A"].to_numpy(float),
                  oldA["qr_star"].to_numpy(float))
    print("=== training (per-seed labels) ===")
    print(f"A-seedwise (no Q_low): MAE={trA['MAE']:.3f} "
          f"OAR={trA['OAR']:.3f} over_floor={trA['over_floor']}/48")
    print(f"A-final   (guarded)  : MAE={tr['MAE']:.3f} "
          f"OAR={tr['OAR']:.3f} over_floor={tr['over_floor']}/48 "
          f"under_floor={tr['under_floor']}/48")
    tr_df.to_csv(os.path.join(PATHS["processed"], "fit_metrics_final.csv"),
                 index=False)

    # ---- 2. held-out --------------------------------------------------------
    test = pd.read_csv(os.path.join(PATHS["validation"],
                                    "test_truth_seedwise.csv"))
    test["pred_final"] = final_predict(test, model)
    te = metrics(test["pred_final"].to_numpy(float),
                 test["qr_star"].to_numpy(float))
    te_df = pd.DataFrame([{**te, "model": "A-final"}])
    teA = metrics(test["pred_A"].to_numpy(float),
                  test["qr_star"].to_numpy(float))
    print("\n=== held-out (per-seed labels, 35 cells) ===")
    print(f"A-seedwise: MAE={teA['MAE']:.3f} OAR={teA['OAR']:.3f} "
          f"over_floor={teA['over_floor']}/35")
    print(f"A-final   : MAE={te['MAE']:.3f} OAR={te['OAR']:.3f} "
          f"over_floor={te['over_floor']}/35 max_over={te['max_over']:.2f}")
    te_df.to_csv(os.path.join(PATHS["validation"], "test_metrics_final.csv"),
                 index=False)

    # ---- 3. closed-loop per-seed SVR ---------------------------------------
    print("\n=== closed-loop (per-seed pass rule) ===")
    cl_floor = pd.read_csv(os.path.join(PATHS["validation"],
                                        "closed_loop_A-floor.csv"))
    cl_new = pd.read_csv(os.path.join(PATHS["validation"],
                                      "closed_loop_seedwise_new.csv"))
    tsweep = pd.read_csv(os.path.join(PATHS["validation"], "test_sweep.csv"))

    def lookup(Wv, qpv, level, src):
        sub = src[(src["W"] == Wv) & (src["qp"] == qpv)]
        return sub[np.isclose(sub["qr"].to_numpy(float), level, atol=TOL)]

    vbar = dict(zip(zip(test["W"], test["qp"]), test["vbar"]))
    gap = []
    rows = []
    for _, r in test.iterrows():
        if not r["base_pass"]:
            continue
        Wv, qpv = r["W"], r["qp"]
        level = float(np.floor(r["pred_final"]))
        frac = None
        if level <= 0:
            frac = 1.0
        else:
            for src in (cl_new, cl_floor, tsweep):
                sub = lookup(Wv, qpv, level, src)
                if len(sub):
                    frac, _ = sweep_pass_frac(sub, vbar[(Wv, qpv)])
                    break
        if frac is None:
            gap.append((Wv, qpv, level))
            rows.append(dict(W=Wv, qp=qpv, level=level,
                             qr_star=r["qr_star"], pass_frac=None,
                             violated=False, scored=False))
            continue
        bad = frac < CONF
        rows.append(dict(W=Wv, qp=qpv, level=level, qr_star=r["qr_star"],
                         pass_frac=frac, violated=bad, scored=True))

    if gap:
        scen = []
        for (Wv, qpv, level) in gap:
            for s in range(N_SEEDS_VALIDATION):
                scen.append([Wv, L, qpv, level, s, None, None, None])
        gap_csv = os.path.join(PATHS["validation"], "closed_loop_final_gap.csv")
        print(f"  re-simulating {len(gap)} missing levels "
              f"({len(scen)} scenarios)")
        gdf = run_batch(scen, n_procs=None, out_csv=gap_csv,
                        label="final closed-loop gap")
        for i, row in enumerate(rows):
            if row["scored"]:
                continue
            sub = lookup(row["W"], row["qp"], row["level"], gdf)
            if len(sub):
                frac, _ = sweep_pass_frac(sub, vbar[(row["W"], row["qp"])])
                row["pass_frac"] = frac
                row["violated"] = frac < CONF
                row["scored"] = True

    svr_tab = pd.DataFrame(rows)
    n = len(svr_tab)
    viol = int(svr_tab["violated"].sum())
    print(f"  A-final A-floor: SVR = {viol/n:.4f} ({viol}/{n} feasible "
          f"cells, per-seed rule)")
    print("  violations:")
    print(svr_tab[svr_tab["violated"]][
        ["W", "qp", "level", "qr_star", "pass_frac"]].to_string(index=False))
    svr_tab.to_csv(os.path.join(PATHS["validation"], "svr_final_table.csv"),
                   index=False)
    pd.DataFrame([dict(model="A-final", SVR=viol / n, n_viol=viol, n=n)]).to_csv(
        os.path.join(PATHS["validation"], "svr_final_summary.csv"),
        index=False)

    # ---- 4. multi-city (200 combos) ----------------------------------------
    print("\n=== multi-city (per-seed labels, 200 combos) ===")
    mc = pd.read_csv(os.path.join(PATHS["root"], "outputs", "p1_multicity",
                                  "multicity_results.csv"))
    rsw = pd.read_csv(os.path.join(PATHS["root"], "outputs", "p1_multicity",
                                   "rescore_seedwise.csv"))

    def parse_tag(tag):
        m = re.match(r"^(.*)\|qp(\d+)$", str(tag))
        return (m.group(1), int(m.group(2))) if m else (None, None)

    rsw["cell_id"], rsw["qp_int"] = zip(*rsw["tag"].map(parse_tag))
    mc = mc.merge(rsw[["cell_id", "qp_int", "seedwise_qr_star"]],
                  left_on=["cell_id", "qp"], right_on=["cell_id", "qp_int"],
                  how="left")
    mc["qr"] = mc["seedwise_qr_star"].fillna(0.0)
    cells = {c["cell_id"]: c for c in json.load(
        open(os.path.normpath(os.path.join(PATHS["root"], "..", "sumo_jupedsim",
                                           "data", "cells.json")),
             encoding="utf-8"))["cells"]}
    mc["pred_final"] = final_predict(mc, model, geom=cells)
    mc["pred_seed"] = final_predict(mc, model, geom=None)
    mc["floor_final"] = np.floor(mc["pred_final"])
    mc["over"] = mc["floor_final"] - mc["qr"]

    print(f"  A-seedwise (unguarded): MAE=1.350 OAR=0.180 over_floor=30/200")
    mf = metrics(mc["pred_final"].to_numpy(float), mc["qr"].to_numpy(float))
    print(f"  A-final   (guarded)  : MAE={mf['MAE']:.3f} OAR={mf['OAR']:.3f} "
          f"over_floor={mf['over_floor']}/200 "
          f"under_floor={mf['under_floor']}/200 max_over={mf['max_over']:.0f}")

    # guard activation ledger
    mt = mc["cell_id"].map(lambda c: cells[c]["max_turn_deg"]).to_numpy(float)
    cum = mc["cell_id"].map(lambda c: cells[c]["cum_turn_deg"]).to_numpy(float)
    conc = np.divide(mt, cum, out=np.zeros_like(mt), where=cum > 1e-6)
    sharp = (mt >= SHARP_DEG) & (cum >= SHARP_DEG) & (conc >= CONC_RATIO)
    slow = mc["vbar"].to_numpy(float) < VBAR_MIN
    base = predict_quota(mc["qp"].to_numpy(float), mc["W"].to_numpy(float),
                         "A", (model["c"], model["p"]), model["x_crit"],
                         model["W_min"], model["C_W"], model["q_max"])
    low_bind = np.minimum(base, qlow(mc["W"].to_numpy(float))) < base - 1e-9
    print(f"  guard activations: sharp_corner={int(sharp.sum())} "
          f"vbar_floor={int(slow.sum())} lowflow_cap={int(low_bind.sum())} "
          f"(combos)")

    subsets = [("all", mc),
               ("amsterdam", mc[mc["city"] == "amsterdam"]),
               ("type B", mc[mc["type"] == "B"]),
               ("type C", mc[mc["type"] == "C"]),
               ("in-domain (W<=3, non-B)",
                mc[(mc["W"] <= 3.0) & (mc["type"] != "B")])]
    rows = []
    for sname, sub in subsets:
        m = metrics(sub["pred_final"].to_numpy(float),
                    sub["qr"].to_numpy(float))
        m["subset"] = sname
        m["n"] = len(sub)
        rows.append(m)
        print(f"  {sname:26s} n={len(sub):3d} MAE={m['MAE']:.3f} "
              f"OAR={m['OAR']:.3f} over_floor={m['over_floor']}/{len(sub)} "
              f"under_floor={m['under_floor']}/{len(sub)} "
              f"max_over={m['max_over']:.1f}")
    pd.DataFrame(rows).to_csv(
        os.path.join(PATHS["root"], "outputs", "p1_multicity",
                     "multicity_final_eval.csv"), index=False)

    # ---- save final model ---------------------------------------------------
    out = dict(
        criterion="per-seed (Pr(C_p=1) >= 0.95, >= 29/30 seeds)",
        architecture="admissibility guards -> level = min(power law, Q_low(W)) -> floor",
        x_crit=model["x_crit"], W_min=model["W_min"],
        C_W={"W": [float(w) for w in model["C_W"][0]],
             "C": [float(c) for c in model["C_W"][1]]},
        q_max=model["q_max"],
        A={"c": model["c"], "p": model["p"]},
        Q_low_W={"W": [float(w) for w in QLOW_W],
                 "Q": [float(q) for q in QLOW_Q],
                 "source": "per-seed training labels at q_p=10; finite robot "
                           "throughput of a nearly-empty corridor"},
        guards={
            "sharp_corner_zero": {"max_turn_min_deg": SHARP_DEG,
                                  "cum_turn_min_deg": SHARP_DEG,
                                  "concentration_min": CONC_RATIO,
                                  "source": "bend_sweep + position_sweep"},
            "absolute_speed_floor": {"vbar_min": VBAR_MIN,
                                     "source": "position_sweep artifact fix"},
        },
        domain="calibrated for straight-to-mildly-curved corridors with "
               "W <= 3.0 m and q_p <= 60 ped/min; extra-wide / sharp-corner "
               "cells need discrete treatment or re-calibration",
    )
    with open(os.path.join(PATHS["models"], "quota_params_final.json"), "w",
              encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"\nwrote {os.path.join(PATHS['models'], 'quota_params_final.json')}")


if __name__ == "__main__":
    main()
