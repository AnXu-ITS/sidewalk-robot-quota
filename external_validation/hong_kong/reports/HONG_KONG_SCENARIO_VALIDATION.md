# Hong Kong External Test — Scenario Validation (Q5)

Construction and validation of the SUMO–JuPedSim scenario for the primary
straight cell **HK-ST-01**, importing the **real** CSDI footway polygon.

## 1. Reuse (no redevelopment)

The HK runner (`hk_smoke_runner.py`) reuses the frozen validated engine:

- `pipeline/sim/scripts/config.py` → `PED / ROBOT / SIM / CONSTRAINTS`
  (frozen robot = Camello-equivalent L=0.96×W=0.70 m, radius 0.48,
  v_ref=1.39 m/s = 5 km/h; pedestrian radius 0.25, v0_mean 1.25 m/s;
  SPEED_CALIB 1.094; dt=0.1, L=50, warmup/measure/tail = 100/240/100 s).
- `pipeline/sim/scripts/simulator.py` → `_build_net`, `_build_routes`,
  `_build_sumocfg`, `_parse`, `evaluate_constraints`.

**The only change** vs the frozen pipeline is the JuPedSim walkable area: it is
the **real imported polygon** (`jupedsim.walkable_area` from the CSDI footway)
instead of the synthetic centerline buffer. Robot/pedestrian reference models,
seeds, metric windows, and criteria code are **unchanged**. No frozen file was
modified (writes are confined to `external_validation/hong_kong/`).

## 2. Real geometry imported

- Centerline (local): `[(0,0), (50,0)]` — straight, L=50 m, W=2.331 m.
- Walkable polygon (local): the real `PG4019702R0312` footway clipped to the
  50 m segment and rigidly transformed (long axis → +x, start → origin).
- Polygon area = **116.571 m²** vs L·W = **116.55 m²** (ratio 1.00), bounds
  `[0.00, −1.171, 50.00, 1.174]` — the real polygon matches the synthetic
  rectangle to within 0.2%.

## 3. Synthetic-reference equivalence check

A frozen synthetic run (rectangle buffer) at the same operating point produced:

| metric | synthetic (frozen) | HK real polygon |
|---|---|---|
| mean_speed | 1.265 | 1.265 |
| mean_density | 0.113 | 0.113 |
| inflow / outflow | 80 / 80 | 80 / 80 |
| flow_ratio | 1.0 | 1.0 |

Identical to 3 decimals → the real geometry is correctly imported and the
measurement chain is intact.

## 4. Sumo/JuPedSim engine

- SUMO `1.27.1` with `--pedestrian.model jupedsim`, at
  `C:\Users\xuan1\sumo\bin\sumo.exe` (SUMO_HOME env empty; config default used).
- The "No connection between edge eA and eB" warnings are **expected by design**
  (mini source/exit waypoints are not network-connected; JuPedSim routes agents
  through the walkable polygon). JuPedSim spawn-retry warnings at the corridor
  ends ("too close to geometry boundaries") are inherent to the mini-edge
  design and are identical in the frozen synthetic case; metrics are unaffected
  (inflow = outflow).

## 5. Demand labeling (pedestrian flow)

No real observed pedestrian count was available for this round, so the demand
is **type 3 — synthetic experimental demand**, clearly labeled, using the
D2-validated in-domain level `q_p = 20 ped/min` (bidirectional split), giving
`x = q_p/W = 8.58 < 33.33` (in-domain). Robot flow uses the D2 `ROBOT_FLOWS`
grid (smoke uses q_r = 2).

## 6. Conclusion (Q5)

The HK scenario is a faithful reuse of the frozen engine with the real HK
walkable polygon imported; geometry and metrics are validated against the
frozen synthetic reference.
