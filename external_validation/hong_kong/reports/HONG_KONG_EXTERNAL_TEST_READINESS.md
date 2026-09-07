# Hong Kong External Test — Readiness Conclusion (Q7)

## Frozen operational-rule check (read-only, Section 9)

`section9_operational_rule_check.py` loaded the frozen runtime and config
**without modification**:

| check | result |
|---|---|
| c = 24.374155890965095 | match ✓ |
| p = −0.9454494315945483 | match ✓ |
| Δ80 (delta) = 3.1068 (pooled) | match ✓ |
| D2 cities = {amsterdam, melbourne, newtaipei, nyc, seattle, taipei, taoyuan} | **HK absent** ✓ |
| frozen execution order | `OOD → base_pass → zero_guards → nominal → margin → Q_low → q_max → floor` unchanged ✓ |
| guardrails (W_min 1.6, x_crit 33.33, q_max 20, Q_low/C_W knots, sharp-corner, vbar_min 0.8) | unchanged ✓ |
| baseline qualification (30 seeds, ≥29/30, density ≤1.2, flow 0.9–1.2) | unchanged ✓ |

Frozen rule applied to the HK cells (mechanical demonstration only):

| cell | W | q_p | x | in-domain | rule result |
|---|---|---|---|---|---|
| HK-ST-01 | 2.331 | 20 | 8.58 | yes | quota(base_pass=1)=**4.0**; base_pass=0→**0.0** |
| HK-ST-02 | 2.657 | 20 | 7.53 | yes | quota(base_pass=1)=**6.0** |
| HK-ST-03 | 0.921 | 20 | 21.72 | **no** (W<1.6) | **None (OOD)** |

The provisional values (4.0 / 6.0) are a **mechanical** demonstration of the
frozen rule — they are **not** a formal recommendation, because the formal
base_pass (30-seed baseline) and q_r^* (full sweep) have not been run.

## LOCO / margin distinction (re-checked)

- **Δ80 = 3.1068** = pooled Q0.80 positive residual → the frozen **deployment**
  margin used by the runtime (verified above).
- **LOCO 6.75%** = fold-calibrated margins, a separate diagnostic; **not** the
  pooled 3.1068. Not conflated anywhere in this round.

## Answer summary (Q1–Q7)

| Q | answer |
|---|---|
| Q1 sources | Official CSDI: Pavement Polygon `hyd_rcd_1632210918434_60749` (INV_PG) + iB1000 `landsd_rcd_1637223748322_25497` (TileIndex + per-sheet). |
| Q2 download | `/csdi-webpage/file-api` GeoJSON export; curl with retry/resume; SHA-256 recorded. |
| Q3 geometry audit | 1174-feature Sha Tin clip; CRS EPSG:4326→2326; footway/vehicular/transit/refuge classified; 1 invalid + 1 duplicate excluded. |
| Q4 site/width | Sha Tin Town Centre box; 3 cells selected; width via perpendicular cross-sections (central-80% median/min/p10), not area/length. |
| Q5 scenario | Frozen engine reused; real walkable polygon imported; metrics identical to synthetic reference. |
| Q6 smoke | S1–S4 all **PASS**; robot spawn/exit/containment verified; smoke q_r^star=3.0 is code-path only. |
| Q7 readiness | see below. |

## Conclusion

**READY FOR FORMAL EXTERNAL TEST**

The data pipeline, geometry audit, real-geometry scenario construction, and the
full graded smoke chain (S1→S4) all pass on genuine, independent Hong Kong data.
The formal external test (full 30-seed baseline + 0–20 robot-flow sweep, with
the iB1000 building/obstacle cross-check) may proceed. No frozen parameter,
formula, or D2 artifact was modified, and no HK result was used to tune the
frozen method.

**Not performed this round (by design):** the full HK experiment, formula
re-fitting, and any use of HK results to tune frozen parameters.
