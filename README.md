# Sidewalk Robot Quota

**A pedestrian-priority quota algorithm for autonomous delivery robots on sidewalks.**

> Given a sidewalk's **pedestrian flow** `q_p` and **effective width** `W`, output the
> **maximum admissible delivery-robot flow** `q̂_r` that keeps pedestrian service acceptable.

[中文说明](README.zh-CN.md)

---

## Status

This repository is the **authoritative, frozen** record of the refactored experiment
(2026-09). All earlier synthetic straight-corridor work and pre-D2 plans/data have been
moved to [`archive/2026-09-03_旧实验与旧数据/`](archive/2026-09-03_旧实验与旧数据/).
Everything below reflects **this machine's** final method and results.

## Final method (frozen)

Scientific law (width-normalized power law):

```
q_hat_r = 24.37 * W * (q_p / W)^-0.945
```

- `c = 24.37`, `p = -0.945` (width exponent `α = 0.992 ± 0.154`; CI includes 1 → keep `W^1`).
- Additive Q80 safety margin `Δ80 = 3.1068` (pooled Q0.80 of positive residuals; the
  operational `+Q80` step uses LOCO fold-calibrated margins per held-out city).
- Frozen execution order:

```
OOD -> base_pass -> zero_guards -> nominal -> -Δ80 -> Q_low -> q_max -> floor
```

Guardrails: `W_min = 1.6 m`, `x_crit = 33.33` ped/min/m, `q_max = 20` robot/min, and the
`Q_low(W)` low-flow ceiling — these four produce the headline chain. The frozen config
additionally specifies deployment-layer guards: `C(W)` capacity, sharp-corner guard, and
an absolute speed floor (v̄ ≥ 0.8 m/s).

**Headline held-out-city overprediction chain** (LOCO, 7 cities):

| Variant | Overprediction | Max overprediction |
|---|---|---|
| G0 nominal | **25.75 %** | **19** |
| G1 + Q80 | **6.75 %** | **16** |
| G1 + baseline guard | **2.75 %** | **7** |

LOCO MAE (model A): **2.189**.

**Single source of truth:** [`final_freeze/final_quota_method_config.yaml`](final_freeze/final_quota_method_config.yaml)
(+ JSON twin). Frozen runtime: [`final_freeze/src/operational_quota.py`](final_freeze/src/operational_quota.py).
The `quota_params/*.json` files are **superseded pre-D2 calibration** — do not cite
(see `quota_params/SUPERSEDED_DO_NOT_USE.md`).

### Deployment model

> offline sidewalk qualification + online closed-form quota assignment

`base_pass` is a per-(cell, pedestrian-flow) flag from a pedestrian-only (`q_r = 0`)
SUMO–JuPedSim baseline. It is precomputed **offline** as a lookup table; **online** use
queries it, then applies the closed-form rule. It is **not** a closed-form function of
`(W, q_p)` alone.

Baseline criterion (over 30 seeds): mean density ≤ 1.20 ped/m² **and**
0.90 ≤ mean flow ratio ≤ 1.20 (mean-based). The per-seed `≥ 29/30` rule defines the
reference quota `q_r*`; the deployed `base_pass` column follows the mean-based rule and
differs from the per-seed rule in 8/400 decoupled high-q_p rows (documented, no headline
impact).

## Data (D2)

The final reference dataset lives in [`data/final/`](data/final/):

- `full_reference_dataset.csv` — 400 combos (280 main + 120 decoupled), 7 cities.
- Constituent / reference / refinement tables + seed-level baseline/sweep CSVs.
- `SHA256SUMS.txt` — immutable hashes (root dataset hash `b2b6743d…4144e9`).

Key facts: `base_pass` 349 pass / 51 fail; `q_r*` 194 zero / 206 positive; in-domain 164 /
OOD 236; pooled evaluation denominator 400. Provenance chain:
`consolidate_reference.py → refine_boundary.py (64 changed) → merge_datasets.py`
(see `final_freeze/final_d2_provenance.txt` and `final_freeze/D2_RECONSTRUCTION_VERIFICATION.md`).

The 7-city sidewalk geometry dataset is in [`train_test_mapdata/`](train_test_mapdata/)
(GeoJSON, stored via **Git LFS**).

## Reproduction

```bash
# 1) verify the frozen runtime (mechanical self-test)
python final_freeze/src/operational_quota.py

# 2) verify the D2 dataset (shape + counts + base_pass rule)
python final_freeze/src/verify_d2.py data/final/full_reference_dataset.csv
python final_freeze/src/verify_base_pass.py

# 3) reproduce the headline chain from the D2 table in data/final/
python final_freeze/src/reproduce_frozen_chain.py
```

Expected: overprediction `25.75 -> 6.75 -> 2.75 %`, max `19 -> 16 -> 7`.
See `final_freeze/SHA256SUMS.txt` for immutable hashes and
`final_freeze/FINAL_REPRODUCIBILITY_FREEZE_REPORT.md` for the full audit.

## Repository layout

```
.
├── README.md / README.zh-CN.md   # this guide (EN / 中文)
├── final_freeze/                 # FROZEN method: config, runtime, verification docs
│   ├── final_quota_method_config.{yaml,json}
│   └── src/                      # operational_quota.py, reproduce_frozen_chain.py, verify_*.py
├── data/final/                   # D2 dataset + hashes (authoritative)
├── pipeline/                     # real-city calibration pipeline (cells, POI, SUMO driver)
├── train_test_mapdata/           # 7-city sidewalk geometry (GeoJSON via Git LFS)
├── quota_params/                 # superseded pre-D2 params (do not use)
├── archive/2026-09-03_旧实验与旧数据/  # archived prior experiments/plans/data
└── (root .md)                    # research direction / plan / migration notes (2026-09)
```

## Honest scope notes

- All quota references are **simulation-derived** (SUMO–JuPedSim), not real-world
  measured capacity. **No formal real-world safety guarantee is made.**
- Applicability domain: `1.6 ≤ W ≤ 3.0 m`, `q_p ≤ 60`, `x < 33.33`,
  straight-to-mildly-curved geometry (Type A, or Type B with sinuosity ≤ 1.05).
  Out-of-domain inputs require the **OOD fallback** (no closed-form recommendation).
- Pedestrian flows `q_p` are **POI-based priors**, not field counts (stated as such in the papers).
- The reference robot is a capacity proxy (0.96 × 0.70 m footprint, 5 km/h).

## Ground truth engine

Eclipse SUMO + JuPedSim (`--pedestrian.model jupedsim`): pedestrian-only baseline, then an
ascending robot-flow sweep (0→20 robot/min, early stop) until pedestrian-service
constraints break; the breaking point is the reference quota `q_r*`. Protocol: 30 seeds,
per-seed ≥ 29/30 pass as the primary criterion (mean as upper bound), frozen before test
cities are evaluated.

## Requirements

- Python 3.10+ with `numpy`, `scipy`, `pandas`.
- Eclipse SUMO 1.27.1 (with JuPedSim) on `PATH` (`SUMO_HOME`) — only for re-running the
  ground-truth campaign; the frozen reproduction above needs no SUMO.

## License

Private research repository — no public license. Please contact the author before reuse.
