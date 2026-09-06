# Final Operational Rule (FROZEN)

> This document freezes the scientific law, the operational rule, and the unique
> execution order. No re-simulation, no re-fitting, no margin search.

---

## 1. Four distinct layers (kept separate, per Critical Rule 10)

| Layer | What it is | Symbol |
|---|---|---|
| **Scientific law** | width-normalized power law fitted on D2 (400 combos) | `q̂_r^nom` |
| **Operational rule** | scientific law + Q80 margin + hard guardrails + integer floor | `q_r^op` |
| **Baseline qualification** | per-(cell, q_p) pedestrian-only feasibility flag | `base_pass` |
| **Applicability / OOD fallback** | domain gate + out-of-domain handling | OOD |

---

## 2. Scientific quota law (Q4)

$$
\hat q_r^{nom} = 24.37\,W\left(\frac{q_p}{W}\right)^{-0.945}
$$

with fitted constants

- `c = 24.37`
- `p = -0.945`
- width exponent fixed at 1 (Model A+ gives `alpha = 0.992 ± 0.154`, CI includes 1).

Monotonicity (in-domain): `∂q̂/∂W > 0`, `∂q̂/∂q_p < 0`.

---

## 3. Conservative margin

Global Q80 additive margin:

$$
\Delta_{80} = 3.1068 \approx 3.11
$$

applied as an **additive shift** (subtraction in quota units), not a multiplicative
factor.

---

## 4. Operational rule — complete execution order (Q5)

Frozen order (authoritative; steps are numbered and must not be re-ordered):

```
Step 0  APPLICABILITY / OOD GATE
        If (W, x=q_p/W, geometry, q_p) is outside the validated domain
        (see §5)  ->  out-of-domain fallback: NO closed-form recommendation.
        STOP. No numeric quota is produced out-of-domain.

Step 1  BASELINE QUALIFICATION
        If base_pass(cell, q_p) == 0  ->  q_r^op = 0.  STOP.

Step 2  HARD ADMISSIBILITY ZERO-GUARDS (any fire => 0)
        W < W_min (1.6 m)                  -> 0
        x >= x_crit (33.33 ped/min/m)      -> 0
        q_p >= C(W)                        -> 0
        sharp corner (max_turn>=20° AND cum_turn>=20° AND
                      max_turn/cum_turn>=0.6)  -> 0
        vbar < 0.8 m/s (absolute speed floor)  -> 0

Step 3  NOMINAL LAW
        q_hat = 24.37 * W * (q_p / W)^(-0.945)

Step 4  Q80 CONSERVATIVE MARGIN
        q_hat = max(0, q_hat - 3.1068)

Step 5  LOW-FLOW CEILING (Q_low)
        q_hat = min(q_hat, Q_low(W))
        Q_low knots (W): [1.5,1.6,1.7,1.8,2.1,2.4,2.7,3.0]
        Q_low values (Q): [ 0,  5,  6,  8, 10, 18, 20, 20]

Step 6  SWEEP CEILING (q_max)
        q_hat = min(q_hat, 20)

Step 7  INTEGER QUOTA
        q_r^op = floor(q_hat)
```

The whole rule collapses to the compact frozen form:

$$
q_r^{op} =
\left\lfloor
\min\Big(
  \min\big(\max(0,\ 24.37\,W(q_p/W)^{-0.945} - 3.1068),\ Q_{low}(W)\big),\ 20
\Big)
\right\rfloor
$$

with Steps 0–2 applied as hard gates before it, and `base_pass=0 => 0` as an
unconditional override.

---

## 5. Applicability domain (frozen)

- `W_min <= W <= 3.0 m`
- `q_p <= 60 ped/min`
- `x = q_p/W < x_crit = 33.33 ped/min/m` (within calibrated flow range)
- geometry: straight to mildly curved (Type A, or Type B with sinuosity <= 1.05);
  no sharp concentrated corners, no barriers
- `q_p < C(W)` (W-dependent robot-admissible capacity)

Outside this domain -> OOD fallback (Step 0). Note the reported OOD band
`W = 5.0–6.9 m` and other out-of-domain samples are **excluded from the in-domain
claim**, reported separately as failure-mode evidence only.

---

## 6. Guardrail ordering analysis (Phase 4)

### Q1 — `base_pass=0` before or after the nominal law?
**Before (Step 1).** Result-wise it is *invariant*: `base_pass=0` forces `0` as an
unconditional override, so applying it before or after the numeric steps yields the
same final value. It is placed first for efficiency and because it is a
qualification gate, not a numeric step. **No sample outcome depends on this order.**

### Q2 — `W_min` / `x_crit` before or after the margin?
**Before (Step 2), as hard zero-guards.** They are hard overrides to zero, so the
order relative to the margin does **not** change any result. Placed before the
nominal law so the law is only evaluated in-domain.

### Q3 — `q_max` before or after floor?
**Equivalent.** `floor(min(x, 20)) == min(floor(x), 20)` because `q_max = 20` is an
integer. **No sample outcome depends on this order.** (Frozen as "cap then floor",
Step 6 → Step 7.)

### Q4 — OOD flag before all numeric computation?
**Yes (Step 0).** The nominal law and the Q80 margin are only *defined* in-domain;
evaluating them out-of-domain would produce a number we explicitly do not claim.
OOD is a gating check, not a numeric adjustment.

### Q5 — Does any ordering change results?
**Exactly one degree of freedom is outcome-relevant: the additive margin vs the
ceilings `Q_low(W)` / `q_max`.**

- `min(Q_low(W), nominal - 3.11)` vs `min(Q_low(W), nominal) - 3.11` **differ**
  whenever `nominal - 3.11 < Q_low(W) < nominal`.
- `min(20, nominal - 3.11)` vs `min(20, nominal) - 3.11` **differ** whenever
  `nominal > 20` (ceiling-constrained wide/light cells).

**Frozen resolution:** apply the margin to the nominal law **before** the ceilings
(Steps 4 → 5 → 6). Rationale:

- At low `q_p` the nominal law diverges (`x^p -> inf`); the margin is irrelevant
  there and `Q_low` is the binding constraint. Applying the margin *after* `Q_low`
  would wrongly shave `Q_low(W)` by 3.11 (double-penalizing).
- At `q_max`-constrained cells, applying the margin *after* `q_max` would
  double-penalize capacity-saturated wide/light cells, contradicting the frozen
  statement that "Q80 has capacity cost but the baseline guard adds ~zero extra
  cost".

### Sample-count statement
The D2 reference table (400 combos) is not present in this checkout, so the exact
number of samples sitting in the `margin-vs-ceiling` band cannot be recounted here
without re-running analysis (forbidden). The frozen order above is chosen so the
frozen headline numbers (overprediction 25.75% → 6.75% → 2.75%; max overprediction
19 → 16 → 7; mean conservative loss 2.623; median utilization 0.25) remain
internally consistent, and any future reproduction must use this exact order.
