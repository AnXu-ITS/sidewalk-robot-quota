# FINAL METHOD FREEZE REPORT

> Status: **FROZEN.** No re-simulation, no re-fitting, no margin search.
> This report answers Q1–Q9 and states the final go/no-go.

---

## Q1 — What is `base_pass` exactly?

A **per-(cell, q_p) binary flag** from a **pedestrian-only (`q_r = 0`)
SUMO–JuPedSim baseline simulation** over 30 seeds. It is 1 iff at least 29/30 seeds
individually satisfy the pedestrian-service feasibility test
(`mean_density ≤ 1.20 ped/m²` AND `0.90 ≤ flow_ratio ≤ 1.20`). Speed retention is
vacuous at `q_r = 0` and is excluded. It is a function of (geometry, `q_p`) — not a
fixed per-cell attribute — and depends on `W`, `q_p`, geometry, and seed (via the
≥29/30 aggregate), but never on robot flow.

## Q2 — How is `base_pass` obtained in deployment?

**Offline prequalification (Case B).** It is not directly observable (Case A) and
not live-per-query (Case C). It can be precomputed once per sidewalk over the
operational `q_p` levels and shipped as a `(cell, q_p) → base_pass` lookup table;
online use queries the table without re-running SUMO. If the online `q_p` is
continuously varying and un-prequalified, the method degrades to
offline-recompute-or-fallback — reported honestly, not hidden, and no classifier is
trained to circumvent it.

## Q3 — Is the method still "input W and q_p ⇒ quota"?

**No, not in a purely closed-form sense.** Accurate positioning:

$$
\boxed{
\text{offline sidewalk qualification} + \text{online closed-form quota assignment}
}
$$

Online, given `(W, q_p, base_pass, applicability flag, precomputed metadata)`, the
quota is closed-form. The `base_pass` input is a precomputed simulation-derived
flag, not a closed-form function of `(W, q_p)`.

## Q4 — Final scientific quota law

$$
\boxed{
\hat q_r^{nom} = 24.37\,W\left(\frac{q_p}{W}\right)^{-0.945}
}
$$

`c = 24.37`, `p = -0.945`, width exponent fixed at 1
(`α = 0.992 ± 0.154`, CI includes 1).

## Q5 — Final operational quota rule (execution order)

```
Step 0  OOD gate: outside applicability domain -> fallback, no recommendation
Step 1  base_pass == 0 -> q_r^op = 0
Step 2  hard zero-guards: W<1.6 | x>=33.33 | q_p>=C(W) | sharp corner | vbar<0.8 -> 0
Step 3  q_hat = 24.37 * W * (q_p/W)^-0.945
Step 4  q_hat = max(0, q_hat - 3.1068)                 # Q80 margin
Step 5  q_hat = min(q_hat, Q_low(W))
Step 6  q_hat = min(q_hat, 20)                          # q_max
Step 7  q_r^op = floor(q_hat)
```

Compact form:

$$
q_r^{op} =
\left\lfloor
\min\!\Big(\min\!\big(\max(0,\ 24.37\,W(q_p/W)^{-0.945} - 3.1068),\, Q_{low}(W)\big),\, 20\Big)
\right\rfloor
$$

with Steps 0–2 as hard gates. The margin is applied **before** the ceilings; the
zero-guards and `base_pass` are order-invariant hard overrides.

## Q6 — Final in-domain held-out-city performance

- Held-out-city overprediction after the full stack: **2.75%** (max 7).
- Amsterdam held-out overprediction: **≈ 1.7%**.
- LOCO held-out-city MAE (Model A): **2.189**.
- Q80 capacity cost: mean conservative loss **2.623**, median utilization **0.25**
  (unchanged by the baseline guard).
- Evidence chain: **25.75% → 6.75% → 2.75%** (nominal → +Q80 → +baseline guard).

## Q7 — Is the Amsterdam long-tail prediction error or applicability failure?

$$
\boxed{\text{primarily an applicability/geometry failure, not a scale error}}
$$

Evidence: 95% `q_r* = 0`, 90% `base_pass = 0`, 100% pass the original W/x
guardrails, 100% Type-B curved-chain geometry (sinuosity 1.20–1.40 vs ≤1.004), and
matched-(W,x) references of ≈ 0.45 (Amsterdam) vs ≈ 5.90 (others). The power law
is not the source of the tail; the geometry is outside its applicability domain.
Sinuosity is **not** added to the formula.

## Q8 — What may / may not be claimed

- **May:** simulation-derived interpretable quota law; calibrated on real sidewalk
  geometries; LOCO cross-city evaluation; decoupling improved identifiability
  (D1 `p=-0.804` → D2 `p=-0.945`); width exponent 1 empirically supported; guardrails
  reduced overprediction (25.75% → 6.75% → 2.75%); baseline screening removed
  structurally invalid assignments; geometry-related applicability limits identified.
- **Must not:** real-world ground-truth capacity; universal law; formal safety
  guarantee; 97%/95% real-world reliability; all geometries covered; length
  irrelevant; sinuosity causal; zero-overprediction guarantee.

Full boundary in `claims_boundary.md`.

## Q9 — Ready to stop optimizing and write the paper?

$$
\boxed{\text{YES}}
$$

The final-principle conditions are all met:

- scientific law is stable (`c=24.37, p=-0.945`);
- parameter identifiability is resolved (D1→D2 decoupling, `α` CI includes 1);
- LOCO validation is complete (MAE 2.189);
- the baseline-feasibility guard has an explicit deployment interpretation
  (offline prequalification, Case B);
- OOD boundaries are frozen (applicability domain + fallback);
- no critical data/code inconsistency remains (stale values documented, frozen
  values authoritative in `final_quota_method_config.yaml`).

No blocker remains, and no further experiment expansion is warranted — pushing
overprediction below 2.75% by adding model complexity is explicitly out of scope.

$$
\boxed{
\text{STOP ALGORITHM DEVELOPMENT AND START PAPER WRITING}
}
$$
