# Multi-city cell coverage vs §2 grid

- generated: 2026-08-28
- mode: budget-selected (§2 grid + §3 per-city quota)
- selected cells: 100

## 1. Per-city quota

| city | quota | selected | A | B | C | D | narrow(<1.5 m) |
|---|---|---|---|---|---|---|---|
| singapore | 35 | 36 | 20 | 5 | 6 | 5 | 2 |
| london | 25 | 23 | 8 | 4 | 9 | 2 | 3 |
| tokyo | 25 | 23 | 11 | 3 | 4 | 5 | 13 |
| amsterdam | 15 | 18 | 1 | 8 | 6 | 3 | 1 |

## 2. Grid coverage (selected)

| width \ type | A | B | C | D | row | §2 target |
|---|---|---|---|---|---|---|
| 1.0-1.5 m | 11 | 2 | 6 | 0 | 19 | ~20 |
| 1.5-1.8 m | 8 | 9 | 12 | 6 | 35 | ~30 |
| 1.8-2.4 m | 16 | 2 | 2 | 3 | 23 | ~25 |
| 2.4-3.5 m | 5 | 7 | 2 | 4 | 18 | ~20 |
| >3.5 m | 0 | 0 | 3 | 2 | 5 | ~10 |
| **total** | 40 | 20 | 25 | 15 | 100 | ~100 |
| **§2 type target** | 40 | 20 | 25 | 15 | ~100 | |

## 3. Available pool (all cut cells)

| width \ type | A | B | C | D | row | §2 target |
|---|---|---|---|---|---|---|
| 1.0-1.5 m | 23 | 10 | 15 | 6 | 54 | ~20 |
| 1.5-1.8 m | 3732 | 1653 | 868 | 1344 | 7597 | ~30 |
| 1.8-2.4 m | 467 | 98 | 61 | 194 | 820 | ~25 |
| 2.4-3.5 m | 556 | 285 | 230 | 218 | 1289 | ~20 |
| >3.5 m | 40 | 4 | 9 | 23 | 76 | ~10 |
| **total** | 4818 | 2050 | 1183 | 1785 | 9836 | ~100 |
| **§2 type target** | 40 | 20 | 25 | 15 | ~100 | |

### Context axis (POI-refined, see context_coverage.md)

| context | residential | commercial | MRT-frontage | tourism/mixed |
|---|---|---|---|---|
| selected | 45 | 20 | 14 | 21 |
| §2 target | ~35 | ~30 | ~25 | ~10 |

## 4. Gap check (highlighted)

- **窄 1.0-1.5 m**：已采 19 / 目标 ~20（池内可用 55；东京贡献 13，主要来自 path 默认 1.2 m + 显式 width 标签） — 缺口 1
- **B 曲线**：已采 20 / 目标 ~20（阿姆斯特丹 8 个，quota 15） — 达标
- **C 瓶颈**：已采 25 / 目标 ~25（伦敦 9 个，quota 25） — 达标
- **D 路口前场**：已采 15 / 目标 ~15 — 达标
- **语境**：POI 精化后 住宅 45 / 商业 20 / 前场 14 / 旅游混行 21（详见 `context_coverage.md`）；商业 −10、前场 −11 缺口如实反映采样区构成，旅游混行与零售在混合用地重叠。

## 5. Notes

- W_eff：有 width 标签用标签值，否则按 highway 默认（path 1.2 m、footway 1.5 m、pedestrian 2.5 m、cycleway 2.0 m、living_street 2.2 m、道路 1.5-1.8 m）。OSM 显式 width 标签稀疏，窄档主要靠默认估计。
- context 已由 `estimate_site_flow.py` 用各城 POI（shop/amenity/landuse/railway）精化；q_p = x_ctx·W_eff 回写 cells.json。
- q_p 用 §5 先验 q_p = x_ctx·W_eff（峰时/非峰区间），q_p_src=prior。
- 每 way 最多取 3 个 cell（多样性上限）。
