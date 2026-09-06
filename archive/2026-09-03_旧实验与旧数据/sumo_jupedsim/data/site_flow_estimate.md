# Bendemeer 走廊人流推算（桌面估算，无现场核验）

> 生成日期：2026-08-22 · 脚本：`scripts/estimate_site_flow.py` → `data/site_cells_estimate.csv`
> 方法定位：**代替现场计数的桌面估算**，用于把真实 cell 映射到算法输入 `(q_p, W)`；所有数值为区间估计，供仿真实验选网格用，非测量值。

## 1. 数据源与依据

| 输入 | 来源 |
|---|---|
| 几何 / 宽度 | `data/osm/bendemeer_road.osm`（footway）+ `bendemeer_poi.osm`（用地/建筑/POI） |
| 地铁站位置 | `bendemeer_poi.osm` railway 节点（Boon Keng NEL、Bendemeer DTL、Geylang Bahru DTL、Kallang、Lavender） |
| 宽度标准 | LTA：标准 footpath **1.5 m**（有相邻 cycling path 时）；近站/商业更宽 |
| 行人流量水平 | Fruin(1971)/HCM 服务水平框架 + Tanaboriboon et al.(1986)《Pedestrian Characteristics Study in Singapore》（自由流速度 ≈1.25 m/s，与本项目校准值一致） |

## 2. 关键地理发现

Bendemeer 走廊是一条**连接两座地铁站的步行廊道**：

- 北端 **Boon Keng NEL（NE9）**（1.3195, 103.8617）
- 南端 **Bendemeer DTL（DT23）**（1.3136, 103.8627）
- 两站直线 ≈ 650 m，由 Bendemeer Road 两侧 + Boon Keng Road 侧的人行道连通

这条"站间换乘走廊"正是 AIDEN 豁免区的核心步行段，也是人流最受约束（配额最紧）的位置。周边用地为**高密度住宅（HDB）+ 商业 + 轻工业（Kallang）**混合。

## 3. 推算规则（透明、可复核）

- **`W_eff`**：按用地语境赋区间 —— 住宅 1.5–1.8 m / 商业 2.0–2.5 m / 地铁前场 2.2–3.0 m（LTA 标准 1.5 m 为下限；OSM 实测 width 标签 1.5–3.0 m 与之一致）。
- **`q_p`**：先定单位宽流量 `x`（ped/min/m，双向合计），再 `q_p = x·W`（与实验 `PED_FLOWS`、`bidirectional_split=0.5` 定义一致）：
  - 住宅 `x_peak = 5–12`，商业 `x_peak = 15–25`，地铁前场（≤150 m）`x_peak = 30–45`；
  - 非高峰取峰值的 25%。

## 4. 推算结果（27 个 50 m cell）

| 语境 | cell 数 | `W_eff` (m) | `q_p` 峰值 (ped/min) | `q_p` 非峰 (ped/min) | 对应实验范围 |
|---|---|---|---|---|---|
| 住宅（HDB） | 18 | 1.5–1.8 | **8–20** | 2–5 | 低端 ✓（10–20） |
| 商业（沿街） | 5 | 2.0–2.5 | **34–56** | 8–14 | 高端 ✓（30–60） |
| 地铁前场（≤150 m） | 4 | 2.2–3.0 | **78–117** | 20–29 | **超出扫描上限 60** |

明细见 `data/site_cells_estimate.csv`。走廊分配：

- `253918225`（408 m）/ `253918226`（403 m）：Bendemeer Road **东/西侧**人行道（主体住宅段）
- `873552517`（259 m）：Bendemeer Road 北段东侧（商业沿街段）
- `661246488`（252 m）：Boon Keng Road 西侧，南起 Bendemeer 路口、北至 **Boon Keng 站前场**（4 个 MRT 前场 cell 在此）
- `481099780`（52 m）：交叉口连接段

## 5. 关键结论（可直接写进论文）

1. **真实场地的 `(q_p, W)` 几乎全部落在已标定区间内**：住宅段 `q_p≈8–20`、商业段 `q_p≈34–56`、`W≈1.5–3.0 m`，与实验 `q_p∈[10,60]`、`W∈[1.5,3.0]` 高度重合 —— 说明主实验的网格设计**覆盖了真实场景**。
2. **地铁前场峰值为硬约束**：`q_p≈78–117 ped/min` 超出扫描上限，且单位宽流量 `x≈30–45 ped/min/m` 已越过 `x_crit=33.3` → 算法在这些 cell 应输出 **`q̂_r=0`（高峰期禁止机器人）**。这为监管结论"高峰期/站前禁行"提供了量化依据。
3. **窄走廊证据点**：真实场地存在 1.5 m footway（`1120776235`），正好落在 `W_min=1.6 m` 悬崖下方 → 支持"过窄走廊应降额或禁行"的规则。

## 6. 局限与置信度（务必标注）

- `W_eff` 未经实测，**置信度低**（依赖 LTA 标准 + 用地推断）；`q_p` 为数量级估计，**置信度中低**。
- 未建模：信号灯过街（OSM 有 400 crossing / 48 信号灯）、早晚高峰不对称、天气、robot 专用通道占用。
- 建议：论文中把本节定位为"**用地-流量先验估计（prior）**"，正式实验前至少对 2–3 个代表 cell 做一次短时（15 min）人工计数标定系数。

## 7. 下一步

1. 按 §5 的 3 个语境各选 1–2 个代表 cell，用 `q_p` 峰值/非峰 + `W_eff` 中值生成 P1 仿真网格。
2. `netconvert --osm-files` 转网 + `build_cells.py` 裁 50 m cell（几何管线，不依赖现场）。
3. 改造 `simulator.py` 支持真实 cell 几何。
