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

### 8.3 Results

The full run completed: 200 combos (100 cells × 2 flow levels × 30 seeds),
82 with nonzero `q_r*`, 17 capped at `q_max=20`, 25 pedestrian-only
over-capacity (Case-1, zeroed).

**Width floor validated.** Cells below `W_min=1.6` m are 106/200 combos; 104 of
them have `q_r*=0` (narrow Tokyo `path` default 1.2 m and 1.5 m cells do not
admit robots, consistent with the 0.96 m robot disc + passing space).

**Model transfer (P1 model, synthetic c/p, on all 200 combos):**

| metric | plain W_eff | W_c = W/sinuosity |
|---|---|---|
| MAE (robot/min) | 1.286 | 1.284 |
| over-allocation rate (OAR) | 0.090 | 0.085 |
| floor-rule violations | 16/200 | 14/200 |

Of the 16 floor violations, 8 over-allocate by 1 robot, 3 by 2–3, and 5 by
4–5. The severe ones concentrate in (a) extra-wide cells (W = 3.6–4.0 m, true
`q_r*` 8–15 but capped at `q_max=20`) and (b) Amsterdam curve cells at
moderate flow (e.g. W=2.5 m, q_p=50, true `q_r*=0`, predicted 5).

**Combined re-fit (c, p) is NOT adopted.** Re-fitting the amplitude on
synthetic + real gives (c, p) = (32.2, −0.856) vs P1's (28.2, −0.828): MAE
improves marginally (1.286 → 1.268) but floor violations worsen 16 → 27
(OAR 0.090 → 0.145). The residual violations are therefore *not* amplitude
errors; they stem from `q_max=20` being generous beyond the synthetic width
range and from discrete curve-cell failures, neither of which a power-law
amplitude re-fit can remove. The synthetic-trained P1 model is retained.

**Cross-city holdout** (train synthetic + singapore/london/tokyo = 212 rows,
test amsterdam = 36): holdout MAE 2.917 (2.851 with sinuosity penalty),
OAR 0.222, floor violations 8/36. Transfer degrades on the held-out city,
driven by its curved canalside B cells and 4.0 m promenades.

**Type-B / Type-C external validation (P1 model):**

| type | n | sinuosity | plain over_floor | with W_c=W/sinuosity |
|---|---|---|---|---|
| B (curve) | 40 | 1.022–1.228 | 7/40 (MAE 0.726) | 5/40 (MAE 0.704) |
| C (bottleneck) | 50 | 1.000–1.339 | 2/50 (MAE 1.761) | 2/50 (MAE 1.745) |

Bottleneck (C) cells are safe (4 % over-allocation); curve (B) cells need the
curvature penalty (17.5 % → 12.5 %), but a residual discrete failure remains
on curved cells at moderate flow — the smooth power law with `W_c=W/sinuosity`
still over-allocates where robot–pedestrian interaction degrades sharply on a
bend. The algorithm's applicability domain is therefore straight-to-mildly-
curved corridors; sharp curves need a discrete (zeroed) treatment.

### 8.4 P2 hardening: turn-angle fix + conservative guard

**Turn-angle metric bug (fixed).** `build_cells.cell_geometry` and
`analyze_osm` computed segment bearings for zero-length (duplicate) centerline
points, so `atan2(0,0)=0°` produced bogus `max_turn_deg` (e.g. AMS-4480644-0
recorded 116.4° but is geometrically straight). Skipping `d ≤ 1e-6` segments
corrected 8/100 cells in place (`fix_turn_angles.py`); the ground-truth
centerlines were unchanged, so no re-simulation was needed.

**Sharp-corner signal (corrected) vs bend sweep.** With corrected angles only
two W≥1.6 m cells carry a concentrated sharp corner (AMS-1351790552-1, 90.2°,
`q_r*=0`; SIN-1105987650-1, 95.1°, `q_r*=6`), while mild bends (40–51°) admit
8–18 robot/min — too sparse to fix a threshold. A controlled **bend-angle ×
width mini-experiment** (`bend_sweep.py`, θ∈{0,30,45,60,75,90}° × W∈{2.0,2.5,3.0}
m × q_p=50 × 30 seeds) closed the gap:

