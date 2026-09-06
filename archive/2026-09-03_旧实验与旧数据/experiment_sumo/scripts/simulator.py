"""
simulator.py  (SUMO-JuPedSim engine)
====================================
Simulation backend that runs a single sidewalk delivery-robot "cell" in
Eclipse SUMO with the JuPedSim pedestrian model (`--pedestrian.model jupedsim`),
replacing the Python social-force reimplementation.

The public API is kept IDENTICAL to the original simulator.py so that the rest
of the pipeline (worker.py / ground_truth.py / validate.py / sensitivity.py) is
reused unchanged:

    run_scenario(W, L, qp, qr, seed, PED, WALL, ROBOT, SIM,
                 bidirectional_split=None, v_ref_override=None,
                 radius_override=None, delta_v=0.10,
                 outflow_ratio_min=0.90, density_floor=1.20,
                 trace=False) -> metrics dict

    evaluate_constraints(metrics, baseline_vbar, ...) -> flags dict

Scenario layout (one straight sidewalk cell of length L, effective width W):

    eA (x=0)  ---- 2D JuPedSim walkable area (L x W) ----  eB (x=L)

  * Two short "mini" pedestrian edges eA/eB act purely as JuPedSim source /
    exit waypoints at the corridor ends.  They are NOT connected in the SUMO
    network; `--ignore-route-errors` lets JuPedSim route agents through the
    explicit walkable-area polygon, so pedestrians really move in 2D and mix
    bidirectionally (lateral spread across the width W).
  * pedestrians walk bidirectionally (split fraction eB -> eA);
  * the reference robot is a custom pedestrian vType with a larger footprint
    (JuPedSim radius = max(length,width)/2) and fixed speed v_ref;
  * robot personFlow enters at eA and walks to eB.

Metrics (matched to the original definitions):
  * mean_speed   = mean instantaneous pedestrian speed in the measurement zone
                   (x in measure_zone) during the measurement window (personfcd);
  * mean_density = mean pedestrian count in the zone / zone area (ped/m^2);
  * inflow_ped   = pedestrian departures in the measurement window (personinfo);
  * outflow_ped  = pedestrian arrivals in the measurement window (personinfo);
  * flow_ratio   = outflow_ped / inflow_ped.
"""

import math
import os
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import SUMO_BIN, NETCONVERT_BIN, PATHS, SPEED_CALIB  # noqa: E402


# ---------------------------------------------------------------------------
# scenario generation
# ---------------------------------------------------------------------------
def _write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _centerline_default(L):
    """Default straight centerline along +x (backward-compatible)."""
    return [(0.0, 0.0), (float(L), 0.0)]


def _centerline_cum(centerline):
    """Cumulative arclength over a centerline polyline."""
    cum = [0.0]
    for i in range(len(centerline) - 1):
        dx = centerline[i + 1][0] - centerline[i][0]
        dy = centerline[i + 1][1] - centerline[i][1]
        cum.append(cum[-1] + math.hypot(dx, dy))
    return cum


def _polyline_buffer(centerline, W):
    """Buffer a centerline polyline by W/2 on each side -> closed polygon.

    Returns a list of (x, y) polygon vertices (mitered at interior vertices).
    """
    h = W / 2.0
    left, right = [], []
    n = len(centerline)
    for i, (x, y) in enumerate(centerline):
        if i == 0:
            tx = centerline[1][0] - x
            ty = centerline[1][1] - y
        elif i == n - 1:
            tx = x - centerline[i - 1][0]
            ty = y - centerline[i - 1][1]
        else:
            tx = centerline[i + 1][0] - centerline[i - 1][0]
            ty = centerline[i + 1][1] - centerline[i - 1][1]
        ln = math.hypot(tx, ty) or 1.0
        tx /= ln
        ty /= ln
        left.append((x - ty * h, y + tx * h))
        right.append((x + ty * h, y - tx * h))
    return left + list(reversed(right))


