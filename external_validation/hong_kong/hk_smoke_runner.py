# -*- coding: utf-8 -*-
"""
HK external test — SUMO-JuPedSim scenario runner (smoke test).

Reuses the validated pipeline engine (pipeline/sim/scripts):
  * config.py  -> PED / ROBOT / SIM / CONSTRAINTS (frozen robot & pedestrian
                  reference models, seed management, metric windows)
  * simulator.py -> _build_net / _build_routes / _build_sumocfg / _parse /
                    evaluate_constraints (validated output chain)

The ONLY change vs the frozen pipeline is that the JuPedSim walkable area is the
REAL footway polygon imported from CSDI (not the synthetic centerline buffer),
so the smoke test exercises true Hong Kong geometry end-to-end.

Does NOT modify any frozen D2 file.
"""
import json
import os
import subprocess
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))       # hong_kong -> external_validation -> repo
_PIPE = os.path.join(_REPO, "pipeline", "sim", "scripts")
sys.path.insert(0, _PIPE)

from config import PED, ROBOT, SIM, CONSTRAINTS, SUMO_BIN  # noqa: E402
import simulator as SIM_MOD  # noqa: E402

RUNS = os.path.join(_HERE, "runs", "smoke")
SCEN = os.path.join(_HERE, "scenarios")
os.makedirs(RUNS, exist_ok=True)
os.makedirs(SCEN, exist_ok=True)


def _write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _build_additional_real(scen_dir, poly_coords):
    """Real walkable-area polygon (local metric coords) as jupedsim.walkable_area."""
    # poly_coords: GeoJSON Polygon coordinates -> list of rings
    rings = poly_coords if isinstance(poly_coords, list) else [poly_coords]
    shape = " ".join(f"{x:.3f},{y:.3f}" for ring in rings for x, y in ring)
    add = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           "<additional>\n"
           f'  <poly id="walkable" type="jupedsim.walkable_area" '
           f'color="179,217,255" fill="1" layer="0" shape="{shape}"/>\n'
           "</additional>\n")
    p = os.path.join(scen_dir, "cell.add.xml")
    _write(p, add)
    return p


def build_scenario(scen_dir, W, L, centerline, poly_coords, qp, qr, seed):
    """Write all SUMO files into scen_dir (real polygon walkable area)."""
    net = SIM_MOD._build_net(scen_dir, W, L, centerline)
    add = _build_additional_real(scen_dir, poly_coords)
    rou = SIM_MOD._build_routes(scen_dir, W, L, qp, qr, PED, ROBOT, SIM,
                                SIM["bidirectional_split"], ROBOT["v_ref"], seed)
    cfg = SIM_MOD._build_sumocfg(scen_dir, net, rou, add, seed, SIM)
    return cfg


def run_cell(cell_id, W, L, centerline, poly_coords, qp, qr, seed,
             keep_scenario=False):
    scen_dir = os.path.join(SCEN, f"{cell_id}_qp{int(qp)}_qr{int(qr)}_s{seed}")
    os.makedirs(scen_dir, exist_ok=True)
    cfg = build_scenario(scen_dir, W, L, centerline, poly_coords, qp, qr, seed)
    log = os.path.join(scen_dir, "sumo.log")
    err = os.path.join(scen_dir, "sumo.err")
    cmd = [SUMO_BIN, "-c", cfg, "--no-warnings", "true",
           "--error-log", err, "--no-duration-log", "true",
           "--ignore-route-errors", "true",
           "--person-device.fcd.probability", "1.0",
           "--person-device.fcd.period", "1.0"]
    with open(log, "w", encoding="utf-8") as lf:
        r = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT,
                           timeout=SIM.get("timeout_sec", 300.0))
    if r.returncode != 0:
        detail = ""
        for name in ("sumo.err", "sumo.log"):
            p = os.path.join(scen_dir, name)
            if os.path.exists(p):
                with open(p, encoding="utf-8", errors="replace") as f:
                    detail += f"\n--- {name} ---\n" + f.read()[-3000:]
        raise RuntimeError(f"sumo failed rc={r.returncode}: {detail}")
    m = SIM_MOD._parse(scen_dir, W, SIM, centerline)
    metrics = dict(
        W=float(W), L=float(L), qp=float(qp), qr=float(qr), seed=int(seed),
        v_ref=float(ROBOT["v_ref"]), r_robot=float(ROBOT["radius"]),
        mean_speed=float(m[0]), speed_count=int(m[1]),
        mean_density=float(m[2]), inflow_ped=int(m[3]),
        outflow_ped=int(m[4]), flow_ratio=float(m[5]), timed_out=0,
        cell_id=cell_id,
    )
    if not keep_scenario:
        # keep the scenario dir for S1 audit only; otherwise leave for inspection
        pass
    return metrics


if __name__ == "__main__":
    # quick sanity: build + run HK-ST-01 with qr=0, qp=20, 1 seed
    geo = json.load(open(os.path.join(_HERE, "sites", "hk_cell_local_geometry.json"),
                         encoding="utf-8"))
    cell = geo["HK-ST-01"]
    cl = [tuple(p) for p in cell["centerline_local"]]
    poly = cell["walkable_polygon_local"]["coordinates"]
    m = run_cell("HK-ST-01", 2.331, 50.0, cl, poly, qp=20.0, qr=0.0, seed=0)
    print(json.dumps(m, indent=2))
