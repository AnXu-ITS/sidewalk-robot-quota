"""
simulator.py
============
Microscopic 2-D mixed pedestrian--robot flow simulator.

Pedestrians follow a social-force model (Helbing & Molnar 1995):
    m dv/dt = (v0 e - v)/tau   (driving)
            + sum_j A exp((r_ij - d_ij)/B) n_ij w_ij   (social repulsion)
            + contact force on overlap
            + wall repulsion

The reference delivery robot is modelled as a *traffic-capacity proxy* per the
experiment plan (section 12): it holds a fixed lateral lane and applies simple
longitudinal collision-free speed control (it stops / matches the leader when a
pedestrian or another robot is directly ahead).  Pedestrians yield to it via a
stronger repulsion, so the robot is a moving hard obstacle occupying sidewalk
capacity rather than a navigation agent.

Agent storage uses preallocated numpy buffers (with compaction on exit) so the
per-step cost stays vectorised and fast enough to farm out tens of thousands of
short runs to a multiprocessing pool.

`run_scenario` is the only public entry point and is picklable.
"""

import numpy as np


def run_scenario(W, L, qp, qr, seed, PED, WALL, ROBOT, SIM,
                 bidirectional_split=None, v_ref_override=None,
                 radius_override=None, delta_v=0.10,
                 outflow_ratio_min=0.90, density_floor=1.20,
                 trace=False):
    rng = np.random.default_rng(seed)

    dt = SIM["dt"]
    warmup = SIM["warmup"]
    measure = SIM["measure"]
    zone = SIM["measure_zone"]
    split = SIM["bidirectional_split"] if bidirectional_split is None else bidirectional_split

    v_ref = ROBOT["v_ref"] if v_ref_override is None else v_ref_override
    r_robot = ROBOT["radius"] if radius_override is None else radius_override

    n_steps = int(round((warmup + measure) / dt))
    warmup_steps = int(round(warmup / dt))
    measure_steps = n_steps - warmup_steps

    ped_rate = qp / 60.0
    rate_plus = ped_rate * (1.0 - split)
    rate_minus = ped_rate * split
    robot_rate = qr / 60.0

    y_lane = ROBOT["lane_frac"] * W
    rp = PED["radius"]

    # jam-capacity bound (keeps the O(n^2) cost bounded in congested cells;
    # density 1.6 ped/m^2 already exceeds the 1.2 floor so a capped jam is
    # still correctly flagged as over capacity)
    N_max = int(1.6 * L * W) + 10

    # ---- preallocated agent buffers --------------------------------------
    cap = int(np.ceil((ped_rate + robot_rate) * (warmup + measure) * 3.0 + 200))
    cap = max(cap, 64)
    pos = np.zeros((cap, 2))
    vel = np.zeros((cap, 2))
    v0 = np.zeros(cap)
    rad = np.zeros(cap)
    mass = np.zeros(cap)
    kind = np.zeros(cap, dtype=np.int8)   # 0 ped+, 1 ped-, 2 robot
    dirm = np.zeros(cap)
    n = 0

    A_r = ROBOT.get("A", 3000.0)
    B_r = ROBOT.get("B", 0.08)
    lam = PED["lam"]
    tau = PED["tau"]
    a_max = PED["a_max"]
    v_max = PED["v_max"]

    speed_sum = 0.0
    speed_cnt = 0
    dens_sum = 0.0
    dens_cnt = 0
    inflow_ped = 0
    outflow_ped = 0
    zone_area = (zone[1] - zone[0]) * W
    trace_hist = []

    for step in range(n_steps):
        in_measure = step >= warmup_steps

        # ---- arrivals -----------------------------------------------------
        if n < N_max:
            n_plus = rng.poisson(rate_plus * dt)
            n_minus = rng.poisson(rate_minus * dt)
            n_rob = rng.poisson(robot_rate * dt)
        else:
            n_plus = n_minus = n_rob = 0
        n_new = n_plus + n_minus + n_rob
        if n_new > 0:
            if n + n_new > cap:
                cap = int(cap * 1.6 + n_new + 50)
                pos = np.resize(pos, (cap, 2)); vel = np.resize(vel, (cap, 2))
                v0 = np.resize(v0, cap); rad = np.resize(rad, cap)
                mass = np.resize(mass, cap); kind = np.resize(kind, cap)
                dirm = np.resize(dirm, cap)
            i0 = n
            for _ in range(n_plus):
                pos[n] = (0.0, rng.uniform(rp, W - rp))
                v0[n] = float(np.clip(rng.normal(PED["v0_mean"], PED["v0_std"]),
                                      PED["v0_min"], PED["v0_max"]))
                rad[n] = rp; mass[n] = PED["mass"]; kind[n] = 0; dirm[n] = 1.0
                n += 1
            for _ in range(n_minus):
                pos[n] = (L, rng.uniform(rp, W - rp))
                v0[n] = float(np.clip(rng.normal(PED["v0_mean"], PED["v0_std"]),
                                      PED["v0_min"], PED["v0_max"]))
                rad[n] = rp; mass[n] = PED["mass"]; kind[n] = 1; dirm[n] = -1.0
                n += 1
            for _ in range(n_rob):
                pos[n] = (0.0, y_lane)
                v0[n] = v_ref; rad[n] = r_robot; mass[n] = ROBOT["mass"]
                kind[n] = 2; dirm[n] = 1.0
                n += 1

        if in_measure:
            inflow_ped += n_plus + n_minus

        if trace and step % 200 == 0:
            nr = int((kind[:n] == 2).sum())
            np_ = int((kind[:n] != 2).sum())
            rx_mean = float(pos[:n][kind[:n] == 2, 0].mean()) if nr else -1.0
            trace_hist.append((step * dt, np_, nr, rx_mean))

        if n == 0:
            continue

        # active slice
        P = pos[:n]; V = vel[:n]; V0 = v0[:n]; R = rad[:n]
        M = mass[:n]; K = kind[:n]; D = dirm[:n]

        # ---- pairwise social / contact forces -----------------------------
        dx = P[:, 0][:, None] - P[:, 0][None, :]
        dy = P[:, 1][:, None] - P[:, 1][None, :]
        dist2 = dx * dx + dy * dy
        np.fill_diagonal(dist2, np.inf)
        dist = np.sqrt(dist2)
        dist_safe = np.where(dist < 1e-6, 1.0, dist)
        nx = dx / dist_safe
        ny = dy / dist_safe
        coinc = dist < 1e-6
        nx = np.where(coinc, 1.0, nx)
        ny = np.where(coinc, 0.0, ny)

        rsum = R[:, None] + R[None, :]
        overlap = rsum - dist

        is_robot_row = (K == 2)[:, None]
        is_robot_col = (K == 2)[None, :]

        Aj = np.where(is_robot_col, A_r, PED["A"])
        Bj = np.where(is_robot_col, B_r, PED["B"])

        arg = np.clip(overlap / Bj, -30.0, 0.5)
        mag = Aj * np.exp(arg)
        mag = mag + np.where(overlap > 0, PED["k_contact"] * overlap, 0.0)

        cosphi = -nx * D[:, None]
        w = lam + (1.0 - lam) * (1.0 + cosphi) / 2.0
        w = np.where(is_robot_col, 1.0, w)
        w = np.where(overlap > 0, 1.0, w)

        Fx = (mag * w * nx).sum(axis=1)
        Fy = (mag * w * ny).sum(axis=1)

        # ---- wall forces --------------------------------------------------
        Fwall_y = np.zeros(n)
        dw = P[:, 1]
        Fwall_y += WALL["A"] * np.exp(np.clip((R - dw) / WALL["B"], -30.0, 0.5))
        Fwall_y += np.where(R - dw > 0, WALL["k_contact"] * (R - dw), 0.0)
        dw = W - P[:, 1]
        Fwall_y -= WALL["A"] * np.exp(np.clip((R - dw) / WALL["B"], -30.0, 0.5))
        Fwall_y -= np.where(R - dw > 0, WALL["k_contact"] * (R - dw), 0.0)

        # ---- integrate pedestrians ---------------------------------------
        is_ped = K != 2
        acc = np.zeros((n, 2))
        acc[is_ped, 0] = Fx[is_ped] / M[is_ped]
        acc[is_ped, 1] = (Fy[is_ped] + Fwall_y[is_ped]) / M[is_ped]
        acc[is_ped, 0] += (V0[is_ped] * D[is_ped] - V[is_ped, 0]) / tau
        acc[is_ped, 1] += (0.0 - V[is_ped, 1]) / tau

        amag = np.linalg.norm(acc, axis=1)
        too = amag > a_max
        if too.any():
            acc[too] = acc[too] / amag[too, None] * a_max

        newV = V.copy()
        newV[is_ped] = V[is_ped] + acc[is_ped] * dt
        vmag = np.linalg.norm(newV, axis=1)
        over = vmag > v_max
        if over.any():
            newV[over] = newV[over] / vmag[over, None] * v_max

        newP = P.copy()
        newP[is_ped] = P[is_ped] + newV[is_ped] * dt
        newP[:, 1] = np.clip(newP[:, 1], R, W - R)

        # ---- robots: lane + longitudinal control + lateral yield ----------
        rob_idx = np.where(K == 2)[0]
        if len(rob_idx) > 0:
            for kk in range(len(rob_idx)):
                ri = rob_idx[kk]
                rx = newP[ri, 0]
                ry = newP[ri, 1]
                y0 = ROBOT["lane_frac"] * W
                ahead = (P[:, 0] - rx > 0) & (P[:, 0] - rx <= ROBOT["lookahead"])
                cand_idx = np.where(ahead)[0]
                if len(cand_idx):
                    gaps = P[cand_idx, 0] - rx
                    j = cand_idx[np.argmin(gaps)]
                    gap = float(gaps[np.argmin(gaps)])
                    # longitudinal target
                    if gap <= ROBOT["d_stop"]:
                        target = 0.0
                    elif gap <= ROBOT["d_follow"]:
                        lead = V[j, 0]
                        target = min(v_ref, max(ROBOT.get("v_creep", 0.25), lead))
                    else:
                        target = v_ref
                    # lateral yield: step aside if a pedestrian is in the path
                    if gap <= ROBOT["d_yield"] and abs(P[j, 1] - ry) < (R[j] + r_robot):
                        if P[j, 1] > ry:
                            y_target = ry - ROBOT["yield_frac"] * W
                        else:
                            y_target = ry + ROBOT["yield_frac"] * W
                    else:
                        y_target = y0
                else:
                    target = v_ref
                    y_target = y0
                y_target = float(min(max(y_target, r_robot), W - r_robot))

                rvx = newV[ri, 0] + (target - newV[ri, 0]) / ROBOT["tau"] * dt
                newV[ri, 0] = float(np.clip(rvx, 0.0, v_ref))
                newV[ri, 1] = (y_target - ry) / ROBOT["tau_lat"]
                newP[ri, 0] = rx + newV[ri, 0] * dt
                newP[ri, 1] = ry + newV[ri, 1] * dt
                newP[ri, 1] = float(min(max(newP[ri, 1], r_robot), W - r_robot))

        # ---- measurement --------------------------------------------------
        if in_measure:
            in_zone = is_ped & (newP[:, 0] >= zone[0]) & (newP[:, 0] <= zone[1])
            if in_zone.any():
                sp = np.linalg.norm(newV[in_zone], axis=1)
                speed_sum += float(sp.sum())
                speed_cnt += int(in_zone.sum())
            dens_sum += float(in_zone.sum()) / zone_area
            dens_cnt += 1

        # ---- removal ------------------------------------------------------
        if in_measure:
            exited = ((K == 0) & (newP[:, 0] > L)) | ((K == 1) & (newP[:, 0] < 0.0))
            outflow_ped += int(exited.sum())
        keep = ~(((K == 0) & (newP[:, 0] > L)) |
                 ((K == 1) & (newP[:, 0] < 0.0)) |
                 ((K == 2) & (newP[:, 0] > L)))
        if not keep.all():
            keep_idx = np.where(keep)[0]
            m = keep_idx.size
            pos[:m] = newP[keep_idx]; vel[:m] = newV[keep_idx]
            v0[:m] = V0[keep_idx]; rad[:m] = R[keep_idx]
            mass[:m] = M[keep_idx]; kind[:m] = K[keep_idx]; dirm[:m] = D[keep_idx]
            n = m
        else:
            pos[:n] = newP; vel[:n] = newV

    mean_speed = speed_sum / speed_cnt if speed_cnt > 0 else 0.0
    mean_density = dens_sum / dens_cnt if dens_cnt > 0 else 0.0
    flow_ratio = outflow_ped / inflow_ped if inflow_ped > 0 else 1.0

    return {
        "W": float(W), "L": float(L), "qp": float(qp), "qr": float(qr),
        "seed": int(seed), "v_ref": float(v_ref), "r_robot": float(r_robot),
        "mean_speed": float(mean_speed), "speed_count": int(speed_cnt),
        "mean_density": float(mean_density),
        "inflow_ped": int(inflow_ped), "outflow_ped": int(outflow_ped),
        "flow_ratio": float(flow_ratio),
    } | ({"trace": trace_hist} if trace else {})


def evaluate_constraints(metrics, baseline_vbar, delta_v=0.10,
                         outflow_ratio_min=0.90, density_floor=1.20):
    """Convert one run's metrics into per-seed pedestrian-service flags."""
    Rv = metrics["mean_speed"] / baseline_vbar if baseline_vbar > 0 else 1.0
    speed_ok = Rv >= (1.0 - delta_v)
    flow_ok = metrics["flow_ratio"] >= outflow_ratio_min
    density_ok = metrics["mean_density"] <= density_floor
    return {
        "Rv": float(Rv),
        "speed_ok": bool(speed_ok),
        "flow_ok": bool(flow_ok),
        "density_ok": bool(density_ok),
        "pass": bool(speed_ok and flow_ok and density_ok),
    }