| θ \ W | 2.0 | 2.5 | 3.0 |
|---|---|---|---|
| 0° (straight) | 0 | 8 | 10 |
| 30° | 1 | 1 | 1 |
| 45° | 1 | 1 | 1 |
| 60° | 1 | 2 | 2 |
| 75° | 0 | 0 | 1 |
| 90° | 0 | 0 | 0 |

**A single sharp corner collapses robot throughput even at 30°** (8–10 → 0–2)
at every width: the corner itself already slows the pedestrian baseline
(vbar 1.198 → 0.931 at 30° → 0.623 at 90°), so one robot tips it over. The
operative feature is turn **concentration** (`max_turn/cum_turn` ≈ 1 for a
single corner vs ≤ 0.5 for a gradual curve) — a 30° corner has sinuosity only
1.035, which the `W_c=W/sinuosity` penalty cannot capture. The real multi-city
"B curve" cells are gradual (multi-bend), which is why they were healthy.

**Corner-position sweep.** `bend_position_sweep.py` (θ∈{0,15,20,30,45,60,75,90}° ×
position∈{entry,middle,exit}, W=2.5 m, q_p=50, 30 seeds, 22 combos) resolves
WHERE the corner sits:

| θ \ pos | entry | middle | exit |
|---|---|---|---|
| 15° | 6 | 2 | 3 |
| 30° | 6 | 1 | 3 |
| 45° | 4 | 1 | 3 |
| 60° | 1 | 2 | 3 |
| 75° | 0 | 0 | 0 |
| 90° | 20* | 0 | 0 |

Corner **position** matters: an **exit** corner (short stub before the exit,
as in AMS-1351790552) is a queueing bottleneck and collapses at 90° (q_r*=0);
an **entry** corner is more forgiving at mild angles (15–30° admit 6) but still
collapses by 75°; **middle** corners collapse most monotonically. The `*` on
entry-90° is a **relative-criterion artifact**: its baseline is vbar=0.645 m/s
(the corner alone slows pedestrians ~46%) yet it "passes" at q_r=20 because
`R_v = v̄/v̄₀ ≥ 0.90` is trivially satisfied on an already-slow baseline. An
**absolute speed floor** (`vbar < 0.8 m/s → 0`) closes this gap with zero impact
on the 200 real combos (all 36 combos with vbar<0.8 already have q_r*=0).

**Conservative guard (evaluated, not adopted).** The refined P2 variant applies
`max_turn ≥ 20° AND cum_turn ≥ 20° AND max_turn/cum_turn ≥ 0.6 → q̂=0`
(concentrated single corner), `vbar < 0.8 m/s → q̂=0` (absolute speed floor),
plus `q_max=15` for `W > 3.0 m` (`quota_params_p2.json`). On the 200 combos it
moves over-allocation 14 → 12 (`max_over` 5 → 4) at the cost of one extra
under-allocation (62 → 63); MAE is unchanged (1.370). The 100-cell sample
under-represents single corners (its "B" cells are gradual), so the guard's
in-sample effect is small; its value is protecting future intersection-corner
cells. Real intersection-corner sampling is the remaining precondition for
adoption.

**Data anomaly resolved (width-tag check).** AMS-244428233-0 (`highway=path`
"Kop van Jut", `barrier=cycle_barrier`) returns `q_r*=20` at q_p=6 and 14 —
the ONLY cell below W_min=1.6 with nonzero quota (both its combos). OSM way
244428233 carries only `highway=path` + `surface=asphalt` + `name` — **no
`width`/`sidewalk` tag** — so `W_eff=1.2 m` is the OSM `path` *default*, not a
measured width; an asphalt named street is very likely ≥ 2 m. The W_min=1.6
floor therefore over-conservatively zeroes the model (predicted 0 vs true 20),
a safe-side under-allocation driven by width-tag understatement, not an
algorithm defect. Recommended fix: re-tag from aerial width or exclude
width-untagged `path` cells; kept as-is here (safe side).

### 8.5 Cross-engine consistency (P2 item 2, RQ4)

The quota algorithm is run against a second, independent dynamics engine —
the Python social-force model (`experiment/`, hard-core discs + continuous
repulsion) — and its reference frontier is placed beside the JuPedSim frontier
on the common `W ∈ {1.5,1.8,2.1,2.4,2.7,3.0}` × `q_p ∈ {10…60}` grid
(`cross_engine.py`).