def _arclength(centerline, cum, x, y):
    """Project point (x, y) onto the centerline; return along-polyline distance."""
    best_s = 0.0
    best_d2 = float("inf")
    for i in range(len(centerline) - 1):
        x0, y0 = centerline[i]
        x1, y1 = centerline[i + 1]
        dx = x1 - x0
        dy = y1 - y0
        seg2 = dx * dx + dy * dy
        t = ((x - x0) * dx + (y - y0) * dy) / seg2 if seg2 > 0 else 0.0
        t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
        px = x0 + t * dx
        py = y0 + t * dy
        d2 = (x - px) ** 2 + (y - py) ** 2
        if d2 < best_d2:
            best_d2 = d2
            best_s = cum[i] + t * (cum[i + 1] - cum[i])
    return best_s


def _build_net(scen_dir, W, L, centerline=None):
    # Two short mini edges at the corridor ends.  They are only waypoints for
    # JuPedSim (source/exit); agents traverse the walkable area between them.
    if centerline is None:
        centerline = _centerline_default(L)
    (x0, y0) = centerline[0]
    (x1, y1) = centerline[-1]
    # local tangent at each end for the mini-edge stubs
    t0x = centerline[1][0] - x0
    t0y = centerline[1][1] - y0
    t0n = math.hypot(t0x, t0y) or 1.0
    t0x /= t0n
    t0y /= t0n
    t1x = x1 - centerline[-2][0]
    t1y = y1 - centerline[-2][1]
    t1n = math.hypot(t1x, t1y) or 1.0
    t1x /= t1n
    t1y /= t1n
    nodes = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<nodes>\n"
        f'  <node id="a0" x="{x0:.3f}" y="{y0:.3f}"/>\n'
        f'  <node id="a1" x="{x0 + 0.5 * t0x:.3f}" y="{y0 + 0.5 * t0y:.3f}"/>\n'
        f'  <node id="b0" x="{x1 - 0.5 * t1x:.3f}" y="{y1 - 0.5 * t1y:.3f}"/>\n'
        f'  <node id="b1" x="{x1:.3f}" y="{y1:.3f}"/>\n'
        "</nodes>\n"
    )
    edges = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<edges>\n"
        '  <edge id="eA" from="a0" to="a1" numLanes="1" spreadType="center">\n'
        f'    <lane index="0" allow="pedestrian" width="{W:.3f}" speed="2.0"/>\n'
        "  </edge>\n"
        '  <edge id="eB" from="b0" to="b1" numLanes="1" spreadType="center">\n'
        f'    <lane index="0" allow="pedestrian" width="{W:.3f}" speed="2.0"/>\n'
        "  </edge>\n"
        "</edges>\n"
    )
    nodes_path = os.path.join(scen_dir, "nodes.nod.xml")
    edges_path = os.path.join(scen_dir, "edges.edg.xml")
    net_path = os.path.join(scen_dir, "cell.net.xml")
    _write(nodes_path, nodes)
    _write(edges_path, edges)

    log = os.path.join(scen_dir, "netconvert.log")
    with open(log, "w", encoding="utf-8") as lf:
        r = subprocess.run(
            [NETCONVERT_BIN, "--node-files", nodes_path,
             "--edge-files", edges_path, "--output-file", net_path,
             "--no-turnarounds", "true",
             "--offset.disable-normalization", "true"],
            stdout=lf, stderr=subprocess.STDOUT,
        )
    if r.returncode != 0 or not os.path.exists(net_path):
        with open(log, encoding="utf-8", errors="replace") as lf:
            raise RuntimeError("netconvert failed:\n" + lf.read())
    return net_path


def _build_additional(scen_dir, W, L, centerline=None):
    """Explicit JuPedSim walkable-area polygon along the cell centerline.

    JuPedSim's geometry generation also derives polygons from pedestrian lanes,
    but the effective width W is the key experimental variable, so we pin the
    walkable area to the exact polyline buffer (rectangle for a straight cell)
    to make the width unambiguous.
    """
    if centerline is None:
        centerline = _centerline_default(L)
    poly = _polyline_buffer(centerline, W)
    shape = " ".join(f"{x:.3f},{y:.3f}" for x, y in poly)
    add = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<additional>\n"
        f'  <poly id="walkable" type="jupedsim.walkable_area" '
        f'color="179,217,255" fill="1" layer="0" shape="{shape}"/>\n'
        "</additional>\n"
    )
    add_path = os.path.join(scen_dir, "cell.add.xml")
    _write(add_path, add)
    return add_path


