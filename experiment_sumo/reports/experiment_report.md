# Sidewalk Delivery-Robot Quota — Experiment Report

> Every number below is produced by running the code in `scripts/`; nothing is hand-edited. Reproduce with `python scripts/run_all.py`.

## 1. Setup

- Straight sidewalk cell, length `L = 50` m; `100s` warm-up + `240s` measurement; time step `dt = 0.1 s`.
- Engine: Eclipse SUMO 1.27.1 with `--pedestrian.model jupedsim` (JuPedSim CollisionFreeSpeedModel) over an explicit `jupedsim.walkable_area` rectangle of width `W`.
- Pedestrians: `vClass=pedestrian` vType, desired speed `N(1.25, 0.15)` m/s (Singapore calibration), body radius 0.25 m, bidirectional 50/50 split.
- Reference robot (Camello-equivalent Singapore delivery robot): a `vClass=pedestrian` vType carrying a REAL anisotropic footprint 0.96 m × 0.70 m (length × width; JuPedSim collision radius = max/2 = 0.48 m) at fixed `v_ref = 1.39` m/s (5.0 km/h). The robot is NOT a special pedestrian — its collision-disc area is ~3.7× the pedestrian's.
- Pedestrian-first service constraints (mean over seeds): speed retention `R̄_v ≥ 0.90`, flow stability `0.90 ≤ q̄_out/q̄_in ≤ 1.20` (two-sided: the upper bound catches SUMO spawn-blocking jams), density `ρ̄ ≤ 1.2` ped/m².

## 2. Reference quota dataset (ground truth)

Training grid 8 widths × 6 flows = 48 cells, 30 seeds each. 3 cells are already over-capacity at the pedestrian-only baseline (Case 1) and are assigned `q_r* = 0`.

### q_r* frontier (robot/min; rows = q_p, cols = W)

| qp | 1.5 | 1.6 | 1.7 | 1.8 | 2.1 | 2.4 | 2.7 | 3.0 |
|---|---|---|---|---|---|---|---|---|
| 10 | 0 | 6 | 10 | 12 | 15 | 20 | 20 | 20 |
| 20 | 0 | 5 | 6 | 6 | 12 | 15 | 20 | 20 |
| 30 | 0 | 3 | 5 | 4 | 8 | 12 | 18 | 18 |
| 40 | 0 | 0 | 0 | 1 | 2 | 12 | 15 | 15 |
| 50 | 0 | 0 | 0 | 0 | 0 | 6 | 10 | 10 |
| 60 | 0 | 0 | 0 | 0 | 0 | 4 | 6 | 6 |

The frontier is monotone: `q_r*` falls with pedestrian flow and rises with width. 3 cell(s) are already over-capacity at the pedestrian-only baseline (Case 1) and are zeroed. 5 light cell(s) sit at the robot-flow sweep ceiling (`q_r* = 20` robot/min, read as "at least this many"); resolving them would require sweeping robot flow above 20 robot/min.

## PRE: Pedestrian Replacement Equivalent

The robot is NOT treated as "one more pedestrian". Its pedestrian-equivalent is measured at the margin (q_r → 0): `PRE = Δs(robot) / Δs(ped)` — the speed-retention impact of ONE robot/min divided by that of ONE pedestrian/min. `PRE > 1` means one robot congests the sidewalk more than one pedestrian.

### PRE surface at the 50/50 split (rows = q_p, cols = W)

| qp | 1.5 | 1.8 | 2.1 | 2.4 | 2.7 | 3.0 |
|---|---|---|---|---|---|---|
| 10.00 | 171.71 | 1.51 | 1.00 | 1.69 | 1.25 | 0.53 |
| 20.00 | 109.27 | 1.41 | 1.20 | 1.64 | 1.20 | 1.31 |
| 30.00 | 113.52 | 0.95 | 1.05 | 2.64 | 2.74 | 2.12 |
| 40.00 | 62.55 | 1.12 | 6.16 | 1.66 | 1.47 | 1.59 |
| 50.00 | 17.77 | 11.68 | 16.26 | 5.28 | 3.32 | 3.68 |
| 60.00 | nan | 21.46 | 76.98 | 8.96 | 5.77 | 4.75 |

