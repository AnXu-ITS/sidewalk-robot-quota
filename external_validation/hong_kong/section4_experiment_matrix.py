# -*- coding: utf-8 -*-
"""Section 4 — freeze pedestrian-flow design + full experiment matrix.

- In-domain cells (18): full protocol (baseline qr=0 + base sweep
  [1,2,3,4,5,6,8,10] + extended [12,15,18,20] only if saturated at qr=10).
- OOD cells (14): frozen runtime abstains (None); NO simulation.
- qp assigned from D2 PED_FLOWS_TRAIN = [10,20,30,40,50,60]; x=qp/W < 33.33
  enforced. Synthetic experimental demand (NOT HK measured flow).
- Deterministic matrix generated upfront (no result-dependent add/remove).
"""
import hashlib
import json
import os

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
SITES = os.path.join(HERE, "sites")

PED_FLOWS = [10, 20, 30, 40, 50, 60]
X_CRIT = 33.333333
ROBOT_FLOWS_BASE = [0, 1, 2, 3, 4, 5, 6, 8, 10]
ROBOT_FLOWS_EXTENDED = [12, 15, 18, 20]
N_SEEDS_BASELINE = 30
N_SEEDS_SWEEP = 30

# deterministic qp assignment per in-domain cell: spans x ~[4,31] with
# width-x overlap across narrow/mid/wide (synthetic demand, NOT measured)
QP_ASSIGN = {
    "HK-ST-05": 20, "HK-ST-06": 50, "HK-ST-08": 40, "HK-ST-09": 30,
    "HK-ST-11": 20, "HK-ST-13": 50, "HK-ST-16": 20, "HK-ST-19": 20,
    "HK-ST-12": 30, "HK-ST-15": 40, "HK-ST-18": 10, "HK-ST-27": 20,
    "HK-ST-24": 10, "HK-ST-21": 30, "HK-ST-22": 20, "HK-ST-30": 30,
    "HK-ST-28": 40, "HK-ST-25": 50,
}


def main():
    frz = pd.read_csv(os.path.join(SITES, "HONG_KONG_FORMAL_SAMPLE_FREEZE.csv"))
    rows = []
    for _, r in frz.iterrows():
        cid = r["cell_id"]
        if r["applicability_status"] != "in-domain":
            rows.append(dict(cell_id=cid, W=r["W"], geometry_type=r["geometry_type"],
                             sinuosity=r["sinuosity"], qp=None, x=None,
                             status="OOD/abstain (no simulation)",
                             robot_flows="", n_seeds_baseline=0, n_seeds_sweep=0))
            continue
        qp = QP_ASSIGN[cid]
        x = qp / r["W"]
        assert qp in PED_FLOWS, f"{cid} qp {qp} not in PED_FLOWS"
        assert x < X_CRIT, f"{cid} x {x} >= x_crit"
        rows.append(dict(cell_id=cid, W=r["W"], geometry_type=r["geometry_type"],
                         sinuosity=r["sinuosity"], qp=qp, x=round(x, 3),
                         status="in-domain (full protocol)",
                         robot_flows=",".join(str(f) for f in ROBOT_FLOWS_BASE),
                         n_seeds_baseline=N_SEEDS_BASELINE,
                         n_seeds_sweep=N_SEEDS_SWEEP))
    df = pd.DataFrame(rows)
    indom = df[df.status == "in-domain (full protocol)"]
    print(f"total combos: {len(df)} (in-domain {len(indom)}, OOD {len(df)-len(indom)})")
    print(f"\nx coverage (in-domain): min={indom.x.min():.1f} "
          f"max={indom.x.max():.1f}")
    print("\nx by width bin:")
    indom["wbin"] = pd.cut(indom.W, [1.5, 2.0, 2.4, 3.01],
                           labels=["narrow", "mid", "wide"])
    print(indom.groupby("wbin", observed=True)["x"].agg(
        ["count", "min", "max"]).round(1).to_string())
    print("\nqp histogram:", indom.qp.value_counts().sort_index().to_dict())

    df.to_csv(os.path.join(SITES, "HONG_KONG_EXPERIMENT_MATRIX.csv"), index=False)
    h = hashlib.sha256()
    with open(os.path.join(SITES, "HONG_KONG_EXPERIMENT_MATRIX.csv"), "rb") as f:
        h.update(f.read())
    sha = h.hexdigest().upper()
    meta = dict(
        n_combos=len(df), n_in_domain=int(len(indom)),
        n_ood=int(len(df) - len(indom)),
        ped_flows=PED_FLOWS, robot_flows_base=ROBOT_FLOWS_BASE,
        robot_flows_extended=ROBOT_FLOWS_EXTENDED,
        n_seeds_baseline=N_SEEDS_BASELINE, n_seeds_sweep=N_SEEDS_SWEEP,
        matrix_sha256=sha, demand_label="synthetic experimental demand",
    )
    with open(os.path.join(SITES, "hk_experiment_matrix_meta.json"), "w",
              encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    print(f"\nmatrix SHA-256: {sha}")
    print("wrote HONG_KONG_EXPERIMENT_MATRIX.csv + meta")


if __name__ == "__main__":
    main()
