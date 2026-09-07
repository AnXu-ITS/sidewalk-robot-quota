# Hong Kong External Validation Results

**Deliverable:** `HONG_KONG_EXTERNAL_VALIDATION_RESULTS.md`
**Ground truth:** 13 sweep-valid in-domain cells (30-seed SUMO–JuPedSim, qr* = per-seed ≥29/30).
**Prediction:** zero-refit frozen runtime (`final_freeze/src/operational_quota.py`).
**CIs:** cell-level cluster bootstrap (2 000 resamples of the 13 cells).

All numbers below are computed by `section7_metrics.py` → `runs/formal/hk_external_metrics.json`.
No parameter was re-fit; no cell was deleted or re-run based on its outcome.

---

## 1. Headline metrics (operational quota vs qr*)

| metric | estimate | 95% CI |
|---|---|---|
| MAE (robots/min) | **4.85** | [3.08, 6.69] |
| RMSE | 5.96 | [4.22, 7.41] |
| median absolute error | 6.00 | [2.00, 6.00] |
| overprediction rate | **0.000** | [0.000, 0.000] |
| mean positive overprediction | 0.000 | [0.000, 0.000] |
| max positive overprediction | 0.000 | — |
| mean conservative loss (underprediction) | 6.30 | [4.67, 7.89] |
| median utilization (quota / qr*) | **0.167** | [0.000, 0.251] |
| feasible-zeroing rate (quota = 0 on a passing cell) | 0.462 | [0.231, 0.692] |

Interpretation: the frozen rule **never overpredicts** on HK (overprediction rate 0%),
but it **underpredicts substantially** — median utilization is 16.7%, and 46% of
the sweep-valid cells are driven to quota 0 by the margin + floor even though the
simulation shows they can carry 4–12 robots/min.

## 2. Effect of the deployment margin (Δ80 = 3.1068)

| variant | MAE | overprediction rate |
|---|---|---|
| nominal law, floored (no margin) | 3.00 | 0.308 |
| operational rule (nominal − 3.1068, + guardrails, floored) | 4.85 | 0.000 |

The margin buys complete overprediction elimination (31% → 0%) at the cost of
+1.85 MAE and 46% feasible-zeroing. On HK the margin is therefore **safe but
overly conservative**.

## 3. Breakdown

**By width bin** (operational − qr*; negative = underprediction):

| width | n | MAE | mean quota | mean qr* |
|---|---|---|---|---|
| narrow (1.6–2.0 m) | 4 | 2.50 | 0.50 | 3.0 |
| mid (2.0–2.4 m) | 5 | 3.60 | 3.00 | 6.6 |
| wide (2.4–3.0 m) | 4 | **8.75** | 1.25 | 10.0 |

**By x = q_p/W bin:**

| x | n | MAE | mean quota | mean qr* |
|---|---|---|---|---|
| x < 8 | 1 | 2.00 | 10.0 | 12.0 |
| 8–15 | 5 | **7.20** | 2.2 | 9.4 |
| 15–22 | 5 | 5.00 | 0.2 | 5.2 |
| 22–33 | 2 | 0.00 | 0.0 | 0.0 |

**By geometry type:**

| type | n | MAE | mean quota | mean qr* |
|---|---|---|---|---|
| A | 8 | 5.50 | 2.63 | 8.13 |
| B | 5 | 3.80 | 0.20 | 4.00 |

The error is concentrated in the **wide** and **mid-x** cells: there the reference
capacity is high (qr* ≈ 9–12) but the power law plus margin predicts ≈ 0–2.

## 4. Feasibility / coverage

| count | category |
|---|---|
| 0 | baseline-fail (base_pass = 0) among sweep-valid cells |
| 6 | zero-guard cells (base_pass = 1 but operational = 0) |
| 5 | spawn-excluded (integrity gate; see failure/OOD analysis) |
| 14 | OOD cells abstained (None) |
| 13 | sweep-valid in-domain cells used for the metric |
| 32 | total frozen sample |

## 5. Systematic transfer error vs the D2 seven cities

D2 in-domain error is recomputed with the same frozen runtime on
`data/final/full_reference_dataset.csv` (n = 164 in-domain rows).

| | MAE | RMSE | overprediction rate |
|---|---|---|---|
| D2 7-city in-domain | 4.49 | 5.66 | 0.000 |
| Hong Kong external | 4.85 | 5.96 | 0.000 |
| **transfer gap (HK − D2)** | **+0.35** | **+0.30** | 0.000 |

Per-city MAE: amsterdam 6.83, taoyuan 5.00, **hongkong 4.85**, seattle 4.60,
newtaipei 4.53, nyc 3.96, melbourne 3.90, taipei 3.76. Hong Kong sits inside the
D2 city range (better than Amsterdam and Taoyuan; worse than the other five).
Full table: `sites/HONG_KONG_CITY_TRANSFER_COMPARISON.csv`.

**Verdict:** the transfer penalty is small in error terms (+0.35 MAE), but the
qualitative behaviour on HK is more conservative than on D2 (16.7% utilization,
46% zeroing), i.e. the margin transfers as *safe* but *inefficient*.
