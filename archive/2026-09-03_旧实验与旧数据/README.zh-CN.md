# 人行道配送机器人配额算法（Sidewalk Robot Quota）

**一个行人优先（pedestrian-first）的人行道配送机器人道路配额算法。**

> 给定一段人行道的**行人流量** `q_p` 与**有效宽度** `W`，输出在保持行人服务水平可接受的前提下，
> **允许进入的最大配送机器人流量** `q̂_r`。

[English](README.md) · [研究方向](配送机器人_研究方向_Quota算法更新版.md) ·
[实验计划书](配送机器人_实验计划书_SUMO_JuPedSim_新加坡.md) ·
[实验进度与下一步计划](实验进度与下一步计划_2026-08-22.md)

---

## 项目概述

本仓库包含回答下面这个问题所需的代码、数据管线与结果：

> **一段人行道到底能容纳多少台配送机器人？**

本项目不研究"单台机器人如何在人群中导航"，而是把人行道视为一种稀缺的公共空间，回答一个交通工程问题：
在不损害行人服务水平的前提下，能把多少通行能力分配给配送机器人。最终产物是一条简单、可解释的配额规则

$$\hat q_r = f(q_p, W)$$

可以直接转化为监管工具 —— robot/min 上限、时间窗上限或地理围栏内的车队配额。

### 为什么用 SUMO–JuPedSim

Ground truth 由 **Eclipse SUMO 1.27.1 + JuPedSim**（`--pedestrian.model jupedsim`）生成：
SUMO 负责路网、需求与输出组织，JuPedSim 提供适合真实人行道可步行区域的二维行人动力学。
先标定行人-only 基线，再逐级增加机器人流量直到行人服务约束被打破，该临界点即为
**仿真派生的参考配额（simulation-derived reference quota）** `q_r*`。

## 关键结果（SUMO–JuPedSim 主线）

| 结果 | 数值 |
|---|---|
| 参考配额前沿 | 单调：`q_r*` 随 `q_p` 上升而下降、随 `W` 增大而上升（8 宽 × 6 流 × 30 seeds） |
| Model A（宽度归一化幂律） | `q̂_r = W · 28.22 · (q_p/W)^−0.828` |
| 硬归零规则 | `x_crit = 33.3` ped/min/m（合成）→ `29.0`（P1 真实场地重标定）；`W_min = 1.6 m`；与宽度相关的容量 `C(W)`；`q_max = 20` robot/min |
| 训练集 MAE（A / B / A-iso） | 1.54 / 1.19 / 1.31 robot/min |
| 留出集 MAE（A / B / A-iso） | 2.65 / 2.30 / 2.75 robot/min |
| 闭环服务违规率（A-floor） | **0.029** —— 安全侧部署规则 |
| 机器人速度鲁棒性 | ±20 % 速度 → 配额变化 **0** |

一个超出计划的增量成果是 **行人替代当量 PRE（Pedestrian Replacement Equivalent）**：
1 台机器人在 1.5 m 宽人行道上约相当于 **95 名行人**，而在 3.0 m 宽人行道上仅约相当于
**2.3 名行人** —— 说明机器人不能简单当作"多一个行人"。

真实场地验证锚定在**新加坡 Bendemeer Road**（2026 年 AIDEN 配送机器人豁免区域），并正在扩展至
伦敦 / 东京 / 阿姆斯特丹做跨城市迁移验证。完整数据与诚实的局限性说明见
[`experiment_sumo/reports/experiment_report.md`](experiment_sumo/reports/experiment_report.md)。

## 仓库结构

