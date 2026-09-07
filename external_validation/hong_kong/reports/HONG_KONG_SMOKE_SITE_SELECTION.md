# Hong Kong External Test — Smoke Site Selection (Q3 & Q4)

## 1. Small-area choice: Sha Tin Town Centre (沙田市中心)

- Rationale: continuous ground-level public sidewalk network, ~1 km class,
  no large plazas/footbridges dominating the footprint, good diversity of
  straight / mildly-curved / complex footway polygons.
- **Study box (HK1980 EPSG:2326):** `(836900, 826100, 838000, 827000)`
  ≈ 1.1 km (E) × 0.9 km (N).
- Ground public footway-type features intersecting the box: **151**.

## 2. Candidate screening

Per-polygon oriented-bounding-box (OBB) metrics were computed in EPSG:2326:
OBB length, OBB width, and `rect_fill = area/(obb_len·obb_wid)` as a
straightness proxy (rect_fill → 1 = straight, low = curved/complex).

| straightness band | count (study box) |
|---|---|
| straight (rect_fill ≥ 0.65) | 55 |
| mild_curve (0.40–0.65) | 45 |
| complex (< 0.40) | 51 |

In-domain width filter (OBB width 1.6–3.0 m, length 20–80 m) → **7 candidates**,
then ranked by `rect_fill` and by cross-section width stability.

## 3. Selected micro-cells

| field | HK-ST-01 | HK-ST-02 | HK-ST-03 |
|---|---|---|---|
| role | **straight (smoke primary)** | different width (straight) | complex diagnostic (OOD) |
| source_id (PG_UID) | `PG4019702R0312` | `PG4019703R0312` | `PG4019765R0312` |
| FEAT_TYPE / LVL | Footway / Ground | Footway / Ground | Footway / Ground |
| L (m) | 50 | 50 | 35 |
| W (representative, m) | **2.331** | **2.657** | 0.921 |
| width_min (central 80%) | 2.320 | 2.627 | 0.810 |
| width_p10 (central 80%) | 2.322 | 2.633 | — |
| rect_fill | 0.992 | 0.963 | 0.334 |
| geometry_type | A | A | C |
| sinuosity | 1.0000 | 1.0000 | 1.0176 |
| applicability_status | **in-domain** | **in-domain** | **OOD/fallback** (W < 1.6) |
| center (WGS84) | 114.1887, 22.3794 | 114.1885, 22.3818 | 114.1852, 22.3800 |

## 4. Width measurement method (Q4)

Width is **never** reported as polygon area ÷ length (that would be a mean
width, not a measured net width). Instead:

1. Compute the oriented bounding box; the long axis is the centerline direction.
2. Cast **perpendicular cross-sections** (spacing 0.5 m) across the polygon at
   each station `s` along the long axis.
3. Record the intersected length (net unobstructed chord) at each station.
4. Report:
   - `width_median` = median over the **central 80%** of the segment (excludes
     end flares where the cross-section grazes the polygon boundary);
   - `width_min` = minimum over the central 80%;
   - `width_p10` = 10th percentile over the central 80%.

The "representative width" `W` fed to the frozen rule is `width_median`.

**Uncertainty flags:**
- End-station cross-sections near the polygon vertices produce near-zero
  chords (graze the boundary) — these are excluded by the central-80% window.
- Curved/complex polygons (HK-ST-03) have an unreliable single OBB width; their
  width is reported as a diagnostic only and they are marked OOD.
- `width_median` is a geometric chord width, NOT a survey "effective unobstructed
  width"; obstructions (planters, poles) are not in `INV_PG` and would require
  the iB1000/imagery cross-check in the formal test.

## 5. Outputs

- `sites/hk_smoke_candidates.{csv,gpkg}` — candidate cell records + polygons.
- `sites/hk_cell_local_geometry.json` — per-cell local centerline + real
  walkable polygon (local metric coords) for SUMO.
- `figures/hk_study_area.png`, `hk_candidate_cells.png`, `hk_width_profiles.png`.
