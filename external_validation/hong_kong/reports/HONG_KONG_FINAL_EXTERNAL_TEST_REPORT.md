# Hong Kong Final External-Test Report

**Deliverable:** `HONG_KONG_FINAL_EXTERNAL_TEST_REPORT.md`
**Study:** 香港正式独立城市外测 — external validation of the frozen D2 quota method on
real Hong Kong sidewalk geometry. No model development, no re-fitting, no
parameter/margin/domain changes. All HK artefacts live under
`external_validation/hong_kong/`; no frozen file was modified.

---

## 0. One-paragraph verdict

The frozen D2 operational rule **does not overpredict anywhere on Hong Kong**
(overprediction rate 0%, 95% CI [0,0]) and its overall error is close to the D2
in-domain error (MAE 4.85 vs 4.49, transfer gap +0.35; RMSE 5.96 vs 5.66, gap
+0.30). The cost is heavy **underprediction**: median utilization 16.7% and 46%
of the sweep-valid cells are driven to quota 0 although the simulation shows they
sustain 4–12 robots/min. The applicability domain abstains on 14/32 (43.8%) HK
footways, and a real geometry–spawn interface (tapered/wedge/narrow-neck footways)
invalidated 5/18 in-domain cells (recorded and excluded via a spawn-integrity gate,
not by tuning). Net: the model **transfers safely but inefficiently**; Hong Kong
surfaces a *conservatism* problem, not an *unsafe-prediction* problem.

## 1. Freeze and isolation (unchanged)

Nominal law q̂_r = 24.374155890965095 · W · (q_p/W)^(−0.9454494315945483);
margin Δ80 = 3.1068 (subtracted before Q_low/q_max/floor); order
OOD → base_pass → zero_guards → nominal → margin → Q_low → q_max → floor;
guardrails W_min=1.6, x_crit=33.33, q_max=20, Q_low(W), C(W), sharp-corner,
vbar_min=0.8; applicability domain W∈[1.6,3.0], q_p≤60, x<33.33, type∈{A,B},
B⇒sinuosity≤1.05. Deployed `base_pass` is mean-based; `qr*` is per-seed ≥29/30.
Freeze verification passed (D2 SHA match, c/p/Δ match, runtime self-test); the
repository manifest is stale for 3 files (regeneration oversight, git-clean, not a
rule change).

## 2. Geometry execution gate — PASSED

Real CSDI polygons are loaded as `jupedsim.walkable_area` (GIS↔SUMO match to 1-mm
rounding, 0.026% symmetric difference). 25/32 cells pass the machine geometry
check; 7 complex Type-C junction polygons are OOD (not simulated).

## 3. Frozen sample

32 cells: 18 in-domain (10 Type A + 8 Type B, W 1.613–2.632 m, x 4.0–30.9) and
14 OOD (5 narrow, 4 wide, 5 complex Type-C incl. one sinuous-B). SHA-pinned in
`HONG_KONG_FORMAL_SAMPLE_FREEZE.csv`.

## 4. Pedestrian-flow design

Deterministic upstream matrix (`HONG_KONG_EXPERIMENT_MATRIX.csv`); pedestrian demand
is **synthetic experimental demand** at D2 levels (10/20/30/40/50/60 ped/min) —
never claimed as measured HK flow.

## 5. Formal sweep (30-seed)

18 in-domain → baseline (30 seeds) → base_pass (mean-based, 18/18) → robot sweep
[1,2,3,4,5,6,8,10,12,15,18,20]×30 → qr* (≥29/30). **Spawn-integrity gate** (a
data/interface finding, not a model change) excluded 5 cells: 2 simulation-invalid
(inflow=0: HK-ST-05, HK-ST-24) and 3 spawn-degraded (inflow<80%: HK-ST-16, 19, 22).
13 sweep-valid cells carry the metric. No timeouts.

## 6. Zero-refit prediction

`HONG_KONG_EXTERNAL_PREDICTIONS.csv` via `final_freeze/src/operational_quota.py`
(no refit). 13 valid cells, 14 OOD abstentions, 5 spawn-excluded (kept, NaN ref).

## 7. External metrics (cell-level cluster bootstrap)

