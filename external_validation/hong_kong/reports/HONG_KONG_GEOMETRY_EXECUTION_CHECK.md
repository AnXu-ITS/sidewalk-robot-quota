# Hong Kong Geometry Execution Check

**Deliverable:** `HONG_KONG_GEOMETRY_EXECUTION_CHECK.md`
**Scope:** Section 2 — confirm the SUMO/JuPedSim scenario actually loads the real
CSDI footway polygon (never silently replaced by an equivalent-area rectangle),
and that entry/exit/boundaries/W/L/area are consistent with GIS.

---

## 1. Was the real polygon loaded, or an equivalent-area rectangle?

Smoke cell **HK-ST-01** (`PG4019702R0312`, Footway / Ground level) was built by
the HK scenario module (`hk_smoke_runner._build_additional_real`) which writes the
real CSDI polygon (local metric coordinates) as `jupedsim.walkable_area`. We
re-parsed the generated `cell.add.xml` and compared it against the GIS source
polygon:

| check | GIS polygon | SUMO `cell.add.xml` polygon |
|---|---|---|
| area (m²) | 116.571 | 116.550 |
| area ratio | — | 0.999822 |
| bounds (x,y) | [0, −1.171, 50, 1.174] | [0, −1.171, 50, 1.174] |
| vertex count | 6 | 6 |
| is a rectangle? | no | **no** |
| symmetric-difference / GIS area | — | **0.000259 (0.026%)** |

**Conclusion:** the loaded polygon is the **real CSDI polygon**, identical to GIS
to within the 3-decimal-metre (1 mm) rounding used when writing the XML. It has
6 vertices and is **not** an equivalent-area rectangle. The 0.026% symmetric
difference is purely the 3-dp rounding of vertex coordinates — not a geometry
substitution.

## 2. Entry / exit / boundaries

Mini-edges parsed from `cell.net.xml`:

| element | coordinates |
|---|---|
| entry edge `eA` | (0.0, 0.0) → (0.5, 0.0) |
| exit edge `eB` | (49.5, 0.0) → (50.0, 0.0) |

Entry is at the west end (x≈0), exit at the east end (x≈50), matching the frozen
corridor convention and the cell travel direction. The walkable area spans
x∈[0,50] with the footway cross-section centered on y≈0 (bounds y∈[−1.171, 1.174]).

## 3. W / L / area / width-profile consistency with GIS

| quantity | value | source |
|---|---|---|
| W (representative) | 2.331 m | perpendicular cross-section median (OBB long axis, central 80%) |
| L | 50.0 m | corridor segment length |
| area | 116.571 m² | GIS polygon |
| L·W | 116.55 m² | 50 × 2.331 |
| area / (L·W) | 1.0002 | — |

Width profile was computed as perpendicular cross-sections along the oriented
long axis (0.5 m spacing, central 80% to exclude end-grazing artefacts). The
reported representative W is the **median**, never area÷length.

## 4. Why do the S1–S4 metrics match the synthetic rectangle?

The smoke-test metrics (speed 1.265 m/s, density 0.113 ped/m², flow ratio 1.0)
are essentially identical to the frozen synthetic-rectangle reference. This is
**expected and correct**, for two reasons:

1. **HK-ST-01 is a straight, near-rectangular footway.** Its rect_fill
   (area / oriented-bbox area) is 0.992, so the real polygon is, to <1%, a
   50 m × 2.33 m rectangle. A real rectangle and a synthetic rectangle must
   produce identical pedestrian-only metrics.
2. **The frozen engine's metric chain is geometry-agnostic where it should be.**
   `_parse` computes density from the FCD positions inside the measure zone
   [15,35] m and flow from the walk arrivals; for a straight uniform corridor
   these quantities do not depend on whether the walkable area was written from
   a buffer or from the CSDI polygon.

This is precisely the desired behaviour: the S1–S4 gate proved the *real-polygon*
pipeline reproduces the frozen reference on a case where the real geometry *is*
rectangular. The generalization signal comes from the non-rectangular formal
cells (curved / width-varying / complex), which is what the formal sweep now
exercises.

## 5. Formal-sample geometry gate (all 32 cells)

Every formal cell's local geometry was machine-checked before simulation:

- **bounds:** walkable polygon must lie in x∈[−0.5, L+0.5], y∈[−W−3, W+3];
- **area ratio:** `area / (L·W)` sanity (fragmented Type-C junctions flagged);
- **centerline:** straight OBB-axis segment (0,0)→(L,0), consistent with the
  frozen corridor convention;
- **width:** perpendicular cross-section median (p10 reported as the stable
  minimum).

Result: 25 of 32 cells passed all checks cleanly. The 7 cells flagged
`area-low` are **complex (Type C) junction polygons** whose oriented bounding
box does not contain a single straight corridor; these are **out-of-domain by the
frozen gate (Type C → None)** and are therefore **not simulated** — they are
retained in the frozen sample and reported under the OOD/fallback analysis
(abstention), never silently dropped.

**Verdict: geometry execution gate PASSED.** No input/geometry substitution was
found; no frozen model file was modified.
