# -*- coding: utf-8 -*-
"""
refine_boundary.py — Phase 4: local boundary refinement.

Identify combos whose quota boundary sits between ladder levels (last feasible
qr* and first infeasible level differ by > 1 step AND the first infeasible level
is a close call), then scan the intermediate levels with the SAME protocol
(30 seeds). No full re-scan.

Two modes:
  --plan   (default) write refinement_plan.json: combos x intermediate levels
  --run    execute the planned refinement scenarios, merge into
           refined_quota_reference_table.csv with before/after qr*
"""
import argparse
import json
import os

import pandas as pd

ROOT = r"C:\Users\xuan1\Desktop\UOL学习\配送机器人workbench\pipeline"
SIM_SCRIPTS = os.path.join(ROOT, "sim", "scripts")
DELTA_V = 0.10
OUTMIN, OUTMAX = 0.90, 1.20
DFLOOR = 1.20
LEVELS = [1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 18, 20]


def load_evidence(kinds=("main", "decoupled"), evdir=None):
    """(combo_key -> (cell_meta, centerline)), sweep df, baseline df."""
    base_parts, sweep_parts, meta = [], [], {}
    for kind in kinds:
        d = evdir or os.path.join(ROOT, "sim", "outputs",
                                  "p1_multicity" if kind == "main"
                                  else "decoupled")
        pref = "multicity" if kind == "main" else "decoupled"
        if not os.path.exists(d):
            continue
        base_parts.append(pd.read_csv(os.path.join(d, f"{pref}_baseline.csv")))
        sweep_parts.append(pd.read_csv(os.path.join(d, f"{pref}_sweep.csv")))
        cells = json.load(open(os.path.join(
            ROOT, "cells", "selected_cells.json" if kind == "main"
            else "decoupled_cells.json"), encoding="utf-8"))
        src = cells["cells"] if "cells" in cells else cells["combos"]
        for c in src:
            key = f"{c['cell_id']}|qp{round(c.get('qp', c.get('q_p_peak', [0])[0]))}"
            meta[key] = c
    return (pd.concat(base_parts, ignore_index=True) if base_parts else None,
            pd.concat(sweep_parts, ignore_index=True) if sweep_parts else None,
            meta)


def plan(evdir=None):
    kinds = ("main",) if evdir else ("main", "decoupled")
    base, sweep, meta = load_evidence(kinds, evdir=evdir)
    if sweep is None:
        print("no sweep data yet"); return
    vb = base.groupby("tag")["mean_speed"].mean()
    s = sweep.merge(vb.rename("vbar"), on="tag", how="left")
    s["Rv"] = s["mean_speed"] / s["vbar"]
    s["pass"] = ((s["Rv"] >= 1 - DELTA_V) & (s["flow_ratio"] >= OUTMIN)
                 & (s["flow_ratio"] <= OUTMAX)
                 & (s["mean_density"] <= DFLOOR)).astype(int)
    g = s.groupby(["tag", "qr"]).agg(pass_frac=("pass", "mean"),
                                     mean_Rv=("Rv", "mean"),
                                     n=("pass", "count")).reset_index()
    plan_rows = []
    for tag, sub in g.groupby("tag"):
        passed = sub[sub["pass_frac"] > 0.5]
        qr_star = float(passed["qr"].max()) if len(passed) else 0.0
        if qr_star <= 0 or qr_star >= 20:
            continue
        hi_levels = [l for l in LEVELS if l > qr_star]
        if not hi_levels:
            continue
        nxt = hi_levels[0]
        fail = sub[(sub["qr"] == nxt) & (sub["n"] >= 30)]
        if not len(fail):
            continue
        close = (float(fail["pass_frac"].iloc[0]) >= 0.5
                 or float(fail["mean_Rv"].iloc[0]) >= 0.85)
        if nxt - qr_star > 1 and close:
            between = [v for v in range(int(qr_star) + 1, int(nxt))]
            plan_rows.append(dict(tag=tag, qr_star=qr_star, next_level=nxt,
                                  between=between,
                                  fail_frac=round(float(fail["pass_frac"].iloc[0]), 3),
                                  fail_Rv=round(float(fail["mean_Rv"].iloc[0]), 3)))
    out = {"n": len(plan_rows), "plan": plan_rows,
           "total_scenarios": sum(len(p["between"]) for p in plan_rows) * 30}
    with open(os.path.join(ROOT, "cells", "refinement_plan.json"),
              "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"refinement plan: {out['n']} combos, "
          f"{out['total_scenarios']} scenarios (x30 seeds)")
    return out


def run():
    base, sweep, meta = load_evidence()
    plan = json.load(open(os.path.join(ROOT, "cells", "refinement_plan.json"),
                         encoding="utf-8"))
    if not plan["plan"]:
        print("empty plan"); return
    import sys
    sys.path.insert(0, SIM_SCRIPTS)
    from config import SIM, N_SEEDS_SWEEP  # noqa: E402
    from run_batch import run_batch  # noqa: E402
    scen = []
    for p in plan["plan"]:
        c = meta[p["tag"]]
        cl = [list(pt) for pt in c["centerline"]]
        for qr in p["between"]:
            for seed in range(N_SEEDS_SWEEP):
                scen.append((c["W_eff"] if "W_eff" in c else c["W"], SIM["L"],
                             float(c["qp"]), float(qr), seed, None, None, None,
                             cl, p["tag"]))
    outdir = os.path.join(ROOT, "sim", "outputs", "refinement")
    os.makedirs(outdir, exist_ok=True)
    df = run_batch(scen, n_procs=None, out_csv=os.path.join(
        outdir, "refinement_sweep.csv"), label="refine")
    # merge with original: recompute qr* including refined levels
    alls = pd.concat([sweep, df], ignore_index=True)
    vb = base.groupby("tag")["mean_speed"].mean()
    alls = alls.merge(vb.rename("vbar"), on="tag", how="left")
    alls["Rv"] = alls["mean_speed"] / alls["vbar"]
    alls["pass"] = ((alls["Rv"] >= 1 - DELTA_V)
                    & (alls["flow_ratio"] >= OUTMIN)
                    & (alls["flow_ratio"] <= OUTMAX)
                    & (alls["mean_density"] <= DFLOOR)).astype(int)
    g = alls.groupby(["tag", "qr"]).agg(pass_frac=("pass", "mean"),
                                        n=("pass", "count")).reset_index()
    recs = []
    for p in plan["plan"]:
        tag = p["tag"]
        sub = g[(g["tag"] == tag) & (g["n"] >= 30)]
        passed = sub[sub["pass_frac"] > 0.5]
        new_star = float(passed["qr"].max()) if len(passed) else 0.0
        recs.append(dict(tag=tag, qr_star_before=p["qr_star"],
                         qr_star_after=new_star,
                         changed=new_star != p["qr_star"]))
    out = pd.DataFrame(recs)
    out.to_csv(os.path.join(outdir, "refined_quota_reference_table.csv"),
               index=False)
    print(out.to_string(index=False))
    print(f"refined: {int(out.changed.sum())}/{len(out)} combos changed")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--evdir", default=None, help="override evidence dir")
    args = ap.parse_args()
    if args.run:
        run()
    else:
        plan(args.evdir)
