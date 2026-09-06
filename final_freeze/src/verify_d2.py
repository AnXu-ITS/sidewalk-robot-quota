# -*- coding: utf-8 -*-
"""Summarize the authoritative D2 table (read-only)."""
import sys
import pandas as pd

p = sys.argv[1]
df = pd.read_csv(p)
print("path      :", p)
print("rows      :", len(df))
print("columns   :", list(df.columns))
print()
print("source counts:")
print(df["source"].value_counts(dropna=False).to_string())
print()
print("city counts:")
print(df["city"].value_counts(dropna=False).to_string())
print()
print("type counts:")
print(df["type"].value_counts(dropna=False).to_string())
print()
print("base_pass counts:")
print(df["base_pass"].value_counts(dropna=False).to_string())
print()
print("qr_star summary:")
print(df["qr_star"].describe().to_string())
print()
print("W summary:")
print(df["W"].describe().to_string())
print()
print("qp summary:")
print(df["qp"].describe().to_string())
print()
# consistency: qr_star vs qr_star_per_seed vs qr_star_mean
print("qr_star == qr_star_per_seed :", int((df["qr_star"] == df["qr_star_per_seed"]).sum()),
      "of", len(df))
print("qr_star == qr_star_mean     :", int((df["qr_star"] == df["qr_star_mean"]).sum()),
      "of", len(df))
print("rows where per_seed != mean :", int((df["qr_star_per_seed"] != df["qr_star_mean"]).sum()))
print()
# zero-quota cells and base_pass
print("rows with qr_star==0        :", int((df["qr_star"] == 0).sum()))
print("rows with base_pass==0       :", int((df["base_pass"] == 0).sum()))
print("rows base_pass==0 & qr_star>0:", int(((df["base_pass"] == 0) & (df["qr_star"] > 0)).sum()))
print("rows base_pass==1 & qr_star==0:", int(((df["base_pass"] == 1) & (df["qr_star"] == 0)).sum()))