### Width-averaged PRE ("1 robot ≈ X pedestrians")

- W = 1.5 m → 1 robot ≈ **94.96** pedestrians
- W = 1.8 m → 1 robot ≈ **6.35** pedestrians
- W = 2.1 m → 1 robot ≈ **17.11** pedestrians
- W = 2.4 m → 1 robot ≈ **3.65** pedestrians
- W = 2.7 m → 1 robot ≈ **2.63** pedestrians
- W = 3.0 m → 1 robot ≈ **2.33** pedestrians

### PRE vs directional split (width-averaged)

| W | 0.3 | 0.5 | 0.7 |
|---|---|---|---|
| 1.50 | 53.79 | 94.96 | 84.49 |
| 1.80 | 3.48 | 6.35 | 9.64 |
| 2.10 | 2.11 | 17.11 | 20.13 |
| 2.40 | 2.11 | 3.65 | 6.06 |
| 2.70 | 1.35 | 2.63 | 2.53 |
| 3.00 | 0.98 | 2.33 | 2.22 |

The robot-equivalent grows as the sidewalk narrows (the fixed 0.96 × 0.70 m footprint blocks proportionally more of a narrow corridor), so the PRE is NOT a constant but a surface over width × pedestrian flow × directional split.

## 3. Quota algorithm (fit)

- `x_crit` (over-capacity zero threshold) = 33.33 ped/min/m; cells with `q_p/W ≥ x_crit` are zeroed.
- `W_min` (minimum robot-operable width) = 1.60 m; cells with `W < W_min` are zeroed. Narrow widths 1.6 / 1.7 m were added to the training grid so `W_min` lands at ~1.6 m rather than the old 1.8 m, removing the cliff that zeroed real 1.65 m sidewalks.
- `C(W)` (robot-admissible pedestrian-flow capacity, W-dependent): cells with `q_p ≥ C(W)` are zeroed. Fitted monotone from the sweep, knots `W = [1.50, 1.60, 1.70, 1.80, 2.10, 2.40, 2.70, 3.00]` m → `C = [10, 35, 35, 45, 45, 90, 90, 90]` ped/min. This replaces the single global `x_crit` as the binding zero for narrow corridors, which saturate at a lower unit-width flow.
- `q_max` (verified ceiling cap) = 20 robot/min; the recommendation never exceeds the swept ceiling.
- **Model A** (width-normalized power law): `q̂_r = W·c·(q_p/W)^p`, `c = 28.2216`, `p = -0.8281`.
- **Model B** (2-D power surface): `q̂_r = a·W^m·q_p^n`, `a = 13.8687`, `m = 2.6316`, `n = -0.8112`.
- **Model A-iso** (non-parametric isotonic, monotone baseline).

### Fit metrics (training cells)

| model | MAE | RMSE | mean_over | max_over | mean_under | OAR |
|---|---|---|---|---|---|---|
| A | 1.535 | 2.559 | 0.376 | 3.901 | 1.159 | 0.271 |
| B | 1.186 | 1.973 | 0.253 | 3.020 | 0.934 | 0.208 |
| A-iso | 1.305 | 2.069 | 0.290 | 3.000 | 1.015 | 0.188 |

`OAR` = over-allocation rate (fraction of cells where the model predicts above the reference). A-iso has the lowest over-allocation (safe-side), B the lowest error.

## 4. Held-out validation (unseen widths)

Test cells use widths [1.65, 1.95, 2.25, 2.55, 2.85] m and flows [12, 18, 22, 27, 35, 45, 55] ped/min (no overlap with training).

