# Hong Kong External Test — Geometry Audit (Q2)

Audit of the downloaded `INV_PG` (Pavement Polygon) layer over the Sha Tin
Town Centre clip. Read from the real CRS; no CRS was guessed.

## 1. CRS and pipeline

- **Source GeoJSON CRS: EPSG:4326** (WGS84 geographic) — verified by reading the
  file header, not assumed. (The ArcGIS service layer is natively EPSG:2326;
  the CSDI GeoJSON export is re-projected to EPSG:4326 on delivery.)
- **Working CRS: EPSG:2326 (Hong Kong 1980 Grid)** for all metric measurement.
  WGS84 retained for display / the manifest only.
- Conversion: `pyproj` Transformer `EPSG:4326 -> EPSG:2326`.
- Processed outputs: `data/processed/hk_pavement_sha_tin_clip_{wgs84,hk1980}.gpkg`.

## 2. Clip scope and feature count

- Clip bbox (WGS84): `(114.178, 22.368, 114.202, 22.392)` → Sha Tin Town Centre.
- **Features in clip: 1,174** (full HK `INV_PG` = 64,644 polygons).

## 3. Schema (fields) — null rate

| column | dtype | null rate | n_unique | note |
|---|---|---|---|---|
| OBJECTID | int32 | 0.0 | 1174 | unique |
| PG_UID | str | 0.0 | 1173 | **1 duplicate** |
| FEAT_TYPE | str | 0.0 | 5 | decoded string labels |
| SUR_TYPE_1 | str | 0.0 | 5 | surface material |
| PAVER_TYPE | str | 0.313 | 2 | 31.3% null (paver-specific) |
| LVL | str | 0.0 | 2 | ground vs bridge |
| Shape_Length | float64 | 0.0 | — | native |
| Shape_Area | float64 | 0.0 | — | native |

Geometry column null rate: 0.0.

## 4. Feature-type classification (decoded labels)

| FEAT_TYPE | count | classification |
|---|---|---|
| Footway | 695 | **footway (public sidewalk)** |
| Carriageway | 366 | vehicular |
| Public Transport Interchange - Footway | 44 | transit-zone footway (excluded from public-footway pool) |
| Traffic Island - Refuge Island | 68 | refuge/island (non-walkable for scenario) |
| Carpark - Carriageway | 1 | vehicular |

**Not present in the clip (relevant codes absent):** cycle track, plaza,
footbridge, stair, run-in, side/back lane. Multi-level is captured by `LVL`
rather than a dedicated FEAT_TYPE. Unknown → no "unknown" features observed in
this clip; any future unseen code is marked `Other`.

## 5. Level (multi-level screen)

| LVL | count |
|---|---|
| Ground level | 1100 |
| Level 1 bridge/flyover/structure above ground level | 74 |

The 74 above-ground features (footbridges/elevated structures) are excluded
from the ground-footway candidate pool (avoid multi-level per spec).

## 6. Geometry integrity

| check | result |
|---|---|
| Invalid geometry | 1 (of 1174) |
| Duplicate PG_UID | 1 |
| Multipolygon | 1174 typed as MultiPolygon by source: **1166 single-part** (wrapped) + **8 genuinely two-part** |
| Self-intersection / non-noded | none beyond the 1 invalid feature |

The 1 invalid and 1 duplicate feature were excluded from candidate selection;
the 8 two-part features were retained only if their merged area passed the
width/straightness filters.

## 7. Ground public footway counts (candidate pool)

- Whole clip footway-type: 739 (695 Footway + 44 PTI-Footway).
- Whole clip ground footway-type: **712**.
- Study box (see Q3) ground footway-type intersecting: **151**
  (150 general Footway + 5 PTI-Footway; 146 general Footway at ground).
- The 3 selected cells are all `FEAT_TYPE = Footway`, `LVL = Ground level`
  (no PTI, no bridge, no carriageway).

## 8. Conclusion (Q2)

Data quality is sufficient for smoke-test geometry construction: CRS verified,
fields decoded, classification footway/vehicular/transit/refuge applied,
multi-level screened, integrity issues (1 invalid + 1 duplicate) identified and
excluded. Residual risk: `PAVER_TYPE` 31% null (cosmetic only) and the FGDB
vector cross-check deferred (requires ogr2ogr/ogrinfo, not available here).
