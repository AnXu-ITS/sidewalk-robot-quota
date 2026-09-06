# -*- coding: utf-8 -*-
"""Empirically determine which rule the deployed base_pass column follows."""
import os

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))          # final_freeze/src -> repo root
DATA = os.path.join(_REPO, "data", "final")
mb = pd.read_csv(os.path.join(DATA, "multicity_baseline.csv"))
db = pd.read_csv(os.path.join(DATA, "decoupled_baseline.csv"))
base = pd.concat([mb, db], ignore_index=True)
full = pd.read_csv(os.path.join(DATA, "full_reference_dataset.csv"))

base["ok"] = ((base["mean_density"] <= 1.20)
              & (base["flow_ratio"] >= 0.90)
              & (base["flow_ratio"] <= 1.20)).astype(int)
g = base.groupby("tag").agg(
    n=("ok", "count"), frac_ok=("ok", "mean"),
    mean_density=("mean_density", "mean"),
    mean_fr=("flow_ratio", "mean")).reset_index()

m = full.merge(g, left_on="combo_id", right_on="tag", how="left")
matched = m["frac_ok"].notna()
print(f"tags matched to baseline CSVs: {int(matched.sum())} / {len(full)}")

mean_based = ((m["mean_density"] <= 1.20) & (m["mean_fr"] >= 0.90)
              & (m["mean_fr"] <= 1.20)).astype(int)
perseed = (m["frac_ok"] >= 29/30 - 1e-9).astype(int)

print("base_pass == mean-based rule   :",
      int((m["base_pass"][matched] == mean_based[matched]).sum()), "/",
      int(matched.sum()))
print("base_pass == per-seed 29/30 rule:",
      int((m["base_pass"][matched] == perseed[matched]).sum()), "/",
      int(matched.sum()))
# where do they disagree with deployed base_pass
dis_mean = matched & (m["base_pass"] != mean_based)
dis_ps = matched & (m["base_pass"] != perseed)
print("rows disagree with mean-based:", int(dis_mean.sum()),
      "| with per-seed:", int(dis_ps.sum()))
