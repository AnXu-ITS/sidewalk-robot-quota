# `base_pass` Deployment Audit

> Status: FROZEN. No re-simulation, no re-fitting, no margin search.
> Scope: Phase 1 (precise definition) + Phase 2 (deployment availability).
> Code references point to the current checkout; line numbers are informational.

---

## 1. Precise definition of `base_pass`

`base_pass` is a **per-(cell, q_p) binary flag** derived from a **pedestrian-only
(robot-flow = 0) SUMO–JuPedSim baseline simulation** under the frozen criterion.

Formally, for a fixed sidewalk cell with geometry `g` and effective width `W`, at
pedestrian flow `q_p`:

```
base_pass(g, q_p) = 1
  <=>
  in a q_r = 0 simulation of (g, q_p) over N = 30 seeds,
  at least 29 of 30 seeds (>= 95%) INDIVIDUALLY satisfy the
  pedestrian-service feasibility test:

      mean_density      <= 1.20 ped/m^2        (density_floor)
      AND
      0.90 <= flow_ratio <= 1.20               (outflow/inflow stability)
```

- **Speed retention is NOT part of the baseline test.** At `q_r = 0` the
  speed-retention term `R_v >= 1 - delta_v` (with `delta_v = 0.10`) is vacuous
  by construction, so the baseline test reduces to density + flow stability.
- `base_pass = 0` means the sidewalk, at that pedestrian flow, **cannot even
  sustain pedestrian-only service** under the criterion. In that case no robot
  quota is assigned: `q_r^op = 0`, regardless of the nominal law output.

### Code provenance

| File | Role |
|---|---|
| `pipeline/sim/scripts/rescore_seedwise_full.py` (`baseline_pass_frac`, `seedwise_labels`) | per-seed baseline test: `ok = (mean_density <= DFLOOR) & (flow_ratio in [OUTMIN, OUTMAX])`; `base_pass = (pass_frac >= CONF)` with `CONF = 0.95`. |
| `pipeline/sim/scripts/external_ground_truth.py` (`baseline_ok`) | identical test for the external driver (`>= 29/30` of seeds). |
| `pipeline/sim/scripts/config.py` (`CONSTRAINTS`) | `delta_v=0.10`, `outflow_ratio_min=0.90`, `outflow_ratio_max=1.20`, `density_floor=1.20`, `conf_level=0.95`. |
| `pipeline/sim/scripts/ground_truth.py` (`derive_quota`) | mean-based analogue (`mean_density <= dfloor AND flow_ok`); the final protocol uses the per-seed form. |

### Answer to Phase 1 sub-questions

1. **What baseline is `base_pass` against?**
   Robot flow = 0, pedestrian-only SUMO–JuPedSim simulation, 30 seeds, the same
   pedestrian-service criterion, per-seed ≥29/30 acceptance. **Yes — this matches
   the hypothesized definition exactly.**

2. **Per-cell fixed, per-(cell, q_p), or time/flow-varying?**
   **per-(cell, q_p).** It is a function of the (geometry, q_p) pair. It is *not* a
   fixed per-cell attribute, because both density and flow ratio grow with `q_p`.

3. **Does each new `q_p` require recomputation?**
   **Yes.** `base_pass` depends on `q_p`; a different pedestrian flow is a
   different baseline scenario. In the D2 study every (cell, q_p) combo had its own
   baseline simulation.

4. **Dependencies.**
   - `W` (effective width) — yes, through density / flow behavior.
   - `q_p` (pedestrian flow) — yes, strongly.
   - **geometry** (centerline shape, width profile, bottlenecks, curvature) — yes,
     through the simulated density / flow; this is what makes `base_pass` stricter
     than the coarse closed-form `x_crit`/`C(W)` proxies.
   - **seed** — yes, only through the aggregate acceptance rule (≥29/30).
   - **context** — only indirectly, via the `q_p` prior it assigns.
   - **robot flow** — **no** (always `q_r = 0` by definition).
   - **other state** — no.

5. **Relationship to `x_crit` / `C(W)`.**
   `x_crit = 33.33 ped/min/m` and the width-dependent `C(W)` are **coarse closed-form
   proxies** calibrated from where `base_pass`/`qr_star` flips across the grid.
   `base_pass` is the **direct, per-cell authoritative** version of the same
   over-capacity concept. This is why the baseline-feasibility guard
   (`base_pass=0 => 0`) removes structurally invalid assignments that the
   W/x guards miss (e.g. curved Amsterdam cells at moderate x).

---

## 2. Deployment availability of `base_pass`

**Question: can `base_pass` be known without online SUMO/JuPedSim simulation?**

`base_pass` cannot be produced by any closed-form function of `(W, q_p)` alone —
it is *defined* by a pedestrian-only simulation under the service criterion.

### Case A — directly observable / externally available: **No (not directly)**

- A municipal sidewalk service classification, an observed LOS, a measured
  walking speed, or a pedestrian density snapshot are **proxies**, not the frozen
  criterion (`mean_density <= 1.20 AND 0.90 <= flow_ratio <= 1.20`, per-seed
  ≥29/30). They cannot be assumed equal to `base_pass` without a separate
  validation study.
- A field-measured pedestrian-only density/flow could *in principle* proxy it, but
  that would be a different data source and would require its own calibration —
  it is not what was used, and it is not claimed.

### Case B — offline simulation / prequalification: **Yes — this is the frozen architecture**

The final method is defined as:

```
offline sidewalk qualification  +  online closed-form quota assignment
```

- **Can qualification be precomputed once?** Yes, per sidewalk cell.
- **Per `q_p` level?** Yes — because `base_pass` depends on `q_p`, it must be
  precomputed for each operational pedestrian-flow level (or over a `q_p` grid).
- **Lookup table?** Yes — a `(cell, q_p) -> base_pass` lookup table can be built
  offline and shipped with the sidewalk metadata.
- **Online use without re-running SUMO?** Yes, **provided** the queried `(cell, q_p)`
  has a precomputed entry. Querying an uncovered `q_p` must route to the
  OOD/fallback branch (or a conservative prequalified-neighbor fallback), not to a
  live per-query simulation.

### Case C — live simulation each time: **No (not required under the frozen method), with a caveat**

The frozen method does **not** assume live per-query simulation. However, this must
be stated honestly:

> **If** an intended deployment has continuously varying `q_p` and cannot
> prequalify the operating range offline, then the current operational rule is
> **not a purely closed-form online method** — obtaining `base_pass` for an
> uncovered `q_p` would require a new offline baseline run (or a conservative
> fallback). This limitation is reported, not hidden, and no classifier is trained
> to circumvent it.

---

## 3. Direct answers

- **Q1 (definition):** per-(cell, q_p) flag from a pedestrian-only (`q_r=0`)
  SUMO–JuPedSim baseline, 30 seeds, per-seed ≥29/30 on
  `mean_density <= 1.20 AND 0.90 <= flow_ratio <= 1.20`; speed retention vacuous.

- **Q2 (deployment):** **offline prequalification** (Case B). Not directly
  observable (Case A), not live-per-query (Case C), with the continuous-`q_p`
  caveat above.

- **Q3 (method positioning):** the method is **not** "input W and q_p ⇒ quota" in a
  purely closed-form sense. It is
  **offline sidewalk qualification + online closed-form quota assignment**, where
  the online closed form takes `(W, q_p, base_pass, applicability flag, precomputed
  metadata)` as inputs.