```
.
├── experiment/                      # 纯 Python 社会力模型 MVP（独立、全流程）
│   ├── scripts/                     #   仿真器、ground truth、拟合、验证、绘图
│   ├── data/processed/              #   拟合预测与指标
│   ├── models/quota_algorithm/      #   拟合模型参数（JSON）
│   ├── outputs/                     #   baseline / sweeps / quota_labels / validation / figures
│   └── reports/                     #   实验报告 + 校准报告
│
├── experiment_sumo/                 # SUMO–JuPedSim 主线（主要结果）
│   ├── scripts/                     #   仿真器、fit_quota、validate、sensitivity、P1 真实场地等
│   ├── data/processed/              #   拟合指标
│   ├── models/quota_algorithm/      #   quota_params.json（+ quota_params_p1.json 重标定）
│   ├── outputs/                     #   quota_labels / validation / figures / p1_real_site / p1_multicity
│   └── reports/                     #   experiment_report.md、calibration_report.md、p1_real_site_report.md
│
├── sumo_jupedsim/                   # 真实场地数据管线（OSM → cells → 流量推算）
│   ├── scripts/                     #   download_osm、analyze_osm、build_cells、estimate_site_flow
│   └── data/                        #   cells.json、各城市 cell 表、选址与覆盖说明
│
└── （根目录 .md 文档）               # 研究方向、实验计划书、进度与下一步计划
```

## 快速开始

### 环境要求

- **Python 3.10+**，依赖 `numpy`、`scipy`、`pandas`、`matplotlib`。
- **Eclipse SUMO 1.27.1**（含内置 JuPedSim 行人模型）加入 `PATH` —— 仅 `experiment_sumo/` 与
  `sumo_jupedsim/` 需要；`experiment/` 是自包含的 Python 仿真器，无需 SUMO。

### 复现

```bash
# 1) 纯 Python MVP（无需 SUMO）
cd experiment
pip install numpy scipy pandas matplotlib
python scripts/run_all.py --n-procs 16

# 2) SUMO–JuPedSim 主线（需 SUMO 1.27.1 + JuPedSim）
cd experiment_sumo
python scripts/run_all.py

# 3) 真实场地数据管线
cd sumo_jupedsim
python scripts/download_osm.py          # 下载 OSM 数据（不提交）
python scripts/analyze_osm.py           # 判别 cell 类型（Type A/B/C/D）
python scripts/build_cells.py           # 切 50 m cell + 分层选取
python scripts/estimate_site_flow.py    # 依 POI 语境推算 W_eff 与 q_p
```

原始 OSM 下载与转换得到的 `bendemeer.net.xml` **有意不提交**（可用上述脚本重新生成）。
大型 SUMO 运行转储（`outputs/sumo_tmp/`）、批处理临时目录（`outputs/_batch_tmp/`）与日志
也已通过 `.gitignore` 排除。

## 文档索引

| 文档 | 语言 | 内容 |
|---|---|---|
| `配送机器人_研究方向_Quota算法更新版.md` | 中文 | 研究方向：配额问题、研究问题、算法形式、验证指标 |
| `配送机器人_实验计划书_SUMO_JuPedSim_新加坡.md` | 中文 | 完整实验计划书（阶段划分、ground-truth 定义、验证） |
| `实验进度与下一步计划_2026-08-22.md` | 中文 | 当前进度快照 + 按优先级排序的下一步计划 |
| `experiment_sumo/reports/experiment_report.md` | English | 主线结果（前沿、拟合、留出、闭环、敏感性） |

## 状态与诚实边界说明

- **状态：** 进行中的博士研究。合成直线走廊线路已端到端完成；真实场地（Bendemeer）验证已完成重标定；
  四城外部验证正在运行。
- 参考机器人采用固定尺寸（0.96 × 0.70 m）与速度（5 km/h），作为**容量代理**，而非完整自主导航栈。
- JuPedSim 的 `CollisionFreeSpeedModel` 会把每个个体压缩成标量碰撞圆盘，因此机器人各向异性足迹
  以 0.48 m 圆盘进入仿真；PRE 指标量化了由此产生的机器人当量。
- 场地宽度 / 流量为**基于 OSM + POI 语境的估计值**（现场调查的桌面替代方案）；报告已明确说明。

## 许可

私有研究仓库 —— 暂无公开许可证，使用前请联系作者。