def _build_routes(scen_dir, W, L, qp, qr, PED, ROBOT, SIM, split, v_ref, seed):
    warmup = SIM["warmup"]
    measure = SIM["measure"]
    T_flow = warmup + measure          # flow stops at the end of the window

    ped_ab_rate = qp * (1.0 - split)   # ped/min in +x (eA -> eB)
    ped_ba_rate = qp * split           # ped/min in -x (eB -> eA)
    rob_rate = qr                      # robot/min (eA -> eB)

    # desired pedestrian speed ~ N(v0_mean, v0_std) within [v0_min, v0_max].
    # SUMO: actual speed = maxSpeed * speedFactor, so maxSpeed carries the mean
    # and the speedFactor distribution the relative spread.  maxSpeed is scaled
    # by SPEED_CALIB to offset JuPedSim's free-flow shortfall.
    v0_mean = PED["v0_mean"]
    ped_max_speed = v0_mean * SPEED_CALIB
    rob_max_speed = v_ref * SPEED_CALIB
    fdev = PED["v0_std"] / v0_mean
    fmin = PED["v0_min"] / v0_mean
    fmax = PED["v0_max"] / v0_mean
    ped_sf = f"normc(1.0000,{fdev:.4f},{fmin:.4f},{fmax:.4f})"

    # Person flows with a <walk> between the two mini edges.  personsPerHour
    # gives constant-rate (deterministic) departures, matching the ped/min rate.
    def personflow_xml(fid, typ, fr, to, rate_per_min):
        if rate_per_min <= 0:
            return ""
        pph = rate_per_min * 60.0
        return (f'  <personFlow id="{fid}" type="{typ}" begin="0.0" '
                f'end="{T_flow:.1f}" personsPerHour="{pph:.4f}">\n'
                f'    <walk from="{fr}" to="{to}"/>\n'
                f'  </personFlow>\n')

    routes = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<routes>\n"
        f'  <vType id="ped" vClass="pedestrian" length="{PED["length"]:.2f}" '
        f'width="{PED["width"]:.2f}" maxSpeed="{ped_max_speed:.3f}" '
        f'speedFactor="{ped_sf}"/>\n'
        f'  <vType id="robot" vClass="pedestrian" length="{ROBOT["length"]:.2f}" '
        f'width="{ROBOT["width"]:.2f}" maxSpeed="{rob_max_speed:.3f}" '
        f'speedFactor="1.0"/>\n'
        + personflow_xml("pfAB", "ped", "eA", "eB", ped_ab_rate)
        + personflow_xml("pfBA", "ped", "eB", "eA", ped_ba_rate)
        + personflow_xml("pfRob", "robot", "eA", "eB", rob_rate)
        + "</routes>\n"
    )
    rou_path = os.path.join(scen_dir, "cell.rou.xml")
    _write(rou_path, routes)
    return rou_path


def _build_sumocfg(scen_dir, net_path, rou_path, add_path, seed, SIM):
    T = SIM["warmup"] + SIM["measure"] + SIM["tail"]
    dt = SIM["dt"]
    cfg = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<configuration>\n"
        "  <input>\n"
        f'    <net-file value="{net_path}"/>\n'
        f'    <route-files value="{rou_path}"/>\n'
        f'    <additional-files value="{add_path}"/>\n'
        "  </input>\n"
        "  <processing>\n"
        '    <pedestrian.model value="jupedsim"/>\n'
        "  </processing>\n"
        "  <time>\n"
        '    <begin value="0"/>\n'
        f'    <end value="{T:.1f}"/>\n'
        f'    <step-length value="{dt:.2f}"/>\n'
        "  </time>\n"
        "  <output>\n"
        # NOTE: person-fcd only emits records when a regular <fcd-output> is
        # also present (SUMO quirk), so keep the (empty) vehicle fcd too.
        f'    <personinfo-output value="{os.path.join(scen_dir, "personinfo.xml")}"/>\n'
        f'    <person-fcd-output value="{os.path.join(scen_dir, "personfcd.xml")}"/>\n'
        f'    <fcd-output value="{os.path.join(scen_dir, "fcd.xml")}"/>\n'
        "  </output>\n"
        "  <random_number>\n"
        f'    <seed value="{seed}"/>\n'
        "  </random_number>\n"
        "</configuration>\n"
    )
    cfg_path = os.path.join(scen_dir, "cell.sumocfg")
    _write(cfg_path, cfg)
    return cfg_path