| metric | value [95% CI] |
|---|---|
| MAE | 4.85 [3.08, 6.69] |
| RMSE | 5.96 [4.22, 7.41] |
| overprediction rate | **0.00 [0.00, 0.00]** |
| mean conservative loss | 6.30 [4.67, 7.89] |
| median utilization | **0.167 [0.00, 0.25]** |
| feasible-zeroing rate | 0.462 [0.23, 0.69] |

Nominal (no margin): MAE 3.00, overprediction 30.8% → the margin removes all
overprediction but adds +1.85 MAE and 46% zeroing. Error is worst for wide cells
(MAE 8.75) and mid-x cells (x 8–15: MAE 7.20). D2 transfer gap: **+0.35 MAE,
+0.30 RMSE**. (Full detail in `HONG_KONG_EXTERNAL_VALIDATION_RESULTS.md`.)

## 8. The seven questions (answered honestly)

1. **Does the frozen law + operational rule generalize to Hong Kong?**
   *Partially.* Error is close to D2 (MAE 4.85 vs 4.49), and safety is preserved
   (0% overprediction). But the rule is systematically conservative on HK
   (utilization 16.7%), so it generalizes in *safety* but not in *efficiency*.

2. **Is the deployment margin Δ80 = 3.1068 appropriate on HK?**
   *Too conservative.* It drives overprediction from 30.8% (nominal) to 0%, but
   zeroes 46% of feasible cells and yields median utilization 16.7%. Direction is
   safe; magnitude is larger than HK geometry requires.

3. **Does the applicability domain cover HK footways?**
   *Partially.* 14/32 (43.8%) abstain: 5 narrow (<1.6 m), 4 wide (>3.0 m), 5
   complex Type-C. This is a substantial coverage gap for a dense Asian city.

4. **Are the guardrails triggered correctly on HK?**
   *Safe but blunt.* 6/13 cells hit operational=0 (margin+floor or C(W)/Q_low);
   no guardrail produced an unsafe value. The C(W) and Q_low ceilings plus the
   3.1068 margin compound into excess zeroing.

5. **Is the deployed mean-based base_pass robust?**
   *No — a real robustness gap.* On 5/18 in-domain cells the frozen `_parse`
   `flow_ratio = 1.0` default (when `inflow_ped == 0`) made the mean-based
   base_pass report a spurious pass. These cells were caught by the
   spawn-integrity gate (documented, pre-fix originals preserved) and excluded —
   but the deployed mean-based criterion alone would not have caught them.

6. **What is the systematic transfer error vs the D2 seven cities?**
   +0.35 MAE, +0.30 RMSE (HK 4.85/5.96 vs D2 4.49/5.66, both 0% overprediction).
   HK's per-city MAE sits inside the D2 range (worse than 5/7 cities, better than
   Amsterdam and Taoyuan).

7. **Should Hong Kong be included in the paper?**
   Presented as evidence for the user's decision, not pre-decided. *In favour:*
   HK is a genuinely held-out city; the model stays safe (0% overprediction) with
   only a +0.35 MAE transfer penalty, and HK exposes a *conservatism/inefficiency*
   limitation plus an applicability-domain coverage gap that D2's own cities do
   not reveal. *Against / caution:* only 13 sweep-valid cells (5 excluded on
   geometry-spawn integrity), synthetic (not measured) pedestrian demand, and the
   result is a documented *underprediction*, which may be read as a weak point
   rather than a strength. **Recommendation: include as a "held-out conservatism
   check" with the spawn-integrity caveat explicit; do not present it as clean
   accuracy confirmation.** Final call is the user's.

## 9. Limitations

- 13/18 in-domain cells sweep-valid; 5 excluded on geometry/spawn integrity.
- Synthetic experimental pedestrian demand (no measured HK flow).
- Straight OBB-axis corridor centreline; tapered/wedge footways deviate (documented).
- 1 combo per cell → 13 independent cells → wide bootstrap CIs.
- 6 cells with L<50 m use the frozen measure zone (15,35) as-is (minor deviation).

## 10. Decision gate

External validation **complete**. Stopping here and awaiting the user's decision on
whether Hong Kong belongs in the paper. No automatic inclusion.
