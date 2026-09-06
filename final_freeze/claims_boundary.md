# Claims Boundary & Terminology Freeze

> This file freezes what the results support and what they do not, plus the exact
> terminology to use throughout the paper. Nothing here is a marketing claim.

---

## 1. Length (`L`) — frozen statement (Phase 8)

**Frozen conclusion:**

$$
\boxed{
\text{length effect was not identifiable under the current protocol}
}
$$

**Reasoning (why):** under the frozen protocol every cell is 50 m and the simulator
is length-insensitive by construction — it drives per-minute flows through a fixed
`[15, 35] m` measurement zone, so `L` has no independent variation. The `(L/L0)^γ`
term therefore has zero identifiability: its exponent `γ` cannot be estimated
(no information), so the length term is excluded from the main formula as a
known limitation, not as an empirical "no effect" finding.

**Forbidden phrasings:**
- ❌ "length has no effect"
- ❌ "`γ = 0` proves length is irrelevant"

**Allowed phrasing:** "the length effect was not identifiable under the current
protocol (all cells 50 m; the simulator is length-insensitive by construction)".

---

## 2. Terminology freeze (Phase 10)

Use exactly these terms:

| Use | Avoid |
|---|---|
| simulation-derived feasible quota reference | true quota / real ground truth |
| nominal quota law | — |
| conservative operational quota | safe quota guarantee / certified capacity |
| baseline-feasibility guard | — |
| applicability domain | — |
| out-of-domain fallback | — |
| held-out-city overprediction | real-world reliability (97%/95%) |

`q_r*` is always "the simulation-derived feasible quota reference", never
"real-world ground truth".

---

## 3. Claims that MAY be made (Phase 9 — allowed)

- A **simulation-derived, interpretable** sidewalk robot quota law.
- Calibrated on **real-world sidewalk geometries** (official width data across
  7 cities).
- **Cross-city evaluated using strict LOCO validation** (leave-one-city-out with
  per-fold re-fit of the coefficients).
- **Targeted decoupling improved parameter identifiability** (D1 `p = -0.804`
  → D2 `p = -0.945`).
- **Width exponent 1 is empirically supported** (Model A+ `α = 0.992 ± 0.154`,
  CI includes 1).
- **Conservative operational guardrails substantially reduced unsafe-side quota
  overprediction** (strict LOCO 26.25% → 7.50% → 3.50%; pooled diagnostic
  25.75% → 6.75% → 2.75%; max 19 → 16 → 7).
- **Baseline-feasibility screening removed structurally invalid assignments**
  (Amsterdam held-out overprediction ≈ 1.7%).
- **Geometry-related applicability limits were identified** (the Amsterdam
  failure mode; the W = 5.0–6.9 m OOD band).

## 4. Claims that MUST NOT be made (Phase 9 — forbidden)

- ❌ real-world ground-truth robot capacity
- ❌ universal sidewalk capacity law
- ❌ formal safety guarantee
- ❌ 97% / 95% real-world reliability
- ❌ all sidewalk geometries are covered
- ❌ length is irrelevant
- ❌ Amsterdam geometry proves sinuosity is causal
- ❌ zero-overprediction guarantee

---

## 5. One-line boundary

> All quota references are simulation-derived; all performance numbers are
> held-out-city overprediction on simulation-derived references; the method is an
> interpretable quota *law with guardrails*, not a certified capacity and not a
> safety guarantee.