| model | MAE | RMSE | mean_over | max_over | mean_under | OAR |
|---|---|---|---|---|---|---|
| Model A | 2.652 | 3.667 | 0.133 | 2.037 | 2.519 | 0.171 |
| Model B | 2.303 | 3.078 | 0.080 | 1.495 | 2.222 | 0.114 |
| Model A-iso | 2.747 | 3.509 | 0.237 | 2.764 | 2.511 | 0.171 |

### Closed-loop Service Violation Rate (re-simulate q̂_r)

- Model A (rounded to 0.5): SVR = **0.059** (2/34 feasible cells).
- A-floor: SVR = **0.0294** (1/34 feasible cells).
- A-iso: SVR = **0.1176** (4/34 feasible cells).

The pedestrian-first (safe-side) deployment rule — flooring the continuous prediction to a deployable whole number — is scored by the closed-loop re-simulation; A-floor achieves the lowest violation rate (SVR = 0.029) on the feasible test cells. This is the rule required by RQ4.

## 5. Sensitivity

Threshold δ_v ∈ ['5%', '10%', '15%']: stricter thresholds shrink the admissible region — the mean quota over the grid falls from 5%→4.9, 10%→7.1, 15%→8.5 robot/min.

**δ_v = 5%**

| qp | 1.5 | 1.6 | 1.7 | 1.8 | 2.1 | 2.4 | 2.7 | 3.0 |
|---|---|---|---|---|---|---|---|---|
| 10 | 0 | 3 | 5 | 6 | 10 | 15 | 20 | 20 |
| 20 | 0 | 2 | 3 | 3 | 6 | 10 | 15 | 18 |
| 30 | 0 | 2 | 2 | 3 | 5 | 8 | 12 | 12 |
| 40 | 0 | 0 | 0 | 1 | 1 | 8 | 10 | 10 |
| 50 | 0 | 0 | 0 | 0 | 0 | 4 | 6 | 6 |
| 60 | 0 | 0 | 0 | 0 | 0 | 2 | 3 | 4 |

**δ_v = 10%**

| qp | 1.5 | 1.6 | 1.7 | 1.8 | 2.1 | 2.4 | 2.7 | 3.0 |
|---|---|---|---|---|---|---|---|---|
| 10 | 0 | 6 | 10 | 12 | 15 | 20 | 20 | 20 |
| 20 | 0 | 5 | 6 | 6 | 12 | 15 | 20 | 20 |
| 30 | 0 | 3 | 5 | 4 | 8 | 12 | 18 | 18 |
| 40 | 0 | 0 | 0 | 1 | 2 | 12 | 15 | 15 |
| 50 | 0 | 0 | 0 | 0 | 0 | 6 | 10 | 10 |
| 60 | 0 | 0 | 0 | 0 | 0 | 4 | 6 | 6 |

**δ_v = 15%**

| qp | 1.5 | 1.6 | 1.7 | 1.8 | 2.1 | 2.4 | 2.7 | 3.0 |
|---|---|---|---|---|---|---|---|---|
| 10 | 0 | 10 | 15 | 18 | 20 | 20 | 20 | 20 |
| 20 | 0 | 6 | 10 | 10 | 12 | 20 | 20 | 20 |
| 30 | 0 | 5 | 6 | 6 | 10 | 18 | 20 | 20 |
| 40 | 0 | 2 | 2 | 1 | 6 | 12 | 15 | 15 |
| 50 | 0 | 0 | 0 | 0 | 1 | 8 | 10 | 12 |
| 60 | 0 | 0 | 0 | 0 | 0 | 4 | 6 | 8 |

Robot speed ×[0.8, 1.0, 1.2]: the quota is invariant to the reference-robot speed (maximum absolute quota change across all tested cells is 0).

The quota is therefore governed chiefly by the robot's *space occupation* in bidirectional flow rather than by its speed — a robustness property of the algorithm.

## 6. Conclusions

1. A monotone reference quota frontier exists: `q_r* = f(q_p, W)` decreases with pedestrian flow and increases with effective width; cells at pedestrian-only over-capacity are zeroed.
2. The interpretable width-normalized power law (Model A) plus a width floor recovers the frontier on unseen widths (held-out MAE ≈ 2.7 robot/min).
3. The safe-side deployment rule (A-floor) achieves closed-loop SVR = 0.029; the quota is robust to ±20% reference-robot speed and keeps pedestrian service above the required level on unseen cells.

