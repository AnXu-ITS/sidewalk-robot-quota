# Hong Kong External Test — Smoke Test Report (Q6)

Graded smoke test of the HK-ST-01 scenario (W=2.331 m, L=50 m, q_p=20,
SMOKE seed count = 6 — **not** the formal 30). Gates run in order; a gate must
pass before the next runs. Engine: frozen SUMO 1.27.1 + JuPedSim, real polygon.

## Gate results

| gate | scope | result |
|---|---|---|
| S1 | geometry-only | **PASS** |
| S2 | pedestrian-only (q_r=0) | **PASS** |
| S3 | minimal mixed flow (q_r=2) | **PASS** |
| S4 | mini reference check (criteria code path) | **PASS** |

## S1 — geometry-only

- Real polygon: area 116.571 m² (L·W=116.55), `valid=True`,
  bounds `[0.00, −1.171, 50.00, 1.174]`.
- Minimal no-traffic run loaded without fatal error.

## S2 — pedestrian-only (q_r=0, q_p=20, 6 seeds)

| seed | mean_density | flow_ratio | mean_speed | in | out |
|---|---|---|---|---|---|
| 0 | 0.113 | 1.000 | 1.266 | 80 | 80 |
| 1 | 0.111 | 1.000 | 1.298 | 80 | 80 |
| 2 | 0.111 | 1.000 | 1.293 | 80 | 80 |
| 3 | 0.111 | 1.012 | 1.292 | 80 | 81 |
| 4 | 0.110 | 1.000 | 1.305 | 80 | 80 |
| 5 | 0.111 | 1.000 | 1.289 | 80 | 80 |

- **mean_density = 0.111 (≤ 1.20)** ✓
- **mean_flow_ratio = 1.0021 (0.90–1.20)** ✓
- **base_pass (mean-based) = True** (speed retention vacuous at q_r=0) ✓
- All pedestrians spawn and exit (in ≈ out).

## S3 — minimal mixed flow (q_r=2, q_p=20, 6 seeds)

- All 6 seeds pass `evaluate_constraints` (6/6); vbar = 1.2904.
- Robot behaviour (per seed): **12 robots** (q_r=2/min × 340 s), **12/12
  completed** (walk arrival recorded), **0 FCD points outside the walkable
  polygon** (no wall-passing / illegal route), robot mean speed 1.18–1.30 m/s
  (near v_ref=1.39 under interaction).
- Pedestrian flow_ratio 0.975–1.025 (slight throughput modulation by the robot,
  as expected).

## S4 — mini reference check (criteria code path)

Tiny ascending sweep q_r ∈ {0,1,2,3} at 6 seeds, with checkpoint CSV write and
re-read:

- per-level pass fraction: `{0.0: 1.0, 1.0: 1.0, 2.0: 1.0, 3.0: 1.0}`.
- checkpoint CSV re-read: OK (row count matches).
- base_pass (mean-based) = True; criteria code (`mean_density ≤ 1.20`,
  `0.90 ≤ flow_ratio ≤ 1.20`, speed retention) exercised end-to-end.

**⚠ q_r^star (smoke) = 3.0 is NOT a formal quota.** It is a code-path check on
6 seeds and a 4-level sweep only. The formal q_r^* requires the full
30-seed × 0–20 robot-flow sweep and is **deferred to the formal external test**.

## Bug guard (frozen criteria, re-verified against code)

- `qr_star` uses **per-seed ≥ 29/30** (pass fraction ≥ 0.95) — `rescore_seedwise_full.py`
  `sweep_pass_frac` via `evaluate_constraints`.
- `base_pass` is **mean-based** (mean_density ≤ 1.20 AND 0.90 ≤ mean_flow_ratio
  ≤ 1.20 over q_r=0 seeds), NOT per-seed; speed retention vacuous at q_r=0.
- The old `pass_frac > 0.5` refinement is **not used**.
- A manual re-read of `simulator.py::_parse` confirmed the outflow path is
  correct (walk `arrival` is read before any element clear); a transient
  diagnostic that reported `outflow=0` was due to a locally introduced
  clear-before-read in the diagnostic script, not in the frozen code.

## Outputs

- `runs/smoke/hk_smoke_results.json` — full gate detail.
- `runs/smoke/hk_s2_baseline.csv`, `hk_s3_mixed_qr2.csv`,
  `hk_s4_sweep_qr{1,2,3}.csv`, `hk_s4_sweep_all.csv`.
- Scenario configs/logs under `scenarios/HK-ST-01_qp20_qr*_s*/`.
- Robot verification: `verify_s3_robot.py` (PASS).
