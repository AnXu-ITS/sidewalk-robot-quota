"""
figures.py
==========
Generate the paper figures from the real experiment outputs.

  fig_degradation.png        speed-retention R_v vs robot flow q_r
  fig_quota_frontier.png     q_r* frontier heatmap over (q_p, W)
  fig_algorithm_vs_ref.png   q_hat_r vs q_r* (Model A)
  fig_policy_table.png       pedestrian-priority quota lookup table
  fig_threshold_sensitivity.png
  fig_speed_sensitivity.png
"""

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import PATHS, WIDTHS_TRAIN, PED_FLOWS_TRAIN, DELTA_V_LEVELS

FIG = PATHS["figures"]
os.makedirs(FIG, exist_ok=True)

plt.rcParams.update({"font.size": 10, "axes.grid": True,
                     "figure.dpi": 130, "savefig.bbox": "tight"})


def fig_degradation():
    detail = pd.read_csv(os.path.join(PATHS["quota_labels"], "quota_detail.csv"))
    quota = pd.read_csv(os.path.join(PATHS["quota_labels"], "quota_dataset.csv"))
    cells = [(1.8, 20), (2.4, 30), (3.0, 40)]
    fig, ax = plt.subplots(figsize=(7, 4.6))
    for W, qp in cells:
        d = detail[(detail["W"] == W) & (detail["qp"] == qp)].sort_values("qr")
        ax.plot(d["qr"], d["mean_Rv"], marker="o", label=f"W={W:.1f} m, q_p={qp} ped/min")
    ax.axhline(0.90, color="red", ls="--", lw=1.2, label="R_v = 0.90 floor")
    ax.axhline(1.0, color="gray", ls=":", lw=1)
    ax.set_xlabel("Robot flow q_r (robot/min)")
    ax.set_ylabel("Speed retention R_v")
    ax.set_title("Pedestrian speed retention vs delivery-robot flow")
    ax.legend(fontsize=8)
    ax.set_ylim(0, 1.15)
    fig.savefig(os.path.join(FIG, "fig_degradation.png"))


def fig_quota_frontier():
    quota = pd.read_csv(os.path.join(PATHS["quota_labels"], "quota_dataset.csv"))
    piv = quota.pivot(index="qp", columns="W", values="qr_star")
    fig, ax = plt.subplots(figsize=(6.6, 4.8))
    im = ax.imshow(piv.to_numpy(), aspect="auto", origin="lower",
                   cmap="viridis")
    ax.set_xticks(range(len(piv.columns)))
    ax.set_xticklabels([f"{c:.1f}" for c in piv.columns])
    ax.set_yticks(range(len(piv.index)))
    ax.set_yticklabels([f"{v:.0f}" for v in piv.index])
    ax.set_xlabel("Effective width W (m)")
    ax.set_ylabel("Pedestrian flow q_p (ped/min)")
    ax.set_title("Maximum feasible robot quota q_r* (robot/min)")
    for i in range(piv.shape[0]):
        for j in range(piv.shape[1]):
            ax.text(j, i, f"{piv.to_numpy()[i, j]:.0f}", ha="center",
                    va="center", color="white", fontsize=8)
    fig.colorbar(im, ax=ax, label="q_r* (robot/min)")
    fig.savefig(os.path.join(FIG, "fig_quota_frontier.png"))


def fig_algorithm_vs_reference():
    df = pd.read_csv(os.path.join(PATHS["processed"], "quota_predictions.csv"))
    for key, col in [("A", "pred_A"), ("B", "pred_B"), ("A-iso", "pred_A-iso")]:
        fig, ax = plt.subplots(figsize=(4.8, 4.6))
        ax.scatter(df["qr_star"], df[col], s=18, alpha=0.7)
        m = max(df["qr_star"].max(), df[col].max()) * 1.05
        ax.plot([0, m], [0, m], "k--", lw=1)
        ax.set_xlabel("Reference quota q_r*")
        ax.set_ylabel("Predicted quota q_hat_r")
        ax.set_title(f"{key}: predicted vs reference")
        ax.set_xlim(0, m)
        ax.set_ylim(0, m)
        fig.savefig(os.path.join(FIG, f"fig_algorithm_vs_reference_{key}.png"))
        plt.close(fig)


def fig_policy_table():
    quota = pd.read_csv(os.path.join(PATHS["quota_labels"], "quota_dataset.csv"))
    piv = quota.pivot(index="qp", columns="W", values="qr_star")
    fig, ax = plt.subplots(figsize=(7.5, 3.2))
    ax.axis("off")
    cols = ["q_p ↓ / W →"] + [f"{c:.1f} m" for c in piv.columns]
    cell = [cols] + [[f"{v:.0f}"] + [f"{piv.to_numpy()[i, j]:.0f}"
                  for j in range(piv.shape[1])]
                 for i, v in enumerate(piv.index)]
    tab = ax.table(cellText=cell, loc="center", cellLoc="center")
    tab.auto_set_font_size(False)
    tab.set_fontsize(9)
    tab.scale(1, 1.6)
    ax.set_title("Pedestrian-priority robot quota q_r* (robot/min)", pad=12)
    fig.savefig(os.path.join(FIG, "fig_policy_table.png"))


def fig_threshold_sensitivity():
    df = pd.read_csv(os.path.join(PATHS["sensitivity"],
                                  "threshold_sensitivity.csv"))
    W = 2.4
    fig, ax = plt.subplots(figsize=(6.4, 4.4))
    for dv in DELTA_V_LEVELS:
        d = df[(df["delta_v"] == dv) & (df["W"] == W)].sort_values("qp")
        ax.plot(d["qp"], d["qr_star"], marker="o",
                label=f"δ_v={dv:.0%} ({'strict' if dv==0.05 else 'normal' if dv==0.10 else 'permissive'})")
    ax.set_xlabel("Pedestrian flow q_p (ped/min)")
    ax.set_ylabel("Robot quota q_r* (robot/min)")
    ax.set_title(f"Threshold sensitivity (W = {W:.1f} m)")
    ax.legend()
    fig.savefig(os.path.join(FIG, "fig_threshold_sensitivity.png"))


def fig_speed_sensitivity():
    df = pd.read_csv(os.path.join(PATHS["sensitivity"],
                                  "speed_sensitivity_summary.csv"))
    fig, ax = plt.subplots(figsize=(6.6, 4.4))
    for (W, qp), g in df.groupby(["W", "qp"]):
        g = g.sort_values("speed_factor")
        ax.plot(g["speed_factor"], g["qr_star"], marker="o",
                label=f"W={W:.1f}, q_p={qp:.0f}")
    ax.set_xlabel("Robot speed factor (× v_ref)")
    ax.set_ylabel("Robot quota q_r* (robot/min)")
    ax.set_title("Reference-robot speed sensitivity")
    ax.legend(fontsize=8)
    fig.savefig(os.path.join(FIG, "fig_speed_sensitivity.png"))


def main():
    fig_degradation()
    fig_quota_frontier()
    fig_algorithm_vs_reference()
    fig_policy_table()
    try:
        fig_threshold_sensitivity()
        fig_speed_sensitivity()
    except FileNotFoundError:
        print("(sensitivity figures skipped: run sensitivity.py first)")
    print(f"figures written to {FIG}")


if __name__ == "__main__":
    main()
