# Fix History — geometry / spawn-integrity

## Finding 1: OBB straight-axis centreline deviates from the true footway
centreline for tapered / wedge / narrow-neck footways (spawn failure)

**Detected:** Section 5 baseline phase. Two failure signatures appeared in the
`seed_results.csv`:

1. `HK-ST-05` (narrow in-domain, W=1.613) — `inflow=0, outflow=0, speed_count=0`
   for all 30 baseline seeds. Cause: footway polygon is a **wedge** whose OBB
   (38.28 m) includes ~8 m of tapered entry tip; the mini-edge eA spawns at
   x∈[0,0.5] inside the triangular tip, so JuPedSim rejects every agent
   ("too close to geometry boundaries" / "not inside walkable area").
2. `HK-ST-24` (wide in-domain, W=2.472) — `inflow=0, outflow=0` but
   `speed_count≈443`. Cause: real **narrow neck** (width p10≈0.73 m) at the exit;
   pedestrians spawn but cannot traverse the neck, so no personinfo departure is
   recorded (SUMO writes `personinfo` only on trip completion).

In both cases the frozen `_parse` returns `flow_ratio = outflow/inflow = 1.0`
(the `inflow_ped == 0` default), so the mean-based `base_pass` falsely reports
**pass** (density≈0 ≤ 1.2 AND 0.9 ≤ 1.0 ≤ 1.2). This is a spurious pass, not a
real baseline.

**Additional partial degradation** (inflow < 80% of expected `qp*4`):
`HK-ST-16` (50%), `HK-ST-19` (48%) and `HK-ST-22` (68%). These are also
**wedge / tapered** footways (entry cross-section span ≈ 0.74–2.7 m vs the
representative W) whose OBB axis sits near one edge at the entry, so a fraction
of JuPedSim spawn attempts land outside the walkable area. Flow that does spawn
is balanced (outflow≈inflow), but the density is underestimated → biased
(inflated) qr_star. The degradation is bimodal (13 cells at 97–100% inflow vs
5 cells at 0–68%), so the 80% gate cleanly separates the two regimes.

## Attempted fix (recorded, reverted)

Tried re-centring each clipped polygon by its y-centroid
(`translate(cell_local, 0, -centroid.y)`) so the cross-section sits on y=0. This
**does not** fix the wedge cells: their centroid is already ≈0 (the wedge is
area-balanced about the OBB axis), while the *entry* cross-section stays offset.
Re-centring was therefore reverted; the original straight-OBB-axis geometry is
kept, and the four spawn-degraded cells are handled by the spawn-integrity gate
below. Pre-fix originals preserved under `reports/fix_history/geometry_recenter_fix/`.

## Resolution (frozen protocol untouched)

- **Spawn-integrity gate** (added to the sweep runner, does not touch frozen
  files): a cell is "simulation-invalid" if its baseline mean inflow is 0, or
  "spawn-degraded" if mean inflow < 80% of the expected `qp*4` departures in the
  measure window. Simulation-invalid / spawn-degraded cells are **excluded from
  the robot sweep** and their `qr_star` is set to `NaN` (not 0, not a spurious
  pass). They remain in the frozen sample and in every OOD/failure table.
- `HK-ST-05`, `HK-ST-24` → simulation-invalid (excluded).
- `HK-ST-16`, `HK-ST-19`, `HK-ST-22` → spawn-degraded (excluded, documented).
- 13/18 in-domain cells are sweep-valid and carry the external metric.

This is a **data/interface finding** (real footway geometry vs the frozen
rectangular-corridor spawn), not a model-parameter change. No frozen file was
modified; the quota formula, margin, guardrails, and service criteria are
unchanged.
