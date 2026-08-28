# Sidewalk Robot Quota

**A pedestrian-priority quota algorithm for autonomous delivery robots on sidewalks.**

> Given a sidewalk's **pedestrian flow** `q_p` and **effective width** `W`, output the
> **maximum admissible delivery-robot flow** `q̂_r` that keeps pedestrian service acceptable.

[中文说明](README.zh-CN.md) · [Research direction](配送机器人_研究方向_Quota算法更新版.md) ·
[Experiment plan](配送机器人_实验计划书_SUMO_JuPedSim_新加坡.md) ·
[Progress & next steps](实验进度与下一步计划_2026-08-22.md)

---

## Overview

This repository holds the code, data pipeline and results behind the question

> **How many delivery robots can a sidewalk handle?**

Instead of modelling how a single robot navigates a crowd, the project treats the sidewalk as a
scarce public space and asks a traffic-engineering question: how much of that capacity can be
allocated to delivery robots **without degrading pedestrian level of service**. The end product is a
simple, interpretable quota rule

$$\hat q_r = f(q_p, W)$$

that a regulator can apply directly — robot/min caps, time-window caps, or geofenced fleet quotas.

### Why SUMO–JuPedSim

The ground truth is generated with **Eclipse SUMO 1.27.1 + JuPedSim**
(`--pedestrian.model jupedsim`): SUMO manages the network, demand and outputs while JuPedSim
provides the two-dimensional pedestrian dynamics suited to real sidewalk walkable areas. A
pedestrian-only baseline is calibrated first, then robot flow is swept upward until the
pedestrian-service constraints break; that breaking point is the **simulation-derived reference
quota** `q_r*`.

## Key results (SUMO–JuPedSim main line)

| Result | Value |
|---|---|
| Reference quota frontier | monotone — `q_r*` ↓ with `q_p`, ↑ with `W` (8 widths × 6 flows × 30 seeds) |
| Model A (width-normalized power law) | `q̂_r = W · 28.22 · (q_p/W)^−0.828` |
| Hard-zero rules | `x_crit = 33.3` ped/min/m (synthetic) → `29.0` (P1 real-site recalibration); `W_min = 1.6 m`; W-dependent capacity `C(W)`; `q_max = 20` robot/min |
| Training MAE (A / B / A-iso) | 1.54 / 1.19 / 1.31 robot/min |
| Held-out MAE (A / B / A-iso) | 2.65 / 2.30 / 2.75 robot/min |
| Closed-loop service violation rate (A-floor) | **0.029** — the safe-side deployment rule |
| Robot-speed robustness | ±20 % speed → quota change **0** |

A headline extra is the **Pedestrian Replacement Equivalent (PRE)**: one robot "costs" as much as
≈ **95 pedestrians** on a 1.5 m-wide sidewalk but only ≈ **2.3 pedestrians** on a 3.0 m-wide one —
so the robot is *not* simply "one more pedestrian".

Real-site validation is anchored on **Bendemeer Road, Singapore** (the 2026 AIDEN delivery-robot
exemption area) and is being extended to London / Tokyo / Amsterdam for cross-city transfer. Full
numbers and honest limitations: [`experiment_sumo/reports/experiment_report.md`](experiment_sumo/reports/experiment_report.md).

## Repository structure

```
.
├── experiment/                      # Pure-Python social-force MVP (standalone, full pipeline)
│   ├── scripts/                     #   simulator, ground truth, fitting, validation, figures
│   ├── data/processed/              #   fitted predictions & metrics
│   ├── models/quota_algorithm/      #   fitted model parameters (JSON)
│   ├── outputs/                     #   baseline / sweeps / quota_labels / validation / figures
│   └── reports/                     #   experiment + calibration report
│
├── experiment_sumo/                 # SUMO–JuPedSim main line (primary results)
│   ├── scripts/                     #   simulator, fit_quota, validate, sensitivity, P1 real-site, ...
│   ├── data/processed/              #   fit metrics
│   ├── models/quota_algorithm/      #   quota_params.json (+ quota_params_p1.json recalibration)
│   ├── outputs/                     #   quota_labels / validation / figures / p1_real_site / p1_multicity
│   └── reports/                     #   experiment_report.md, calibration_report.md, p1_real_site_report.md
│
├── sumo_jupedsim/                   # Real-site data pipeline (OSM → cells → flow estimates)
│   ├── scripts/                     #   download_osm, analyze_osm, build_cells, estimate_site_flow
│   └── data/                        #   cells.json, per-city cell tables, site selection & coverage docs
│
└── (root .md files)                 # Research direction, experiment plan, progress & next steps
```

## Getting started

### Requirements

- **Python 3.10+** with `numpy`, `scipy`, `pandas`, `matplotlib`.
- **Eclipse SUMO 1.27.1** (with the integrated JuPedSim pedestrian model) on `PATH` — required only
  for `experiment_sumo/` and `sumo_jupedsim/`. `experiment/` is a self-contained Python simulator.

### Reproduce

```bash
# 1) Pure-Python MVP (no SUMO required)
cd experiment
pip install numpy scipy pandas matplotlib
python scripts/run_all.py --n-procs 16

# 2) SUMO–JuPedSim main line (requires SUMO 1.27.1 + JuPedSim)
cd experiment_sumo
python scripts/run_all.py

# 3) Real-site data pipeline
cd sumo_jupedsim
python scripts/download_osm.py          # download OSM extracts (not committed)
python scripts/analyze_osm.py           # classify cells (Type A/B/C/D)
python scripts/build_cells.py           # cut 50 m cells + stratified selection
python scripts/estimate_site_flow.py    # estimate W_eff and q_p from POI context
```

Raw OSM downloads and the converted `bendemeer.net.xml` are intentionally **not committed**
(regenerate with the scripts above). Large SUMO run dumps (`outputs/sumo_tmp/`), batch scratch
(`outputs/_batch_tmp/`) and logs are also excluded via `.gitignore`.

## Documentation

| Document | Language | Content |
|---|---|---|
| `配送机器人_研究方向_Quota算法更新版.md` | 中文 | Research direction: the quota problem, research questions, algorithm form, validation metrics |
| `配送机器人_实验计划书_SUMO_JuPedSim_新加坡.md` | 中文 | Full experiment plan (phases, ground-truth definition, validation) |
| `实验进度与下一步计划_2026-08-22.md` | 中文 | Current progress snapshot + prioritized next steps |
| `experiment_sumo/reports/experiment_report.md` | English | Main-line results (frontier, fit, held-out, closed-loop, sensitivity) |

## Status & honest scope notes

- **Status:** in-progress PhD research. The synthetic straight-corridor line is complete end-to-end;
  real-site (Bendemeer) validation is recalibrated; 4-city external validation is running.
- The reference robot uses a fixed footprint (0.96 × 0.70 m) and speed (5 km/h) as a **capacity
  proxy**, not a full autonomy stack.
- JuPedSim's `CollisionFreeSpeedModel` reduces each agent to a scalar collision disc, so the robot's
  anisotropic footprint enters as a 0.48 m disc; the PRE metric quantifies the resulting
  robot-equivalent.
- Field width / flow are **estimates from OSM + POI context** (a desktop substitute for site
  surveys); the reports state this explicitly.

## License

Private research repository — no public license. Please contact the author before reuse.
