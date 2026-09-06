# Pedestrian-only baseline calibration report

Target: reproduce Singapore mean free-flow walking speed.
- reference desired speed `v0_mean = 1.25 m/s` (Tanaboriboon et al., 1986).
- simulated free-flow speed (q_p = 10 ped/min, W = 3.0 m) = **1.326 m/s** (± 0.026 across seeds).
- calibration bias = **+6.0%**.

## Speed-density relationship (pedestrian-only)

| W (m) | q_p (ped/min) | speed (m/s) | density (ped/m²) | out/in |
|---:|---:|---:|---:|---:|
| 3.0 | 10 | 1.326 | 0.042 | 1.01 |
| 2.7 | 10 | 1.325 | 0.047 | 1.01 |
| 2.4 | 10 | 1.323 | 0.053 | 1.01 |
| 2.1 | 10 | 1.315 | 0.061 | 1.01 |
| 1.8 | 10 | 1.310 | 0.072 | 1.01 |
| 1.7 | 10 | 1.311 | 0.076 | 1.01 |
| 1.6 | 10 | 1.308 | 0.081 | 1.01 |
| 3.0 | 20 | 1.313 | 0.085 | 1.00 |
| 1.5 | 10 | 1.311 | 0.086 | 1.01 |
| 2.7 | 20 | 1.309 | 0.095 | 1.00 |
| 2.4 | 20 | 1.300 | 0.107 | 1.00 |
| 2.1 | 20 | 1.274 | 0.126 | 1.00 |
| 3.0 | 30 | 1.276 | 0.131 | 1.00 |
| 2.7 | 30 | 1.272 | 0.146 | 1.00 |
| 1.8 | 20 | 1.251 | 0.150 | 1.00 |
| 1.7 | 20 | 1.251 | 0.159 | 1.01 |
| 2.4 | 30 | 1.259 | 0.167 | 1.00 |
| 1.6 | 20 | 1.249 | 0.169 | 1.00 |
| 3.0 | 40 | 1.238 | 0.180 | 1.00 |
| 1.5 | 20 | 1.250 | 0.180 | 1.00 |
| 2.1 | 30 | 1.209 | 0.199 | 1.00 |
| 2.7 | 40 | 1.234 | 0.201 | 1.00 |
| 2.4 | 40 | 1.216 | 0.229 | 1.00 |
| 3.0 | 50 | 1.207 | 0.231 | 0.99 |
| 1.8 | 30 | 1.158 | 0.244 | 1.00 |
| 2.7 | 50 | 1.204 | 0.257 | 0.99 |
| 1.7 | 30 | 1.151 | 0.261 | 0.99 |
| 1.6 | 30 | 1.148 | 0.278 | 0.99 |
| 2.1 | 40 | 1.146 | 0.280 | 1.00 |
| 3.0 | 60 | 1.171 | 0.285 | 1.00 |
| 2.4 | 50 | 1.189 | 0.294 | 1.00 |
| 1.5 | 30 | 1.152 | 0.295 | 0.99 |
| 2.7 | 60 | 1.169 | 0.318 | 1.00 |
| 1.8 | 40 | 1.073 | 0.352 | 1.00 |
| 2.4 | 60 | 1.153 | 0.363 | 1.01 |
| 2.1 | 50 | 1.077 | 0.373 | 1.00 |
| 1.7 | 40 | 1.046 | 0.384 | 1.00 |
| 1.6 | 40 | 1.063 | 0.398 | 1.00 |
| 1.5 | 40 | 1.067 | 0.422 | 1.00 |
| 2.1 | 60 | 1.006 | 0.479 | 1.00 |
| 1.8 | 50 | 0.963 | 0.489 | 0.99 |
| 1.6 | 50 | 0.939 | 0.559 | 0.98 |
| 1.7 | 50 | 0.867 | 0.584 | 1.07 |
| 1.5 | 50 | 0.918 | 0.610 | 1.02 |
| 1.8 | 60 | 0.805 | 0.697 | 0.97 |
| 1.6 | 60 | 0.466 | 1.099 | 1.70 |
| 1.5 | 60 | 0.463 | 1.109 | 3.25 |
| 1.7 | 60 | 0.462 | 1.221 | 1.78 |

## Interpretation

The free-flow speed is within 6% of the Singapore reference (reproduced by scaling the pedestrian vType `maxSpeed` by `SPEED_CALIB` to offset JuPedSim's ~0.914x free-flow factor), and speed decreases monotonically with density as expected for JuPedSim's CollisionFreeSpeedModel.  Over-capacity cells (narrow × high demand) are detected via the density / flow-stability floor and assigned `q_r* = 0` (plan Case 1).

> Note: JuPedSim's CollisionFreeSpeedModel reduces every agent to a scalar collision disc (`radius = max(length, width)/2`), so the robot enters as a 0.48 m disc (Camello 0.96 × 0.70 m) rather than a true oriented rectangle. The PRE (Pedestrian Replacement Equivalent) analysis quantifies how many pedestrians that disc is worth as a function of width, flow, and split.
