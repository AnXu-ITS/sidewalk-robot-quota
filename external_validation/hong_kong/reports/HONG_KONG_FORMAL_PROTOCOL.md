# Hong Kong Formal External-Test Protocol

**Deliverable:** `HONG_KONG_FORMAL_PROTOCOL.md`
**Status:** protocol frozen before any HK result was inspected for tuning.
This document records *what was done and why*; no number below was changed after
seeing a Hong Kong result.

---

## 0. Role of this study

This is an **external validation**, not model development. The frozen D2 quota
method (formula, margin, guardrails, applicability domain, service criteria) is
applied **unchanged** to real Hong Kong sidewalk geometry. Nothing here may
modify the model. If the model transfers, that is reported; if it fails, that is
reported as a formal finding.

## 1. Frozen method (unchanged, verified read-only)

| item | value |
|---|---|
| nominal law | q̂_r = 24.374155890965095 · W · (q_p/W)^(−0.9454494315945483) |
| deployment margin | Δ80 = 3.1068 (additive subtraction, applied before Q_low/q_max ceilings and integer floor) |
| execution order | OOD → base_pass → zero_guards → nominal → margin → Q_low → q_max → floor |
| W_min | 1.6 m |
| x_crit | 33.333… (q_p/W) |
| q_max | 20.0 robots/min |
| Q_low(W) knots | [1.5,1.6,1.7,1.8,2.1,2.4,2.7,3.0] → [0,5,6,8,10,18,20,20] |
| C(W) knots | [1.5,1.6,1.7,1.8,2.1,2.4,2.7,3.0] → [10,35,35,45,45,55,90,90] |
| sharp-corner guard | max_turn ≥ 20° AND cum_turn ≥ 20° AND concentration ≥ 0.6 |
| speed floor | vbar_min = 0.8 m/s |
| applicability domain | W∈[1.6,3.0], q_p≤60, x<33.33, Type A or Type B with sinuosity≤1.05 |
| OOD handling | `None` (abstention/fallback), **not** numeric zero, never silently dropped |

Freeze verification (read-only): D2 7-city list confirmed (Hong Kong absent);
`data/final/full_reference_dataset.csv` SHA-256 == config claim
`b2b6743d…4144e9`; runtime self-test passed; constants c/p/Δ verified; execution
order and baseline-qualification note confirmed.

> **Manifest note (recorded, not fixed in-place):** the repository
> `final_freeze/SHA256SUMS.txt` is stale for three files
> (`final_quota_method_config.{json,yaml}`, `src/operational_quota.py`) — they
> were updated in commit `e0cd83c` (audit response: strict-LOCO framing, runtime
> type/sinuosity gate) *after* the manifest was generated at `5ff9c29`. Their
> on-disk content is git-committed (clean) and semantically consistent with the
> authoritative `.md` freeze docs (which *do* match). This is a manifest
> regeneration oversight, not a formula/rule change. `git status` is clean and no
> frozen file was modified by this study.

## 2. Criterion resolution (authoritative)

- **`base_pass` (DEPLOYED) is mean-based**: over the 30 `q_r=0` seeds,
  `mean_density ≤ 1.20` AND `0.90 ≤ mean_flow_ratio ≤ 1.20` (speed retention is
  vacuous at `q_r=0`). Source: `ground_truth.py::derive_quota` (line 102),
  `extend_experiment.py::_base_pass`, config note.
- **`qr_star` (DEPLOYED) is per-seed ≥ 29/30**: for each `q_r` level,
  `sweep_pass_frac = fraction of 30 seeds passing evaluate_constraints`
  (speed `Rv ≥ 1−0.10`, flow `0.90 ≤ fr ≤ 1.20`, density ≤ 1.20);
  `qr_star = max q_r with sweep_pass_frac ≥ 0.95`.
- The old `pass_frac > 0.5` refinement bug is **not** revived. Baseline-failure
  combos are set to conservative zero **and kept** (never deleted).

## 3. Data provenance

- Official CSDI Pavement Polygon (GeoJSON `INV_PG_CSDI_INV_PG_converted.geojson`,
  SHA-256 `EB978B50…B3E`), ground public footways, Hong Kong 1980 Grid
  (EPSG:2326), study area Sha Tin. HK data lives **only** under
  `external_validation/hong_kong/`.
- Real walkable polygons are imported as `jupedsim.walkable_area` (see
  `HONG_KONG_GEOMETRY_EXECUTION_CHECK.md`); no equivalent-area rectangle
  substitution.