# ---------------------------------------------------------------------------
# output parsing
# ---------------------------------------------------------------------------
def _parse(metric_dir, W, SIM, centerline=None):
    warmup = SIM["warmup"]
    measure = SIM["measure"]
    zlo, zhi = SIM["measure_zone"]
    zone_area = (zhi - zlo) * W
    if centerline is None:
        centerline = _centerline_default(SIM["L"])
    cum = _centerline_cum(centerline)

    # ---- personfcd: speed + density in the measurement zone ---------------
    pfcd_path = os.path.join(metric_dir, "personfcd.xml")
    speed_sum = 0.0
    speed_cnt = 0
    dens_sum = 0.0
    dens_cnt = 0
    if os.path.exists(pfcd_path):
        for _, ts in ET.iterparse(pfcd_path, events=("end",)):
            if ts.tag != "timestep":
                continue
            t = float(ts.get("time"))
            if t < warmup or t >= warmup + measure:
                ts.clear()
                continue
            in_zone = 0
            for v in ts.iter("person"):
                if v.get("type") != "ped":
                    continue
                x = float(v.get("x"))
                y = float(v.get("y"))
                s = _arclength(centerline, cum, x, y)
                if zlo <= s <= zhi:
                    in_zone += 1
                    speed_sum += float(v.get("speed"))
                    speed_cnt += 1
            dens_sum += in_zone / zone_area
            dens_cnt += 1
            ts.clear()

    mean_speed = speed_sum / speed_cnt if speed_cnt > 0 else 0.0
    mean_density = dens_sum / dens_cnt if dens_cnt > 0 else 0.0

    # ---- personinfo: inflow / outflow ------------------------------------
    pinfo_path = os.path.join(metric_dir, "personinfo.xml")
    inflow_ped = 0
    outflow_ped = 0
    if os.path.exists(pinfo_path):
        for _, pi in ET.iterparse(pinfo_path, events=("end",)):
            if pi.tag != "personinfo":
                continue
            if pi.get("type") != "ped":
                pi.clear()
                continue
            depart = float(pi.get("depart"))
            walk = pi.find("walk")
            arr = walk.get("arrival") if walk is not None else None
            arrival = float(arr) if arr is not None else -1.0
            if warmup <= depart < warmup + measure:
                inflow_ped += 1
            if arrival >= 0.0 and warmup <= arrival < warmup + measure:
                outflow_ped += 1
            pi.clear()

    flow_ratio = outflow_ped / inflow_ped if inflow_ped > 0 else 1.0
    return mean_speed, speed_cnt, mean_density, inflow_ped, outflow_ped, flow_ratio


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------
def run_scenario(W, L, qp, qr, seed, PED, WALL, ROBOT, SIM,
                 bidirectional_split=None, v_ref_override=None,
                 radius_override=None, delta_v=0.10,
                 outflow_ratio_min=0.90, density_floor=1.20,
                 centerline=None, trace=False):
    split = SIM["bidirectional_split"] if bidirectional_split is None else bidirectional_split
    v_ref = ROBOT["v_ref"] if v_ref_override is None else v_ref_override
    r_robot = ROBOT["radius"] if radius_override is None else radius_override

    # The robot keeps its REAL anisotropic footprint (Camello length x width)
    # on the vType; JuPedSim's CollisionFreeSpeedModel reduces it to a scalar
    # collision radius = max(length, width) / 2 (= length/2 for the robot).
    # Only an explicit radius_override (sensitivity) forces a circular disc.
    rob = dict(ROBOT)
    rob["v_ref"] = v_ref
    if radius_override is not None:
        rob["length"] = 2.0 * radius_override
        rob["width"] = 2.0 * radius_override

    os.makedirs(PATHS["tmp"], exist_ok=True)
    # NOTE: avoid tempfile.mkdtemp — directories it creates cannot be written to
    # under the workspace sandbox (filesystem-policy quirk); use os.makedirs with
    # a uuid-derived name instead (same effect, sandbox-friendly).
    scen_dir = os.path.join(PATHS["tmp"], "sumo_" + uuid.uuid4().hex)
    os.makedirs(scen_dir, exist_ok=False)

    try:
        net_path = _build_net(scen_dir, W, L, centerline)
        add_path = _build_additional(scen_dir, W, L, centerline)
        rou_path = _build_routes(scen_dir, W, L, qp, qr, PED, rob, SIM, split, v_ref, seed)
        cfg_path = _build_sumocfg(scen_dir, net_path, rou_path, add_path, seed, SIM)

        log = os.path.join(scen_dir, "sumo.log")
        with open(log, "w", encoding="utf-8") as lf:
            r = subprocess.run(
                [SUMO_BIN, "-c", cfg_path, "--no-warnings", "true",
                 "--error-log", os.path.join(scen_dir, "sumo.err"),
                 "--no-duration-log", "true",
                 "--ignore-route-errors", "true",
                 "--person-device.fcd.probability", "1.0",
                 "--person-device.fcd.period", "1.0"],
                stdout=lf, stderr=subprocess.STDOUT,
            )
        if r.returncode != 0:
            detail = ""
            for name in ("sumo.err", "sumo.log"):
                p = os.path.join(scen_dir, name)
                if os.path.exists(p):
                    with open(p, encoding="utf-8", errors="replace") as f:
                        detail += f"\n--- {name} ---\n" + f.read()
            raise RuntimeError(
                f"sumo failed (rc={r.returncode}) for W={W} qp={qp} qr={qr} "
                f"seed={seed}: {detail}")

        (mean_speed, speed_cnt, mean_density,
         inflow_ped, outflow_ped, flow_ratio) = _parse(scen_dir, W, SIM, centerline)

        metrics = {
            "W": float(W), "L": float(L), "qp": float(qp), "qr": float(qr),
            "seed": int(seed), "v_ref": float(v_ref), "r_robot": float(r_robot),
            "mean_speed": float(mean_speed), "speed_count": int(speed_cnt),
            "mean_density": float(mean_density),
            "inflow_ped": int(inflow_ped), "outflow_ped": int(outflow_ped),
            "flow_ratio": float(flow_ratio),
        }
        return metrics
    finally:
        # keep the scenario dir on failure for debugging; otherwise clean up
        if "metrics" not in locals():
            pass  # keep on error (raised above)
        else:
            import shutil
            shutil.rmtree(scen_dir, ignore_errors=True)


