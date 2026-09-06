# -*- coding: utf-8 -*-
"""
consolidate_reference.py — Phase 0/3/4 table builder.
Builds main_280_reference_table.csv (and the same schema for decoupled data)
from the driver outputs, adding per-seed pass/fail & pass fractions and the
per-seed (>=29/30) qr* alongside the mean-criterion qr*.

Usage:
  python consolidate_reference.py --kind main     # p1_multicity outputs
  python consolidate_reference.py --kind decoupled
Inputs are discovered under pipeline/sim/outputs/{p1_multicity,decoupled}/.
"""
import argparse
import json
import os

import numpy as np
import pandas as pd

ROOT = r"C:\Users\xuan1\Desktop\UOL学习\配送机器人workbench\pipeline"
DELTA_V = 0.10
OUTMIN, OUTMAX = 0.90, 1.20
DFLOOR = 1.20
LEVELS = [1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 18, 20]
PASS_RULE = 29 / 30

KIND_META = {
    "main": dict(dir="p1_multicity", prefix="multicity",
                 cells_json="cells/selected_cells.json",
                 out="main_280_reference_table.csv"),
    "decoupled": dict(dir="decoupled", prefix="decoupled",
                      cells_json="cells/decoupled_cells.json",
                      out="decoupled_120_reference_table.csv"),
}


def per_seed_pass(df, vbar):
    df = df.copy()
    df["Rv"] = df["mean_speed"] / df["vbar"]
    return ((df["Rv"] >= 1 - DELTA_V)
            & (df["flow_ratio"] >= OUTMIN)
            & (df["flow_ratio"] <= OUTMAX)
            & (df["mean_density"] <= DFLOOR)).astype(int)


def build(kind, outdir=None):
    meta = KIND_META[kind]
    outdir = outdir or os.path.join(ROOT, "sim", "outputs", meta["dir"])
    base = pd.read_csv(os.path.join(outdir, f"{meta['prefix']}_baseline.csv"))
    sweep = pd.read_csv(os.path.join(outdir, f"{meta['prefix']}_sweep.csv"))
    results = pd.read_csv(os.path.join(outdir, f"{meta['prefix']}_results.csv"))

    vb = base.groupby("tag")["mean_speed"].mean()
    sweep = sweep.merge(vb.rename("vbar"), on="tag", how="left")
    sweep["Rv"] = sweep["mean_speed"] / sweep["vbar"]
    sweep["pass"] = ((sweep["Rv"] >= 1 - DELTA_V)
                     & (sweep["flow_ratio"] >= OUTMIN)
                     & (sweep["flow_ratio"] <= OUTMAX)
                     & (sweep["mean_density"] <= DFLOOR)).astype(int)
    g = sweep.groupby(["tag", "qr"]).agg(
        pass_frac=("pass", "mean"), n=("pass", "count"),
        mean_Rv=("Rv", "mean")).reset_index()

    rows = []
    for _, r in results.iterrows():
        # tag must match the driver's format: f"{cell_id}|qp{qp:g}"
        tag = f"{r['cell_id']}|qp{float(r['qp']):g}"
        sub = g[g["tag"] == tag]
        qr_star_mean = r["qr_star"]
        # per-seed rule: max qr with pass_frac >= 29/30
        ok = sub[(sub["pass_frac"] >= PASS_RULE - 1e-9) & (sub["n"] >= 30)]
        qr_star_ps = float(ok["qr"].max()) if len(ok) else 0.0
        frac_at_star = None
        frac_at_next = None
        if len(sub):
            s1 = sub[sub["qr"] == qr_star_mean]
            if len(s1):
                frac_at_star = round(float(s1["pass_frac"].iloc[0]), 3)
            nxt_levels = [l for l in LEVELS if l > qr_star_mean]
            if nxt_levels:
                s2 = sub[sub["qr"] == nxt_levels[0]]
                if len(s2):
                    frac_at_next = round(float(s2["pass_frac"].iloc[0]), 3)
        rows.append(dict(
            combo_id=tag, cell_id=r["cell_id"], city=r["city"],
            city_code=r.get("city_code"), type=r["type"],
            context=r["context"], W=round(r["W"], 3), L=r.get("L", 50.0),
            qp=round(float(r["qp"]), 1), x=round(float(r["qp"]) / r["W"], 3),
            sinuosity=round(r.get("sinuosity", 1.0), 4),
            vbar=round(r.get("vbar", 0.0), 3),
            base_pass=int(r.get("base_pass", 1)),
            qr_star_mean=float(qr_star_mean),
            above_upper=int(r.get("above_upper", 0)),
            qr_star_per_seed=qr_star_ps,
            pass_frac_at_star=frac_at_star,
            pass_frac_at_next=frac_at_next))
    out = pd.DataFrame(rows).sort_values(["city", "qp", "cell_id"])
    out_path = os.path.join(ROOT, "cells", meta["out"])
    out.to_csv(out_path, index=False)
    print(f"[{kind}] {len(out)} combos -> {out_path}")
    print(f"  qr* mean vs per-seed differ: "
          f"{int((out.qr_star_mean != out.qr_star_per_seed).sum())}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=["main", "decoupled", "both"],
                    default="both")
    ap.add_argument("--outdir", default=None,
                    help="override outputs dir (dry-run on archived data)")
    ap.add_argument("--outfile", default=None,
                    help="override output csv path")
    args = ap.parse_args()
    if args.kind in ("main", "both"):
        build("main", args.outdir)
    if args.kind in ("decoupled", "both"):
        build("decoupled", args.outdir)


if __name__ == "__main__":
    main()
