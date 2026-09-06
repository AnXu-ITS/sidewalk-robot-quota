# Figure & Table Plan (paper)

> Recommended items. All figures use only frozen numbers; no new experiments.

## Figure A — Method pipeline

```
Real geometry  →  simulation reference  →  quota law  →  Q80 margin
              →  baseline guard  →  OOD fallback
```

Show the two-layer structure: offline qualification (simulation reference +
`base_pass`) feeding the online closed-form chain (quota law → Q80 margin →
guardrails → floor), with the applicability gate branching to the OOD fallback.

## Figure B — D1 vs D2 identifiability

Show the `x = q_p/W` coverage of D1 (clustered, `corr(W,q_p)≈0.98`) versus D2
(the decoupled `{18,24,30}` anchors), and the corresponding change in the fitted
exponent (`p = −0.804` → `p = −0.945`). This is the confounding-corrected
identifiability figure.

## Figure C — Nominal vs operational performance

Bar/step plot of the evidence chain, with both scopes (strict LOCO as primary):

```
strict LOCO (per-fold refit):  26.25%  →  7.50%  →  3.50%
pooled fit + fold margin:      25.75%  →  6.75%  →  2.75%
max overprediction (both):        19   →    16    →    7
```

with the capacity-cost annotation (mean conservative loss 2.623, median
utilization 0.25) on the Q80 step, and "unchanged" on the baseline-guard step.
Annotate the denominator as pooled 400 rows (164 in-domain + 236 OOD).

## Figure D — Amsterdam failure case

Two panels: (a) the curved-chain Type-B geometry (sinuosity 1.20–1.40 vs ≤ 1.004);
(b) the matched-(W,x) reference contrast (Amsterdam ≈ 0.45 vs others ≈ 5.90), with
the 90% `base_pass = 0` / 100% W/x-guardrail-pass annotation.

## Table 1 — Dataset / city / sidewalk characteristics

| City | Role | Cells | Width source | Width median (m) |
|---|---|---|---|---|
| NYC | train | 20 | derived (aerial) | 2.87 |
| Amsterdam | train | 20 | official (BGT) | 2.33 |
| Melbourne | train | 20 | derived (2A/P) | 1.97 |
| Taipei | train | 20 | official (NLMA) | 1.82 (net 1.36) |
| New Taipei | train | 20 | official (NLMA) | 2.01 |
| Seattle | test (main) | 20 | official (SDOT) | 1.52 |
| Taoyuan | test (secondary) | 20 | official (NLMA) | 2.52 |

Plus: per-city provenance, the `q_p` prior method (POI context), and the
physically-impassable filter (`W < 1.0 m` excluded).

## Table 2 — Candidate model comparison

| Model | Form | LOCO MAE | Overprediction | Physical | Interpretable |
|---|---|---|---|---|---|
| A | `c·W·x^p` | 2.189 | lowest with guards | ✓ | ✓ |
| A+ | `c·W^α·x^p` | — | — | ✓ (α=0.992±0.154) | ✓ |
| L | `+ (L/L0)^γ` | — | — | γ not identifiable | ✓ |
| R | `C(W)[1−(x/x_c)^β]+` | — | — | ✓ | partial |
| SVR | black-box | — | — | ✗ | ✗ |

## Table 3 — Guardrail ablation

The frozen `final_ablation_table.csv` (5 variants × {overprediction, max
overprediction, mean loss, median utilization, zero-quota rate}).
