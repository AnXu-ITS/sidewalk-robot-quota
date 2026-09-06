# -*- coding: utf-8 -*-
"""
merge_datasets.py — build full_reference_dataset.csv =
  main_280_reference_table.csv (mean & per-seed qr*, pass fractions)
+ decoupled_120_reference_table.csv
+ refined boundary corrections (qr*_refined where changed).
Rows keep a `source` column (main / decoupled) and `qr_star` (deployable:
per-seed criterion with refinement applied where available).
"""
import argparse
import os

import pandas as pd

CELLS = r"C:\Users\xuan1\Desktop\UOL学习\配送机器人workbench\pipeline\cells"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refined", default=None,
                    help="refined_quota_reference_table.csv (optional)")
    args = ap.parse_args()

    main = pd.read_csv(os.path.join(CELLS, "main_280_reference_table.csv"))
    main["source"] = "main"
    dec = pd.read_csv(os.path.join(CELLS, "decoupled_120_reference_table.csv"))
    dec["source"] = "decoupled"

    both = pd.concat([main, dec], ignore_index=True)
    both["qr_star"] = both["qr_star_per_seed"]

    if args.refined and os.path.exists(args.refined):
        ref = pd.read_csv(args.refined)
        if "tag" in ref.columns and "qr_star_after" in ref.columns:
            ref = ref[["tag", "qr_star_after"]].rename(
                columns={"tag": "combo_id"})
            both = both.merge(ref, on="combo_id", how="left")
            both["qr_star"] = both["qr_star_after"].fillna(both["qr_star"])
            both = both.drop(columns=["qr_star_after"])
            print(f"refinement applied to "
                  f"{int(ref['combo_id'].isin(both['combo_id']).sum())} rows")
    out = os.path.join(CELLS, "full_reference_dataset.csv")
    both.to_csv(out, index=False)
    print(f"full_reference_dataset: {len(both)} rows "
          f"(main {len(main)} + decoupled {len(dec)}) -> {out}")
    print("cities:", sorted(both["city"].unique()))
    print("qr* counts:", both["qr_star"].value_counts().sort_index().to_dict())


if __name__ == "__main__":
    main()
