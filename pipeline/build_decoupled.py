# -*- coding: utf-8 -*-
"""
build_decoupled.py — Phase 2: decoupled supplemental design.
For each of the 40 selected cells, add THREE identical specific-flow levels
x = q_p/W in {18, 24, 30} -> q_p = x * W (NOT the contextual priors), so that
W and x become (near-)independent in the supplemental design.

Out-of-domain combos (e.g. q_p > 60 ped/min, the calibrated domain ceiling, or
W < W_min) are FLAGGED, never clipped. 40 x 3 = 120 supplemental combos.

Outputs:
  pipeline/cells/decoupled_120_design.csv   design table
  pipeline/cells/decoupled_cells.json       driver input (flat combo list)
"""
import csv
import json
import os

SEL = r"C:\Users\xuan1\Desktop\UOL学习\配送机器人workbench\pipeline\cells\selected_40_cells.json"
OUT_CSV = r"C:\Users\xuan1\Desktop\UOL学习\配送机器人workbench\pipeline\cells\decoupled_120_design.csv"
OUT_JSON = r"C:\Users\xuan1\Desktop\UOL学习\配送机器人workbench\pipeline\cells\decoupled_cells.json"

X_NEW = [18.0, 24.0, 30.0]
QP_DOMAIN_MAX = 60.0   # final model's calibrated q_p domain ceiling
W_MIN = 1.6            # final model W_min (below -> physically impassable for 0.96 m robot)


def main():
    sel = json.load(open(SEL, encoding="utf-8"))
    combos = []
    ci = 0
    for c in sel["cells"]:
        for x in X_NEW:
            qp = round(x * c["W_eff"], 1)
            flags = []
            if qp > QP_DOMAIN_MAX:
                flags.append("qp>60")
            if c["W_eff"] < W_MIN:
                flags.append("W<W_min")
            if x >= 33.33:
                flags.append("x>=x_crit")
            combos.append(dict(
                combo_id=f"DC-{ci:03d}", cell_id=c["cell_id"],
                city=c["city"], city_code=c.get("city_code"),
                split=c["split"], type=c["type"], context=c["context"],
                W=c["W_eff"], L=c["L"], qp=qp, x=x,
                ood_flags=";".join(flags) if flags else "",
                centerline=c["centerline"], sinuosity=c["sinuosity"]))
            ci += 1
    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        wcsv = csv.writer(f)
        wcsv.writerow(["combo_id", "cell_id", "city", "split", "type",
                       "context", "W", "L", "qp", "x", "ood_flags"])
        for i, c in enumerate(combos):
            wcsv.writerow([f"DC-{i:03d}", c["cell_id"], c["city"], c["split"],
                           c["type"], c["context"], c["W"], c["L"], c["qp"],
                           c["x"], c["ood_flags"]])
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump({"n": len(combos), "combos": combos}, f, ensure_ascii=False,
                  indent=1)
    ood = sum(1 for c in combos if c["ood_flags"])
    print(f"decoupled combos: {len(combos)} (40 x 3), out-of-domain flagged: {ood}")
    qps = sorted(c["qp"] for c in combos)
    print(f"qp range: {qps[0]:.1f} .. {qps[-1]:.1f} ped/min")
    print(f"-> {OUT_CSV} / {OUT_JSON}")


if __name__ == "__main__":
    main()
