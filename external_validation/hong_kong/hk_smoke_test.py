# -*- coding: utf-8 -*-
"""
HK external test — graded smoke test (Gates S1-S4).

Only proceeds to the next gate if the previous one passes. Reuses the frozen
pipeline engine and criteria. SMOKE seed count is reduced (not the formal 30);
smoke values are NEVER reported as q_r*.

Gates:
  S1 geometry-only: build + load + minimal run, no fatal error / bad geometry
  S2 pedestrian-only (qr=0): spawn/leave + valid metrics + mean-based base_pass
  S3 minimal mixed flow (qr=2): robot spawns, interaction runs, metrics valid
  S4 mini reference check: tiny ascending sweep + checkpoint/CSV + criteria code
     (mean_density<=1.20, 0.90<=flow_ratio<=1.20, speed vacuous at qr=0,
      base_pass mean-based, qr_star per-seed >=29/30) — code-path check only.
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from hk_smoke_runner import run_cell  # noqa: E402

_PIPE = os.path.join(os.path.dirname(os.path.dirname(_HERE)),
                     "pipeline", "sim", "scripts")
sys.path.insert(0, _PIPE)
from config import CONSTRAINTS  # noqa: E402
from simulator import evaluate_constraints  # noqa: E402

RUNS = os.path.join(_HERE, "runs", "smoke")
os.makedirs(RUNS, exist_ok=True)

DFLOOR = CONSTRAINTS["density_floor"]       # 1.20
DELTA_V = CONSTRAINTS["delta_v"]            # 0.10
OUTMIN = CONSTRAINTS["outflow_ratio_min"]   # 0.90
OUTMAX = CONSTRAINTS["outflow_ratio_max"]   # 1.20
CONF = CONSTRAINTS["conf_level"]            # 0.95  -> >= 29/30 (formal)

CELL = "HK-ST-01"
W = 2.331
L = 50.0
QP = 20.0            # frozen in-domain level (D2 PED_FLOWS_TRAIN)
QR_MIX = 2.0         # minimal non-zero robot flow (D2 ROBOT_FLOWS)
N_SMOKE = 6          # SMOKE seed count (formal = 30)
SMOKE_SWEEP = [0.0, 1.0, 2.0, 3.0]   # tiny ascending sweep for S4

GEO = json.load(open(os.path.join(_HERE, "sites", "hk_cell_local_geometry.json"),
                     encoding="utf-8"))
CELLGEO = GEO[CELL]
CL = [tuple(p) for p in CELLGEO["centerline_local"]]
POLY = CELLGEO["walkable_polygon_local"]["coordinates"]


def log(msg):
    print(msg, flush=True)


def check_geometry():
    """S1 helper: static geometry sanity of the imported real polygon."""
    from shapely.geometry import shape
    from shapely.ops import unary_union
    poly = shape({"type": "Polygon", "coordinates": POLY})
    area = poly.area
    exp = L * W
    x0, y0, x1, y1 = poly.bounds
    return dict(
        area=round(area, 3), expected_LxW=round(exp, 3),
        area_ratio=round(area / exp, 3),
        bounds=[round(v, 3) for v in (x0, y0, x1, y1)],
        valid=poly.is_valid,
        centerline=CL,
    )


def run_batch(cell, W, L, qp, qr, seeds):
    rows = []
    t0 = time.time()
    for s in seeds:
        m = run_cell(cell, W, L, CL, POLY, qp=qp, qr=qr, seed=s)
        rows.append(m)
        log(f"  [qp={qp} qr={qr} seed={s}] dens={m['mean_density']:.3f} "
            f"flow_ratio={m['flow_ratio']:.3f} speed={m['mean_speed']:.3f} "
            f"in={m['inflow_ped']} out={m['outflow_ped']}")
    dt = time.time() - t0
    log(f"  batch wall-time {dt:.1f}s for {len(seeds)} seeds")
    return pd.DataFrame(rows)


def main():
    results = {"gates": {}, "runs": {}}
    seeds = list(range(N_SMOKE))

    # ---------------- S1: geometry-only --------------------------------
    log("=" * 70)
    log("GATE S1 — geometry-only")
    geo = check_geometry()
    log(f"  real polygon area={geo['area']} m2 (L*W={geo['expected_LxW']}), "
        f"ratio={geo['area_ratio']}, valid={geo['valid']}, "
        f"bounds={geo['bounds']}")
    s1_ok = geo["valid"] and abs(geo["area_ratio"] - 1.0) < 0.35
    # minimal run (no traffic) to confirm sumo loads the scenario without error
    try:
        m0 = run_cell(CELL, W, L, CL, POLY, qp=0.0, qr=0.0, seed=0)
        s1_run_ok = (m0["timed_out"] == 0)
        log(f"  minimal-run OK: {s1_run_ok} (in={m0['inflow_ped']})")
    except Exception as e:
        s1_run_ok = False
        log(f"  minimal-run FAILED: {e}")
    s1_ok = s1_ok and s1_run_ok
    results["gates"]["S1"] = {"pass": bool(s1_ok), "geometry": geo,
                              "minimal_run_ok": bool(s1_run_ok)}
    log(f"  S1 PASS={s1_ok}")
    if not s1_ok:
        return results, "S1"

    # ---------------- S2: pedestrian-only ------------------------------
    log("=" * 70)
    log("GATE S2 — pedestrian-only (qr=0, qp=20)")
    base_df = run_batch(CELL, W, L, QP, 0.0, seeds)
    base_df.to_csv(os.path.join(RUNS, "hk_s2_baseline.csv"), index=False)
    n = len(base_df)
    checks = dict(
        n_seeds=n,
        inflow_all_positive=bool((base_df["inflow_ped"] > 0).all()),
        outflow_all_positive=bool((base_df["outflow_ped"] > 0).all()),
        density_finite=bool(np.isfinite(base_df["mean_density"]).all()),
        speed_finite=bool(np.isfinite(base_df["mean_speed"]).all()),
        no_timeout=bool((base_df["timed_out"] == 0).all()),
    )
    # mean-based base_pass (deployed criterion; speed retention vacuous at qr=0)
    mean_density = float(base_df["mean_density"].mean())
    mean_flow = float(base_df["flow_ratio"].mean())
    base_pass_mean = bool(mean_density <= DFLOOR and OUTMIN <= mean_flow <= OUTMAX)
    checks.update(mean_density=round(mean_density, 4),
                  mean_flow_ratio=round(mean_flow, 4),
                  base_pass_mean=base_pass_mean)
    # per-seed baseline pass fraction (speed vacuous)
    ok = ((base_df["mean_density"] <= DFLOOR)
          & (base_df["flow_ratio"] >= OUTMIN)
          & (base_df["flow_ratio"] <= OUTMAX)).to_numpy(bool)
    checks["baseline_pass_frac_seed"] = round(float(ok.mean()), 3)
    s2_ok = (checks["inflow_all_positive"] and checks["outflow_all_positive"]
             and checks["density_finite"] and checks["speed_finite"]
             and checks["no_timeout"] and n >= 2)
    results["gates"]["S2"] = {"pass": bool(s2_ok), **checks}
    results["runs"]["baseline"] = base_df.to_dict("records")
    log(f"  mean_density={mean_density:.4f} (<=1.20) mean_flow={mean_flow:.4f} "
        f"(0.90-1.20) base_pass_mean={base_pass_mean}")
    log(f"  S2 PASS={s2_ok}")
    if not s2_ok:
        return results, "S2"

    # ---------------- S3: minimal mixed flow ---------------------------
    log("=" * 70)
    log("GATE S3 — minimal mixed flow (qr=2, qp=20)")
    mix_df = run_batch(CELL, W, L, QP, QR_MIX, seeds)
    mix_df.to_csv(os.path.join(RUNS, "hk_s3_mixed_qr2.csv"), index=False)
    vbar = float(base_df["mean_speed"].mean())
    # robot presence: robot count = inflow of vClass robot (approx via speed>=1.3)
    # better: re-parse robot from personinfo; here we check speed/density/metrics
    checks3 = dict(
        n_seeds=len(mix_df),
        no_timeout=bool((mix_df["timed_out"] == 0).all()),
        density_finite=bool(np.isfinite(mix_df["mean_density"]).all()),
        speed_finite=bool(np.isfinite(mix_df["mean_speed"]).all()),
        inflow_positive=bool((mix_df["inflow_ped"] > 0).all()),
    )
    # per-seed pass under mixed flow (speed retention now active)
    flags = [evaluate_constraints(m, vbar, DELTA_V, OUTMIN, OUTMAX, DFLOOR)
             for m in mix_df.to_dict("records")]
    mix_pass = sum(f["pass"] for f in flags)
    checks3["mixed_pass_frac"] = round(mix_pass / len(flags), 3)
    s3_ok = (checks3["no_timeout"] and checks3["density_finite"]
             and checks3["speed_finite"] and checks3["inflow_positive"]
             and mix_pass > 0)
    results["gates"]["S3"] = {"pass": bool(s3_ok), "vbar": round(vbar, 4),
                              **checks3}
    results["runs"]["mixed_qr2"] = mix_df.to_dict("records")
    log(f"  vbar={vbar:.4f} mixed_pass_frac={mix_pass}/{len(flags)}")
    log(f"  S3 PASS={s3_ok}")
    if not s3_ok:
        return results, "S3"

    # ---------------- S4: mini reference check -------------------------
    log("=" * 70)
    log("GATE S4 — mini reference check (tiny ascending sweep, code-path)")
    sweep_parts = [base_df.assign(qr=0.0)]
    for qr in SMOKE_SWEEP:
        if qr == 0.0:
            continue
        df = run_batch(CELL, W, L, QP, qr, seeds)
        df.to_csv(os.path.join(RUNS, f"hk_s4_sweep_qr{int(qr)}.csv"), index=False)
        sweep_parts.append(df.assign(qr=float(qr)))
    sweep_df = pd.concat(sweep_parts, ignore_index=True)
    sweep_df.to_csv(os.path.join(RUNS, "hk_s4_sweep_all.csv"), index=False)

    # ---- criteria code (read from authoritative logic) -----------------
    vbar = float(base_df["mean_speed"].mean())
    # base_pass: mean-based (deployed column)
    mean_density = float(base_df["mean_density"].mean())
    mean_flow = float(base_df["flow_ratio"].mean())
    base_pass = bool(mean_density <= DFLOOR and OUTMIN <= mean_flow <= OUTMAX)
    # qr_star: per-seed >= CONF (0.95) — smoke seed count means >= N/N
    qr_star = 0.0
    per_level = {}
    for qr in sorted(sweep_df["qr"].unique()):
        sub = sweep_df[sweep_df["qr"] == qr]
        flags = [evaluate_constraints(m, vbar, DELTA_V, OUTMIN, OUTMAX, DFLOOR)
                 for m in sub.to_dict("records")]
        frac = sum(f["pass"] for f in flags) / len(flags)
        per_level[float(qr)] = round(frac, 3)
        if frac >= CONF:
            qr_star = max(qr_star, float(qr))
    # checkpoint re-read (verify CSV merge path)
    reread = pd.read_csv(os.path.join(RUNS, "hk_s4_sweep_all.csv"))
    checkpoint_ok = (len(reread) == len(sweep_df))

    results["gates"]["S4"] = dict(
        **{"pass": bool(base_pass and checkpoint_ok)},
        vbar=round(vbar, 4),
        base_pass_mean=base_pass,
        qr_star_smoke=qr_star,
        per_level_pass_frac=per_level,
        checkpoint_csv_ok=checkpoint_ok,
        NOTE="SMOKE seed count=%d; qr_star_smoke is NOT the formal 30-seed "
             ">=29/30 value and must not be reported as q_r*." % N_SMOKE,
    )
    log(f"  base_pass(mean)={base_pass} qr_star_smoke={qr_star} "
        f"per_level={per_level} checkpoint_ok={checkpoint_ok}")
    log(f"  S4 PASS={results['gates']['S4']['pass']}")
    return results, None


if __name__ == "__main__":
    t0 = time.time()
    res, stopped = main()
    res["stopped_at_gate"] = stopped
    res["wall_time_s"] = round(time.time() - t0, 1)
    out = os.path.join(RUNS, "hk_smoke_results.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, ensure_ascii=False, default=str)
    print("\nwrote", out)
    print(json.dumps({k: v.get("pass") if isinstance(v, dict) else v
                      for k, v in res["gates"].items()}, indent=2))