| engine | 10 | 20 | 30 | 40 | 50 | 60 (q_p) |
|---|---|---|---|---|---|---|
| social-force 1.8 m | 1 | 1 | 0 | 0 | 0 | 0 |
| social-force 2.4 m | 4 | 3 | 1 | 1 | 0 | 0 |
| social-force 3.0 m | 10 | 8 | 2 | 1 | 0 | 0 |
| JuPedSim 1.8 m | 12 | 6 | 4 | 1 | 0 | 0 |
| JuPedSim 2.4 m | 20 | 15 | 12 | 12 | 6 | 4 |
| JuPedSim 3.0 m | 20 | 20 | 18 | 15 | 10 | 6 |

Re-fitting Model A on the common grid with the **same procedure** as
`fit_quota.py`:

| engine | c | p | x_crit | W_min |
|---|---|---|---|---|
| social-force | 11.2 | −1.186 | 25.0 | 1.8 |
| JuPedSim | 31.3 | −0.856 | 33.3 | 1.8 |

**Structure is engine-robust, parameters are engine-specific.** The two
frontiers are near-identically *ordered* (Spearman ρ = 0.915 on the 36 common
combos): quota decreases in q_p and increases in W in both, with a hard
capacity cutoff (`x_crit`) and a width floor (`W_min`). The `W_min` gap
(1.8 vs 1.6) is a **grid-coverage artifact**: the social-force grid never
tested 1.6–1.7 m, where JuPedSim found 6–10 robot/min at low flow — the width
floor itself (≈ the 0.48 m robot disc + passing space) is geometric and
engine-independent.

The **scale differs by ~2.8×** (amplitude) and the exponent by ~0.72×
(social-force decays faster, p = −1.19 vs −0.86): the social-force model's
continuous repulsion degrades pedestrian service more aggressively than
JuPedSim's collision-free steering, so it admits fewer robots at the same
(x = q_p/W). This is expected — the (c, p) coefficients encode engine dynamics,
not the algorithm.

**Implication for deployment.** The *form* of the algorithm (`q̂_r = W·c·x^p`,
W_min floor, x_crit zeroing, floor() safe-side) transfers across engines; only
(c, p) must be re-calibrated. Calibrating on the more conservative engine
(social-force) yields a lower — hence safer — quota than the JuPedSim
calibration, so the JuPedSim-trained production model is the optimistic bound
and the social-force model the conservative bound. The quota is thus robust to
the choice of dynamics engine in *structure*, with the engine's conservatism
spanning the deployment margin.

### 8.6 Pass-criterion: mean vs per-seed (P2 item 1)

The plan specifies a per-seed service guarantee `Pr(C_p=1) ≥ 0.95`
(`conf_level=0.95` in `config.CONSTRAINTS`), but the implementation has been
using a **seed-averaged** pass rule (a level passes if the *mean* speed-retention
/ flow-ratio / density over 30 seeds satisfies the constraint). `rescore_seedwise.py`
re-scores the SAME sweep data under the per-seed rule — a (tag, q_r) level passes
only if ≥ 29/30 seeds individually satisfy all three constraints — no
re-simulation.

| criterion | sum of q_r* | nonzero combos |
|---|---|---|
| mean-based (current) | 1028 | 82/175 |
| per-seed (≥ 95%) | 753 | 78/175 |

The per-seed criterion is strictly more conservative: **70/175 combos lower
(none higher), total quota −27%**, and the reductions concentrate at **low flow**
(q_p = 9–12 ped/min) — e.g. SIN-200171267-2 (q_p=10) drops 20 → 10 — exactly the
regime the plan flagged as "arrival-noise-dominated". At low flow a single
unlucky seed (a late arrival, a transient jam) is enough to pull the *mean*
below/above threshold inconsistently, whereas the per-seed rule demands
near-unanimity across seeds.

**Decision.** The per-seed rule is the correct *service-guarantee* ground truth
and should be the primary reference for the algorithm evaluation; the mean-based
`q_r*` is an upper bound that understates the low-flow noise. Re-scoring
(`rescore_seedwise.csv`) is adopted as the reference for the low-flow regime,
and the paper reports both criteria with the −27% gap as the cost of the
seedwise guarantee.