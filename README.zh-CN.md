# 人行道配送机器人配额（Sidewalk Robot Quota）

**面向人行道自主配送机器人的「行人优先」配额算法。**

> 输入人行道的**行人流量** `q_p` 与**有效宽度** `W`，输出在保证行人服务水平可接受的前提下
> **允许的最大配送机器人流量** `q̂_r`。

[English](README.md)

---

## 状态

本仓库是 **2026-09 大规模重构后的权威冻结记录**。此前的合成直线走廊实验与 D2 之前的
计划/数据已整体归档到 [`archive/2026-09-03_旧实验与旧数据/`](archive/2026-09-03_旧实验与旧数据/)。
以下内容**全部以本机（这台机器）最终方法与结果为准**。

## 最终方法（已冻结）

科学定律（宽度归一化幂律）：

```
q_hat_r = 24.37 * W * (q_p / W)^-0.945
```

- `c = 24.37`，`p = -0.945`（宽度指数 `α = 0.992 ± 0.154`，置信区间含 1 → 保留 `W^1`）。
- 加性 Q80 安全裕量 `Δ80 = 3.1068`（正残差的 Q0.80 池化值；实际的 `+Q80` 步骤采用
  LOCO 按留出城市折式标定的裕量）。
- 冻结执行顺序：

```
OOD -> base_pass -> zero_guards -> nominal -> -Δ80 -> Q_low -> q_max -> floor
```

护栏：`W_min = 1.6 m`、`x_crit = 33.33` 人/min/m、`q_max = 20` 机器人/min、以及
`Q_low(W)` 低流量上限——这四条构成头条链条。冻结配置还规定了部署层护栏：`C(W)` 容量、
急弯护栏、绝对速度下限（v̄ ≥ 0.8 m/s）。

**头条留出城市过配链条**（LOCO，7 城）：

| 变体 | 过配率 | 最大过配 |
|---|---|---|
| G0 名义 | **25.75 %** | **19** |
| G1 + Q80 | **6.75 %** | **16** |
| G1 + 基线护栏 | **2.75 %** | **7** |

LOCO MAE（模型 A）：**2.189**。

**唯一事实来源：** [`final_freeze/final_quota_method_config.yaml`](final_freeze/final_quota_method_config.yaml)
（及 JSON 孪生文件）。冻结运行时：[`final_freeze/src/operational_quota.py`](final_freeze/src/operational_quota.py)。
`quota_params/*.json` 是 **D2 之前的旧标定，已被取代，请勿引用**
（见 `quota_params/SUPERSEDED_DO_NOT_USE.md`）。

### 部署方式

> 离线人行道资格判定 + 在线闭式配额分配

`base_pass` 是每个（细胞、行人流量）上的标志，来自纯行人（`q_r = 0`）SUMO–JuPedSim
基线。它在**离线**阶段预计算为查找表；**在线**使用先查表、再套用闭式规则。它**不是**
`(W, q_p)` 的纯闭式函数。

基线判据（30 个种子）：平均密度 ≤ 1.20 人/m² **且** 0.90 ≤ 平均流量比 ≤ 1.20
（均值判据）。参考配额 `q_r*` 由每种子 `≥ 29/30` 规则定义；部署的 `base_pass` 列遵循均值
判据，在 8/400 条解耦高 q_p 行上与每种子规则有差异（已记录，不影响头条结果）。

## 数据（D2）

最终参考数据集位于 [`data/final/`](data/final/)：

- `full_reference_dataset.csv` —— 400 条组合（280 主实验 + 120 解耦），7 城。
- 构成/参考/精化表 + 种子级 baseline/sweep CSV。
- `SHA256SUMS.txt` —— 不可变哈希（根数据集哈希 `b2b6743d…4144e9`）。

关键事实：`base_pass` 349 通过 / 51 不通过；`q_r*` 194 零 / 206 正；域内 164 / 域外 236；
池化评估分母 400。溯源链：
`consolidate_reference.py → refine_boundary.py（64 条改动）→ merge_datasets.py`
（见 `final_freeze/final_d2_provenance.txt` 与 `final_freeze/D2_RECONSTRUCTION_VERIFICATION.md`）。

7 城人行道几何数据集在 [`train_test_mapdata/`](train_test_mapdata/)
（GeoJSON，经 **Git LFS** 存储）。

## 复现

```bash
# 1) 校验冻结运行时（机械自测）
python final_freeze/src/operational_quota.py

# 2) 校验 D2 数据集（形状 + 计数 + base_pass 规则）
python final_freeze/src/verify_d2.py data/final/full_reference_dataset.csv
python final_freeze/src/verify_base_pass.py

# 3) 由 data/final/ 中的 D2 表复现头条链条
python final_freeze/src/reproduce_frozen_chain.py
```

预期输出：过配率 `25.75 -> 6.75 -> 2.75 %`，最大过配 `19 -> 16 -> 7`。
完整审计见 `final_freeze/SHA256SUMS.txt` 与
`final_freeze/FINAL_REPRODUCIBILITY_FREEZE_REPORT.md`。

## 仓库结构

```
.
├── README.md / README.zh-CN.md   # 本说明（EN / 中文）
├── final_freeze/                 # 冻结方法：配置、运行时、校验文档
│   ├── final_quota_method_config.{yaml,json}
│   └── src/                      # operational_quota.py、reproduce_frozen_chain.py、verify_*.py
├── data/final/                   # D2 数据集 + 哈希（权威）
├── pipeline/                     # 真实城市标定流水线（cells、POI、SUMO 驱动）
├── train_test_mapdata/           # 7 城人行道几何（GeoJSON，Git LFS）
├── quota_params/                 # 已取代的 D2 前参数（勿用）
├── archive/2026-09-03_旧实验与旧数据/  # 归档的旧实验/计划/数据
└── (根目录 .md)                  # 研究方向 / 计划 / 迁移说明（2026-09）
```

## 诚实范围说明

- 所有配额参考均为**仿真推导**（SUMO–JuPedSim），并非真实世界实测容量。
  **不作出任何正式的真实世界安全保证。**
- 适用域：`1.6 ≤ W ≤ 3.0 m`、`q_p ≤ 60`、`x < 33.33`、直行至轻度弯曲几何
  （Type A，或 sinuosity ≤ 1.05 的 Type B）。域外输入必须走 **OOD 回退**（无闭式推荐）。
- 行人流量 `q_p` 为**基于 POI 的先验**，非现场计数（论文中已如实说明）。
- 参考机器人是容量代理（0.96 × 0.70 m 占地、5 km/h）。

## 真值引擎

Eclipse SUMO + JuPedSim（`--pedestrian.model jupedsim`）：先纯行人基线，再做机器人流量
升序扫描（0→20 机器人/min，提前停止）直至行人服务约束被破坏；破坏点即参考配额 `q_r*`。
协议：30 个种子，每种子 ≥ 29/30 通过为主判据（均值为上界），在评估测试城市之前冻结。

## 环境要求

- Python 3.10+，含 `numpy`、`scipy`、`pandas`。
- Eclipse SUMO 1.27.1（含 JuPedSim）置于 `PATH`（`SUMO_HOME`）——仅在重跑真值战役时需要；
  上面的冻结复现不需要 SUMO。

## 许可证

私有研究仓库——无公开许可证。复用前请联系作者。
