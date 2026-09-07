# Hong Kong Failure & OOD Analysis

**Deliverable:** `HONG_KONG_FAILURE_AND_OOD_ANALYSIS.md`
**Status:** written before the robot sweep completed; Section 7/8 metrics append the
sweep-specific failure rows (timeouts / per-level fails) once `hk_sweep_detail.csv`
exists.

This document records, without deletion and without parameter changes:
(1) out-of-domain (OOD) cells that the frozen runtime correctly abstains on;
(2) in-domain cells whose *real geometry* broke the frozen rectangular-corridor
spawn (a data/interface finding, not a model change);
(3) the fix history and the conservative handling applied.

---

## 1. Out-of-domain cells (frozen runtime → `None`, abstention)

The frozen applicability gate (`operational_quota.in_domain`) is
`W∈[1.6,3.0]`, `x=q_p/W<33.33`, `type∈{A,B}`, `type B ⇒ sinuosity≤1.05`, plus
the sharp-corner guard. Of the 32 frozen sample cells, **14 are OOD**; none is
simulated and none contributes a numeric quota. The frozen runtime returns
`None` for all of them (abstention, never a numeric zero, never deleted).

| cell | W (m) | type | sinuosity | rect_fill | OOD reason |
|---|---|---|---|---|---|
| HK-ST-01 | 1.501 | A | 1.0025 | 0.861 | W < 1.6 (narrow) |
| HK-ST-02 | 1.196 | C | 1.1282 | 0.064 | W < 1.6; also Type C |
| HK-ST-03 | 1.554 | A | 1.0017 | 0.781 | W < 1.6 (narrow) |
| HK-ST-04 | 0.995 | C | 1.0307 | 0.115 | W < 1.6; also Type C |
| HK-ST-10 | 1.564 | C | 1.0303 | 0.187 | W < 1.6; also Type C |
| HK-ST-07 | 6.676 | C | 1.1989 | 0.211 | W > 3.0; also Type C |
| HK-ST-23 | 4.853 | C | 1.2629 | 0.250 | W > 3.0; also Type C |
| HK-ST-31 | 3.047 | A | 1.0007 | 0.852 | W > 3.0 (wide) |
| HK-ST-32 | 3.001 | B | 1.0635 | 0.427 | W > 3.0 AND Type-B sinuosity 1.0635 > 1.05 |
| HK-ST-14 | 2.002 | C | 1.0137 | 0.274 | Type C (complex, rect_fill<0.5) |
| HK-ST-17 | 2.034 | C | 1.1629 | 0.063 | Type C (complex) |
| HK-ST-20 | 2.067 | C | 1.0207 | 0.265 | Type C (complex) |
| HK-ST-26 | 2.040 | C | 1.6794 | 0.124 | Type C; very sinuous (1.68) |
| HK-ST-29 | 2.452 | C | 1.0487 | 0.297 | Type C (complex) |

Coverage of the gate: 18/32 in-domain (56.2%), 14/32 OOD (43.8%). The OOD set
is **not** dominated by a single failure mode — narrow (5), wide (4), and
Type-C complex (5, several also narrow/wide) are all exercised, which is the
intended stress on the applicability domain.

## 2. In-domain cells with spawn/flow failure (geometry-method finding)

The frozen simulator assumes a rectangular corridor with full-width cross-sections
at both ends (D2 synthetic cells). Several real HK footways are **tapered / wedge
/ narrow-neck**, so the OBB straight axis used as the corridor centreline deviates
from the true cross-section centre at the ends. JuPedSim then rejects spawns near
the ends ("too close to geometry boundaries" / "not inside walkable area").

Two failure signatures appear in the 30-seed baseline:

1. **Simulation-invalid** (`inflow=0`, no pedestrian departs): the frozen
   `_parse` returns `flow_ratio = 1.0` (its `inflow_ped == 0` default), so the
   mean-based `base_pass` **falsely reports pass**. These would otherwise
   surface as a spurious `qr* = 20`.
   - `HK-ST-05` (W=1.613, narrow): wedge footway, OBB 38.28 m includes ~8 m
     tapered entry tip; every spawn at the entry tip is rejected.
   - `HK-ST-24` (W=2.472): real narrow neck (width p10 ≈ 0.73 m) at the exit;
     agents spawn but cannot traverse the neck.
2. **Spawn-degraded** (`0 < inflow < 0.8 × expected`): wedge/tapered entries
   reject a fraction of spawns → density underestimated → biased (inflated) qr*.
   - `HK-ST-16` (50%), `HK-ST-19` (48%), `HK-ST-22` (68%).

**Handling (conservative, no model change):** a **spawn-integrity gate** in the
sweep runner flags any cell with baseline mean inflow ≤ 0 as `simulation-invalid`
and < 80% of `qp×4` (the expected 4-min measure-window departures) as
`spawn-degraded`. These 5 cells are **excluded from the robot sweep**; their
`qr*` is recorded as `NaN` (not 0, not a spurious pass); they remain in the
frozen sample and in every OOD/failure table. 13/18 in-domain cells are
sweep-valid. See `reports/fix_history/geometry_recenter_fix/FIX_HISTORY.md`.

This is the principal **external-generalization finding so far**: the frozen
method's geometric applicability gate does not detect tapered/wedge/narrow-neck
footways — they pass `W`, `x`, `type`, `sinuosity` yet fail the rectangular
spawn assumption (22% of in-domain cells, 5/18).

## 3. Baseline qualification summary (before sweep)

| count | category |
|---|---|
| 18 | in-domain cells reach Phase B |
| 18 | mean-based `base_pass = 1` (including 5 spurious/degraded, re-classified below) |
| 5 | re-classified by spawn-integrity gate (2 invalid, 3 degraded) → excluded |
| 13 | sweep-valid in-domain cells (97–100% baseline inflow) |

No in-domain cell *fails* the mean-based baseline on density/flow alone; the
re-classification is driven entirely by the spawn-integrity evidence, recorded
above with the pre-fix originals preserved.

## 4. Sweep-level failures

Post-sweep summary (13 sweep-valid cells, 156 level rows in `hk_sweep_detail.csv`):

- **Timeouts:** 0 (no `timed_out=1` rows). No conservative `mean_density=99.0`
  fallback was needed.
- **Baseline-fail:** 0/13 (all sweep-valid cells pass the mean-based base_pass).
- **Zero-quota cells:** 6/13 (HK-ST-06, 08, 09, 13, 15, 25) have operational
  quota 0 — driven by the Δ80 margin + integer floor (nominal − 3.1068 < 1) and/or
  the C(W)/Q_low guardrails. Their qr* = 0 for the three dense cells (HK-ST-06,
  08, 13) but 4, 6, 6 for HK-ST-09, 15, 25 → genuine underprediction.
- **Failure signature at high q_r (dense cells):** `flow_ratio` inflates well above
  1.2 (e.g. HK-ST-06 reaches 1.67 at q_r=1, 3.77 at q_r=10) while `pass_frac`
  collapses to 0 — the D2 "inflow collapses while pre-jam arrivals still land"
  signature, reproduced on HK.
- **Clean transitions (light/wide cells):** HK-ST-18 passes 1.00 up to q_r=12 then
  0.90 at 15; HK-ST-21 passes 1.00 up to q_r=12 then 0.80 at 15; HK-ST-25 passes
  ≈0.97 up to q_r=6 then 0.37 at 8.

No level was re-run or re-selected based on its outcome; the sweep runs the full
12 non-zero robot levels for every sweep-valid cell.