def evaluate_constraints(metrics, baseline_vbar, delta_v=0.10,
                         outflow_ratio_min=0.90, outflow_ratio_max=1.20,
                         density_floor=1.20):
    """Convert one run's metrics into per-seed pedestrian-service flags.

    flow_ok is TWO-sided: with SUMO's spawn-blocking, a jam shows up as
    flow_ratio >> 1 (inflow collapses while pre-jam arrivals still land),
    which is the SUMO analogue of the original throughput collapse.
    """
    Rv = metrics["mean_speed"] / baseline_vbar if baseline_vbar > 0 else 1.0
    speed_ok = Rv >= (1.0 - delta_v)
    fr = metrics["flow_ratio"]
    flow_ok = outflow_ratio_min <= fr <= outflow_ratio_max
    density_ok = metrics["mean_density"] <= density_floor
    return {
        "Rv": float(Rv),
        "speed_ok": bool(speed_ok),
        "flow_ok": bool(flow_ok),
        "density_ok": bool(density_ok),
        "pass": bool(speed_ok and flow_ok and density_ok),
    }


if __name__ == "__main__":
    # quick single-run smoke test
    import json
    from config import PED, WALL, ROBOT, SIM
    m = run_scenario(2.4, 50.0, 40.0, 5.0, 0, PED, WALL, ROBOT, SIM)
    print(json.dumps(m, indent=2))
