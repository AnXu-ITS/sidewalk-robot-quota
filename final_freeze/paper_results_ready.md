# Results (paper-ready)

> All numbers are held-out-city overprediction against simulation-derived feasible
> quota references. Terminology follows the frozen list.

## 1. Formula identification

On the initial design D1 the fitted exponent was `p = −0.804`. After adding the
decoupled supplement, the exponent on D2 moved to `p = −0.945`. The width-exponent
relaxation (Model A+) returns `α = 0.992 ± 0.154`, whose confidence interval
contains 1, supporting the fixed width exponent of the nominal law. Model A reaches
a LOCO held-out-city MAE of 2.189. The decoupling therefore corrected the
width–flow confounding: with `W` and `x = q_p/W` independent in the supplement,
the fitted flow exponent is no longer biased toward zero.

## 2. Guardrail ablation

The evidence chain is

```
overprediction:  25.75%  →  6.75%  →  2.75%
max overprediction:   19  →   16    →    7
```

- **Nominal law** (no margin): 25.75% overprediction, max 19.
- **+ Q80 additive margin (`Δ80 = 3.1068`)**: 6.75% overprediction, max 16. The
  margin has a capacity cost: mean conservative loss 2.623 quota units, median
  utilization 0.25.
- **+ baseline-feasibility guard (`base_pass = 0 ⇒ 0`)**: 2.75% overprediction,
  max 7. Amsterdam held-out overprediction ≈ 1.7%. The guard does **not** increase
  quota sacrifice: loss, utilization, and zero-quota rate are unchanged.

## 3. Negative findings

- **Q90/Q95 escalation destroys median utilization.** Larger quantile margins cut
  overprediction further but at a capacity cost that is disproportionate; global
  margin escalation beyond Q80 is not appropriate.
- **Multiplicative margin fails at zero-quota boundary states.** It raises
  utilization but leaves overprediction at 19.5%.
- **Hybrid margin is unstable.** The calibrated margin jumps across bootstrap
  folds, so it cannot be frozen.

Therefore the final stack keeps the Q80 additive global margin, the
baseline-feasibility guard, and the out-of-domain fallback, and rejects
multiplicative, hybrid, and higher-quantile margins.

## 4. Amsterdam applicability case (failure analysis)

The Amsterdam top-tail is reported as an applicability case, not as a main
performance result. In that tail, 95% of cells have `q_r* = 0` and 90% have
`base_pass = 0`, while 100% pass the original width/flow guardrails. All such cells
are Type-B curved-chain geometry with sinuosity 1.20–1.40, versus ≤ 1.004 for the
comparison cities. After matching on `(W, x)`, Amsterdam references are ≈ 0.45
against ≈ 5.90 elsewhere. The failure is primarily an applicability/geometry issue,
not a scale error of the law. The baseline-feasibility guard is what absorbs this
case, not a re-fit of the law.
