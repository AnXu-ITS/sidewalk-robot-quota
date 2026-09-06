# Methods (paper-ready)

> Academic English, no overclaiming, no marketing. Sections map one-to-one to the
> frozen pipeline.

## 1. Reference quota generation

For every sidewalk cell and pedestrian-flow level `q_p`, we run a two-stage
simulation in Eclipse SUMO 1.27.1 with the JuPedSim pedestrian model. Stage one is
the pedestrian-only baseline (`q_r = 0`, 30 seeds). Stage two is an ascending robot
flow sweep (`q_r` over the frozen level set 0–20 robot/min, early-stop). The
reference quota `q_r*` is the largest swept robot flow at which the pedestrian
service criterion holds.

The service criterion is pedestrian-first. A scenario passes if pedestrian speed
retention `R_v ≥ 0.90` (relative to the pedestrian-only baseline speed), the
pedestrian outflow/inflow ratio lies in `[0.90, 1.20]`, and mean pedestrian density
stays at or below `1.20 ped/m²`. The reference robot is a Camello-equivalent
delivery robot (0.96 × 0.70 m footprint, 5 km/h), mapped by JuPedSim to a 0.48 m
collision radius. Cells are 50 m with a `[15, 35] m` measurement zone.

## 2. Per-seed acceptance criterion (29/30)

We score constraints per seed, not on seed-averaged quantities. A swept level
passes only if at least 29 of 30 seeds individually satisfy all three constraints
(≥95%). The reference quota is the maximum passing level. This per-seed rule is
more conservative than a mean-based rule and is the primary criterion; the mean is
retained only as an upper-bound diagnostic.

## 3. D1 → D2 decoupling motivation

The initial design (D1, 280 combos) set `q_p` proportional to width via a
context-dependent factor `x = q_p/W`. As a result `x` clustered on a handful of
values and `corr(W, q_p) ≈ 0.98`. Under that confounding, a width–flow effect cannot
be separated, and the fitted exponent is biased. We therefore added a decoupled
design (120 combos) in which each of 40 cells is run at the same three `x` levels
`{18, 24, 30}`, making `W` and `x` independent within the supplement. D2 is the
union (400 combos).

## 4. Final quota-law fitting

The nominal law is the width-normalized power law

```
q_hat = c · W · (q_p/W)^p ,  p < 0
```

fitted by ordinary least squares in log–log space on cells with `q_r* > 0`.
The width exponent is fixed at 1. A relaxation model (Model A+,
`q_hat = c · W^α · (q_p/W)^p`) tests the hypothesis `α = 1`. The fitted law is
`q_hat = 24.37 · W · (q_p/W)^-0.945`.

## 5. LOCO validation

Model selection and the reported errors use leave-one-city-out (LOCO) validation:
we fit on five training cities and evaluate on the held-out city, repeating for
each city. No random split is used, because cells within a city are correlated and
a random split would inflate the estimated generalization. Seattle and Taoyuan are
frozen held-out test cities evaluated once, after the model and protocol are fixed.

## 6. Q80 residual margin calibration

The nominal law still overpredicts the reference on some cells. We calibrate a
single global additive margin `Δ80 = 3.1068` quota units so that the conservative
quota `max(0, q_hat − Δ80)` controls the unsafe-side overprediction. The margin is
additive (a shift in quota units), not multiplicative, and is calibrated once and
frozen. Applying it has a capacity cost (mean conservative loss 2.623 quota units,
median utilization 0.25).

## 7. Baseline-feasibility guard

A sidewalk cell can only admit a robot if the pedestrian-only state is itself
feasible. We encode this as a per-(cell, `q_p`) flag `base_pass`, computed from the
pedestrian-only baseline over 30 seeds with the same per-seed criterion (density
and flow stability; speed retention is vacuous at `q_r = 0`). If `base_pass = 0`,
the operational quota is set to zero regardless of the nominal law. This guard
removes structurally invalid assignments that the closed-form width/flow
guardrails miss, with near-zero additional capacity cost.

## 8. Applicability / out-of-domain handling

The law is defined on the calibrated domain: `1.6 ≤ W ≤ 3.0 m`, `q_p ≤ 60
ped/min`, `x = q_p/W < 33.33`, and straight-to-mildly-curved geometry (Type A, or
Type B with sinuosity ≤ 1.05; no barriers or sharp concentrated corners). Inputs
outside this domain do not receive a closed-form recommendation; they are routed to
the out-of-domain fallback and reported separately as failure-mode evidence only.

## 9. No test-city leakage

The model parameters, the guardrails, and the margin are fixed before any test-city
evaluation. Test cities (Seattle, Taoyuan) are excluded from all fitting and from
all threshold calibration. LOCO folds hold out one training city at a time and
never touch the frozen test cities. No threshold in the final stack is tuned on the
test set.
