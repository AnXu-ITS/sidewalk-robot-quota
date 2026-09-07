# -*- coding: utf-8 -*-
"""Section 7/8 — figures for the HK external validation report.

Matplotlib-only (no image model). Produces:
  fig_hk_pred_vs_ref.png      operational quota vs qr_star (in-domain)
  fig_hk_error_by_width.png   |pred-ref| by width bin (box + scatter)
  fig_hk_margin_effect.png    nominal vs operational overprediction
  fig_hk_transfer.png         D2 7-city vs HK external MAE/RMSE bars
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
SITES = os.path.join(_HERE, "sites")
RUNS = os.path.join(_HERE, "runs", "formal")
FIG = os.path.join(_HERE, "figures")
os.makedirs(FIG, exist_ok=True)


def main():
    pred = pd.read_csv(os.path.join(SITES, "HONG_KONG_EXTERNAL_PREDICTIONS.csv"))
    indom = pred[pred.operational.notna()].copy()
    ood = pred[pred.operational.isna()].copy()

    # 1) prediction vs reference
    fig, ax = plt.subplots(figsize=(6.4, 4.6))
    ax.plot([0, 20], [0, 20], "k--", lw=0.8, label="perfect")
    ax.scatter(indom.qr_star_ref, indom.operational, s=42, alpha=0.75,
               c=indom.W, cmap="viridis", edgecolor="k", linewidth=0.3)
    ax.set_xlabel("reference qr* (simulation)")
    ax.set_ylabel("frozen operational quota")
    ax.set_title("HK external: frozen quota vs qr* (in-domain, n=%d)" % len(indom))
    ax.axis("equal"); ax.set_xlim(-1, 21); ax.set_ylim(-1, 21)
    ax.legend(loc="upper left")
    fig.colorbar(ax.collections[0], ax=ax, label="W (m)")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig_hk_pred_vs_ref.png"),
                                    dpi=150); plt.close(fig)

    # 2) error by width bin
    indom["wbin"] = pd.cut(indom.W, [1.5, 2.0, 2.4, 3.01],
                           labels=["narrow\n1.6-2.0", "mid\n2.0-2.4", "wide\n2.4-3.0"])
    indom["err"] = indom.operational - indom.qr_star_ref
    fig, ax = plt.subplots(figsize=(6.4, 4.6))
    bins = indom.wbin.cat.categories
    data = [indom.loc[indom.wbin == b, "err"].values for b in bins]
    ax.boxplot(data, showfliers=False, widths=0.5)
    ax.set_xticks(range(1, len(bins) + 1), list(bins))
    ax.axhline(0, color="k", lw=0.8, ls="--")
    ax.set_ylabel("operational quota − qr*")
    ax.set_title("HK external: prediction error by width bin")
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig_hk_error_by_width.png"),
                                    dpi=150); plt.close(fig)

    # 3) margin effect (nominal vs operational overprediction)
    fig, ax = plt.subplots(figsize=(6.4, 4.6))
    ax.hist(indom.nominal_floored - indom.qr_star_ref, bins=20, alpha=0.6,
            label="nominal (no margin)")
    ax.hist(indom.operational - indom.qr_star_ref, bins=20, alpha=0.6,
            label="operational (Δ80=3.1068)")
    ax.axvline(0, color="k", lw=0.8, ls="--")
    ax.set_xlabel("prediction − qr*")
    ax.set_ylabel("count")
    ax.set_title("HK external: effect of deployment margin on overprediction")
    ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig_hk_margin_effect.png"),
                                    dpi=150); plt.close(fig)

    # 4) D2 vs HK transfer bars
    import json
    with open(os.path.join(RUNS, "hk_external_metrics.json"), encoding="utf-8") as f:
        m = json.load(f)
    tr = m["d2_transfer"]
    labels = ["D2 7-city\n(in-domain)", "HK external"]
    mae = [tr["d2_mae"], tr["hk_mae"]]
    rmse = [tr["d2_rmse"], tr["hk_rmse"]]
    x = np.arange(2); w = 0.35
    fig, ax = plt.subplots(figsize=(6.0, 4.4))
    ax.bar(x - w/2, mae, w, label="MAE")
    ax.bar(x + w/2, rmse, w, label="RMSE")
    ax.set_xticks(x); ax.set_xticklabels(labels)
    ax.set_ylabel("error (robots/min)")
    ax.set_title("Transfer: D2 fit vs HK external")
    ax.legend()
    for i, (a, b) in enumerate(zip(mae, rmse)):
        ax.text(i - w/2, a + 0.05, f"{a:.2f}", ha="center", fontsize=8)
        ax.text(i + w/2, b + 0.05, f"{b:.2f}", ha="center", fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig_hk_transfer.png"),
                                    dpi=150); plt.close(fig)

    print("wrote 4 figures to figures/; OOD cells abstained:", len(ood))


if __name__ == "__main__":
    main()
