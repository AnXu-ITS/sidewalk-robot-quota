# `base_pass(q_p)` Deployment — Final Decision (Part A)

> Question: can baseline feasibility be represented as a monotonic
> pedestrian-flow threshold `q_{p,base}^max(s)` per sidewalk?
> Constraint: use only existing data; no SUMO re-run.

---

## 1. Analytical argument (from the frozen criterion)

`base_pass(q_p) = 1` iff ≥29/30 pedestrian-only seeds satisfy

```
mean_density <= 1.20 ped/m^2  AND  0.90 <= flow_ratio <= 1.20
```

- **Density** is monotone non-decreasing in `q_p` (more pedestrians → higher density).
- **Flow ratio** is ≈1.0 in free flow and departs the feasible band monotonically
  as congestion sets in: it either collapses below 0.90 (throughput breakdown) or
  spikes above 1.20 (spawn-blocking jam). It does not re-enter the band once out.

Both terms therefore cross their thresholds in one direction only, so the pass set
is expected to be a prefix: `1,1,...,1,0,0,...,0`. The only plausible source of a
*reversal* is binomial noise at the ≥29/30 boundary (pass_frac hovering near 0.95,
where a single seed flips 29/30 ↔ 28/30).

## 2. Proxy empirical evidence (P1b, the only per-(cell,qp) data in checkout)

`base_pass` itself is absent (baseline CSVs were excluded from the migration kit),
so we use the `qr_star` proxy: `qr_star > 0 ⇒ base_pass = 1`, `qr_star = 0 ⇒
base_pass unknown`. Run via `src/base_pass_monotonicity.py` on
`pipeline/p1b_reference_dryrun.csv` (200 combos, 100 cells, 4 cities):

| Statistic | Value |
|---|---|
| cells with ≥2 qp levels | 100 |
| `qr_star` monotonic (non-increasing in q_p) | **100 / 100** |
| POTENTIAL base_pass reversals (qr_star low=0 AND high>0) | **0 / 100** |
| direct base_pass monotonic (all levels known) | 39 / 39 decisive cells |
| direct base_pass violations | 0 |

**Claim discipline:** this proxy result must NOT be written as "base_pass
monotonicity verified". The correct statement is:

> Existing proxy evidence was consistent with monotonic baseline feasibility, but
> the final D2 baseline table was unavailable for direct verification.

No cell shows the only pattern that could indicate a true base_pass reversal, but
`qr_star = 0` leaves `base_pass` unidentified, so a direct D2 audit is required
before any stronger statement. The proxy numbers are supporting evidence only.

## 3. Direct D2 audit — BLOCKED

The D2 (400-combo) `base_pass` values are not in this checkout (see
`final_d2_provenance.txt`), so the direct per-sidewalk monotonicity test on the
final dataset cannot be executed here. The tooling is in place
(`src/base_pass_monotonicity.py`) and will produce the three CSVs verbatim once
the D2 table is copied in.

## 4. Decision (non-ambiguous)

**Outcome B:**

$$
\boxed{
\text{Use discrete offline qualification lookup; do not compress to one threshold}
}
$$

Reasons:

1. The empirical monotonicity of the **final D2** `base_pass` cannot be confirmed
   in this checkout (data absent), so a "defensible single threshold" claim is not
   substantiated.
2. The D2 cells carry sparse `q_p` levels (2 per cell in D1, 3 in the decoupled
   supplement), which only ever pin down an **interval** `[q_{p,last pass},
   q_{p,first fail})`, not a point. A point threshold would be fabricated.
3. A lookup table is strictly honest and degrades gracefully: if/when the D2 data
   confirms monotonicity, the table is stored compactly as that per-sidewalk
   interval, but it is never collapsed to a scalar without the confirming data.

## 5. Deployment architecture (frozen)

- **Offline** — precompute the lookup `(cell, q_p) → base_pass` from the
  pedestrian-only baseline over the operational flow set. Expose it as the
  per-sidewalk interval `[q_{p,last pass}, q_{p,first fail})`, recorded in
  `data/sidewalk_baseline_thresholds.csv` (proxy columns, see note there).
- **Online** — gate: if `q_p ≥ q_{p,first fail}` then `q_r^op = 0`; otherwise
  proceed to the closed-form quota law. This is exactly the frozen Step 1
  (`base_pass`), executed by `src/operational_quota.py`.
- **Online inputs** (Q2 of the final report): `(W, q_p, base_pass)` plus the
  applicability flag and (if geometry guards are active) the corner/`vbar`
  metadata. `base_pass` is a precomputed flag, not a closed-form function of
  `(W, q_p)`.