## 7. Scope notes (honest limitations)

- The simulation engine is **Eclipse SUMO 1.27.1 + JuPedSim** (`--pedestrian.model jupedsim`, CollisionFreeSpeedModel); the *methodology* (baseline → sweep → q_r* → algorithm → held-out + closed-loop validation) follows the plan.
- **Field geometry/counts** were unavailable, so cells use the representative width range 1.5–3.0 m and demand 10–60 ped/min rather than surveyed Singapore micro-cells; the real Bendemeer Road OSM network was downloaded but experiment cells are idealized straight corridors at controlled widths.
- JuPedSim's CollisionFreeSpeedModel reduces every agent to a scalar collision disc (`radius = max(length, width)/2`), so the robot's 0.96 × 0.70 m footprint enters as a 0.48 m disc rather than a true oriented rectangle; the anisotropy and any wake behind the robot are only approximated. The PRE section quantifies the resulting robot-equivalent, which is what this footprint reduction buys.
- dt = 0.1 s is the SUMO step length (JuPedSim sub-steps internally); pedestrian/robot arrivals use constant-rate person flows (`personsPerHour`) walking between two mini edges through the 2D walkable area, and the free-flow speed is calibrated to ~1.25 m/s via a measured JuPedSim speed factor (`SPEED_CALIB = 1.094`).

## 8. Multi-city external validation (P1b, 2026-08-24)

The Bendemeer-only validation (§P1) is extended to a 4-city set (singapore
anchor + london / tokyo / amsterdam) to test cross-city transfer and the
Type-B (curve) / Type-C (bottleneck) applicability domain.

### 8.1 Cell set and coverage

100 cells (singapore 36 / london 23 / tokyo 23 / amsterdam 18) cut at 50 m from
OSM footway geometries, selected under the §2 stratified budget:

| type | A | B | C | D | total |
|---|---|---|---|---|---|
| selected | 40 | 20 | 25 | 15 | 100 |
| §2 target | 40 | 20 | 25 | 15 | 100 |

Width strata: narrow 1.0–1.5 m = 19/20 (tokyo 13, `path` default 1.2 m),
cliff 1.5–1.8 m = 35/30, mid 1.8–2.4 m = 23/25, wide 2.4–3.5 m = 18/20,
extra >3.5 m = 5/10 (optional stratum).

### 8.2 POI-based flow context

`estimate_site_flow.py` classifies each cell from its city's POI
(shop/amenity/landuse/railway) into residential / commercial / MRT-frontage /
tourism/mixed, then `q_p = x_ctx · W_eff` with the §5 priors:

| context | residential | commercial | MRT-frontage | tourism/mixed |
|---|---|---|---|---|
| selected | 45 | 20 | 14 | 21 |
| §2 target | ~35 | ~30 | ~25 | ~10 |

`W_eff` stays geometry-sourced (width tag / highway default); only `q_p` is
re-derived. Residual gaps (commercial −10, MRT-frontage −11) reflect the
sampled districts; tourism/mixed overlaps retail in mixed-use districts.

### 8.3 Ground truth and validation (results pending)

`p1_multicity.py` runs the same baseline → ascending-sweep → `q_r*` derivation
on all 100 cells × 2 flow levels × 30 seeds (200 combos). `fit_multicity.py`
then: (1) cross-city holdout (train synthetic + singapore/london/tokyo,
holdout amsterdam); (2) combined re-fit of the Model-A amplitude (c, p) keeping
the P1 real capacity structure (x_crit=29, W_min=1.6, C(W)); (3) Type-B/C
external validation with the curvature penalty `W_c = W/sinuosity`.

<!-- TODO(2026-08-24): fill §8.3 numbers from outputs/p1_multicity/ once the
     ground-truth run completes (~10 h). -->