## 4. Formal sample freeze (Section 3)

`HONG_KONG_FORMAL_SAMPLE_FREEZE.csv` — **32 cells**, frozen before any run
(SHA-256 recorded in the manifest). Stratified by final centreline-normal width:

| width bin | n | notes |
|---|---|---|
| narrow in-domain (1.6–2.0 m) | 5 | incl. Type A & B |
| mid (2.0–2.4 m) | 7 | incl. Type A & B |
| wide (2.4–3.0 m) | 6 | incl. Type A & B |
| narrow OOD (<1.6 m) | 5 | W down to ~1.0 m |
| wide OOD (>3.0 m) | 4 | incl. plazas/promenades |
| **in-domain total** | **18** | Type A (10) + Type B (8), sinuosity ≤1.05 |
| OOD (Type C / sinuous B / W out of range) | 14 | abstain (`None`) |

Each cell records: unique ID, source polygon ID, W (representative median),
width_p10, width method (perpendicular cross-section), geometry type
(A/B/C by rect-fill), sinuosity, max/cum turn, rect_fill, CRS, applicability
status. The 7 complex Type-C cells whose oriented box contains no straight
corridor are retained in the sample and reported as OOD/abstain (never deleted).

## 5. Pedestrian-flow design (Section 4)

`HONG_KONG_EXPERIMENT_MATRIX.csv` — generated **upfront**, deterministic, never
edited after seeing results. Pedestrian demand uses the D2-validated fixed levels
`PED_FLOWS = [10,20,30,40,50,60]` ped/min, labelled **synthetic experimental
demand** (never claimed as Hong Kong measured flow). q_p assigned to span
`x = q_p/W` over **[4.0, 30.9]** with width-x overlap across narrow/mid/wide;
`x < 33.33` enforced for every in-domain combo. 18 in-domain combos (1 q_p per
cell); 14 OOD combos → abstain (no simulation).

## 6. Simulation protocol (Section 5)

Frozen pedestrian/robot models and windows (from `config.py`):

| group | values |
|---|---|
| pedestrian | radius 0.25, length 0.50, width 0.50, v0_mean 1.25, v0_std 0.15, v0∈[0.8,1.8] |
| robot | length 0.96, width 0.70, radius 0.48, v_ref 1.39 (Camello-equivalent), SPEED_CALIB 1.094 |
| sim | dt 0.1, L=50 (real cells use their own L∈[35,50]), warmup 100 s, measure 240 s, tail 100 s, measure zone (15,35) m, bidirectional_split 0.5, timeout 300 s |
| constraints | delta_v 0.10, outflow_ratio [0.90,1.20], density_floor 1.20, conf_level 0.95 |
| seeds | baseline 30, sweep 30 |

**Phases** (D2 `ground_truth.py` semantics):
- **A** baseline `q_r=0`, 30 seeds per in-domain cell (parallel, ~12 workers);
- **B** `base_pass` = mean-based (see §2);
- **C** for `base_pass=1` cells, robot sweep
  `q_r ∈ [1,2,3,4,5,6,8,10,12,15,18,20]` × 30 seeds; `qr_star` = per-seed ≥29/30.

Raw seed-level rows are retained in `runs/formal/seed_results.csv`
(checkpoint/resume); scenario dirs are removed on success and kept on
failure/timeout for diagnosis. Timeout → conservative FAIL
(`mean_density=99.0, timed_out=1`).

## 7. Prediction & metrics (Sections 6–7)

Zero-refit prediction via the frozen runtime `final_freeze/src/operational_quota.py`:
`quota(W, q_p, base_pass, geom)` → `None` (OOD) / `0.0` (base_pass=0 or
zero-guard) / floored float. Reported: nominal law, frozen Q80 operational rule,
baseline-feasibility guard, OOD/fallback separately. Metrics (MAE/RMSE/median
absolute error/overprediction rate/mean·max positive overprediction/mean
conservative quota loss/median utilization/feasible-zeroing rate/baseline-failure
count/in-domain-OOD coverage/per-width·per-x·per-geometry error) use **cell-level
cluster bootstrap** (all flow combos of one cell are correlated; seeds are not
independent cities).

## 8. Stop rule

Report honestly regardless of outcome, answer the seven questions, then **stop**
and wait for the user's decision on whether Hong Kong belongs in the paper.
