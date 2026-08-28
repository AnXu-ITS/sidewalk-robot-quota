# 配送机器人道路配额算法实验计划书

> **Experiment Plan | Singapore Real-Site Micro-Cells × SUMO–JuPedSim**  
> **核心任务：** 输入 pedestrian flow 与 effective sidewalk width，输出 maximum admissible robot flow，并用独立仿真实验验证。

---

# 1. 实验总目标

本实验不是为了研究 delivery robot navigation 本身，而是为了回答一个交通工程问题：

> **在给定人行道人流量 \(q_p\) 和有效宽度 \(W\) 的情况下，一段人行道最多允许多少配送机器人流量 \(q_r\)，才能保持 pedestrian-first 的可接受服务水平？**

最终开发：

\[
\boxed{
\hat q_r=f(q_p,W)
}
\]

输入：

- pedestrian flow \(q_p\)；
- effective sidewalk width \(W\)。

输出：

- recommended delivery robot quota \(\hat q_r\)，单位可采用 robot/min 或 robot/h。

---

# 2. 软件方案

## 2.1 正式名称

用户所说的 “SUMO 搭配原生 jeped” 对应：

> **SUMO–JuPedSim coupling**

JuPedSim 已作为 pedestrian model 集成到 SUMO。

启用方式：

```bash
sumo-gui -c scenario.sumocfg --pedestrian.model jupedsim
```

或：

```xml
<pedestrian.model value="jupedsim"/>
```

---

## 2.2 软件职责

### SUMO

负责：

- network / route 管理；
- pedestrian / robot demand generation；
- simulation scenario 组织；
- NetEdit 场景编辑；
- 输出数据；
- 批量运行；
- 后续如有需要可通过 TraCI / libsumo 自动控制实验。

### JuPedSim

负责：

- 2D pedestrian movement；
- pedestrian–pedestrian interaction；
- wall / obstacle interaction；
- bottleneck / lane formation 等 crowd dynamics。

### Python

负责：

- 自动生成实验组合；
- 批量运行 SUMO；
- 解析输出；
- Ground Truth 搜索；
- quota algorithm 拟合；
- 统计分析；
- 画 quota frontier。

---

# 3. 为什么采用 SUMO–JuPedSim

本研究的核心不是车辆交通，而是：

\[
\text{pedestrian–robot mixed flow}
\]

JuPedSim 比 SUMO 默认的 striping pedestrian model 更适合真实 sidewalk 的二维运动。

同时保留 SUMO 的优点：

- NetEdit；
- real network；
- demand；
- route；
- batch simulation；
- traffic-system integration。

因此不需要自己重新开发 pedestrian simulator。

---

# 4. 新加坡真实场地设计

## 4.1 Primary study area

优先建议：

> **Bendemeer Road 指定 AIDEN delivery robot 运行区域中的真实 footpaths**

原因：

- 2026 年 Singapore Active Mobility regulation 已专门允许 AIDEN delivery robot 在该 specified area / footpaths 运行；
- 研究问题与未来 fleet-level robot quota 直接对应；
- 比随机选择一个没有 robot context 的 sidewalk 更有政策解释力。

---

# 5. 不做整片地图：真实场地切成 Micro-Sidewalk Cells

## 5.1 基本思想

不把整个 Bendemeer Road 区域作为一个巨大的仿真网络。

先进行实地或地图侦察，然后将 footpath 切成局部 homogeneous sections：

\[
C_1,C_2,\ldots,C_n
\]

建议：

- 每个 cell 长约 50 m；
- cell 内 sidewalk width 近似恒定；
- cell 内 pedestrian flow 可近似视为稳定输入。

---

## 5.2 切分规则

遇到以下位置时重新切一个 cell：

- width change；
- 转角；
- 固定障碍；
- 树池；
- 灯杆密集区；
- narrowing；
- crossing；
- driveway；
- building entrance；
- bus-stop-like disturbance；
- path merging / diverging。

---

# 6. Cell 分类

## Type A — Core algorithm cells

特征：

- 直线或近似直线；
- 宽度稳定；
- 无 signalized crossing；
- 无明显动态出入口；
- 无大型瓶颈；
- pedestrian flow 可以清楚计数。

**用途：**

建立主算法：

\[
(q_p,W)\rightarrow q_r^*
\]

---

## Type B — Mild complexity

例如：

- 少量固定障碍；
- 轻微 curvature；
- 小范围 width variation。

**用途：**

外部验证。

将宽度转换成：

\[
W_{\mathrm{eff}}
\]

后，检查主算法是否仍成立。

---

## Type C — Complex / OOD

例如：

- crossing；
- strong bottleneck；
- bus stop；
- entrance；
- merge；
- sharp turn。

**用途：**

不用于第一版算法拟合。

只作为 out-of-domain test。

如果显著失败，说明未来需要扩展第三个输入变量，而不是在第一篇论文里强行解释所有复杂场景。

---

# 7. 场地测量计划

每个 micro-cell 建立一个 site sheet。

记录：

| 项目 | 内容 |
|---|---|
| Cell ID | SG-BM-01 等 |
| Cell length | m |
| Physical width | m |
| Effective width | m |
| Fixed obstacles | 类型、位置、尺寸 |
| Geometry | straight / mild curve / bottleneck |
| Direction | uni / bi-directional |
| Pedestrian count | ped/min |
| Observation time | 日期 + 时间段 |
| Mean walking speed | m/s |
| Notes | 特殊活动、天气等 |

---

# 8. 有效宽度定义

算法的 width 不使用简单 curb-to-edge nominal width，而使用：

\[
\boxed{
W=W_{\mathrm{eff}}
}
\]

即真正可持续通行的 effective usable width。

固定障碍造成的宽度损失在 geometry preprocessing 阶段处理。

这样最终算法仍保持：

\[
f(q_p,W)
\]

只有两个输入。

---

# 9. Pedestrian 数据采集

## 9.1 最低要求

每个 Type-A cell 至少需要：

- pedestrian directional flow；
- observation duration；
- rough walking speed sample；
- effective width。

---

## 9.2 建议时间段

为了覆盖不同 demand：

- morning peak；
- midday / off-peak；
- evening peak。

建议多个工作日重复，而不是只观察一天。

---

## 9.3 流量统计

建议用固定断面 count line。

例如每 5 min 一个 observation interval：

\[
q_p=
\frac{N_p}{T}
\]

最终换算为：

- ped/min；
- 或 ped/h。

双向流分别记录：

\[
q_p^{AB},\quad q_p^{BA}
\]

同时保存：

\[
q_p=q_p^{AB}+q_p^{BA}
\]

---

# 10. 几何数据进入 SUMO–JuPedSim

推荐工作流：

```text
Real Singapore sidewalk
        ↓
OneMap / OSM / field measurement
        ↓
NetEdit or DXF geometry correction
        ↓
SUMO pedestrian network
        ↓
2D JuPedSim walkable area
        ↓
Micro-cell simulation
```

对真实 sidewalk 不要求一次性实现 centimetre-level digital twin。

第一篇论文最重要的是：

- width 正确；
- cell length 正确；
- obstacle footprint 合理；
- source / sink 正确；
- demand 正确。

---

# 11. Pedestrian-only Baseline Calibration

任何 robot quota 实验之前，先完成：

\[
q_r=0
\]

的 pedestrian-only calibration。

这是整个 Ground Truth 是否可信的基础。

---

## 11.1 校准变量

优先校准：

- desired pedestrian speed distribution；
- pedestrian radius / body size assumptions；
- inflow process；
- bidirectional split。

不要一开始过度校准几十个参数。

---

## 11.2 校准目标

仿真应基本重现实地：

- mean walking speed；
- directional flow；
- travel time；
- density / accumulation pattern；
- 有条件时的局部 trajectory pattern。

---

## 11.3 Baseline validation

将部分观测时间段用于 calibration，其他时间段留作 validation。

例如：

- 2/3 observations → calibration；
- 1/3 observations → validation。

避免全部现场数据都用于调参。

---

# 12. Reference Robot 建模

## 12.1 原则

本论文不建立完整 autonomous navigation stack。

定义一个：

> **standardized reference delivery robot**

机器人作为一种固定尺寸、固定期望速度的 moving agent。

---

## 12.2 固定参数

主实验固定：

- robot length；
- robot width / radius；
- desired speed；
- route；
- basic collision-free movement。

如果使用 AIDEN 作为现实背景，可确保设定速度不超过该场景法规允许的上限，但不把“速度优化”作为研究问题。

---

## 12.3 SUMO–JuPedSim 中的实现思路

可建立 custom agent / `vType`，为 robot 设置与 pedestrian 不同的：

- length；
- width；
- desiredMaxSpeed。

JuPedSim 中 agent radius 可由自定义 type 的几何尺寸产生。

在这一阶段，robot agent 是 **traffic-capacity proxy**，不是完整物理机器人。

---

# 13. 主实验变量

核心 factorial design 只保留三个变量：

\[
q_p,\quad W,\quad q_r
\]

---

## 13.1 Pedestrian demand \(q_p\)

不要凭空设完全脱离现实的范围。

先通过新加坡现场观测得到：

\[
[q_{p,\min},q_{p,\max}]
\]

然后在这个范围内加密采样，并可适当外推到 planning stress-test demand。

---

## 13.2 Effective width \(W\)

直接来自真实 micro-cells。

同时可对真实宽度做标准化 interpolation，例如：

\[
1.5,\ 1.8,\ 2.1,\ 2.4,\ 2.7,\ 3.0\,m
\]

具体范围以现场实测为准。

---

## 13.3 Robot flow \(q_r\)

从 0 开始逐级增加。

例如：

\[
0,\Delta q_r,2\Delta q_r,\ldots
\]

\(\Delta q_r\) 可先使用较粗步长定位 breakdown 区域，再在临界点附近细扫。

---

# 14. 两阶段 Robot Flow Sweep

为了节省计算量：

## Stage 1 — Coarse Search

粗粒度增加 robot flow，找到首次明显 violation 的区间：

\[
[q_r^L,q_r^U]
\]

---

## Stage 2 — Fine Search

只在该区间内细化：

\[
q_r^L,
q_r^L+\Delta,
q_r^L+2\Delta,
\ldots,
q_r^U
\]

这样不需要对所有机器人流量都做极密集仿真。

---

# 15. 随机重复

每个：

\[
(q_p,W,q_r)
\]

组合至少运行多个 seeds。

建议初始：

\[
N=30
\]

若临界区间置信度不稳定，再增加到：

\[
N=50-100
\]

随机性来自：

- pedestrian arrivals；
- pedestrian desired speed；
- initial positions；
- bidirectional encounters。

---

# 16. Ground Truth / Reference Quota 定义

首先定义 pedestrian service constraint：

\[
C_p
\]

例如 base scenario：

### Constraint A — Speed retention

\[
\frac{\bar v_p(q_r)}
{\bar v_p(0)}
\geq0.90
\]

### Constraint B — Flow stability

稳定统计窗口中：

\[
q_{p,out}\approx q_{p,in}
\]

不能形成持续增长 accumulation。

### Constraint C — LOS / density floor

不能跌破预设最低 pedestrian service level。

---

然后：

\[
\boxed{
q_r^*(q_p,W)
=
\max q_r
\quad
\text{s.t.}
\quad
P(C_p=1)\geq0.95
}
\]

这个 \(q_r^*\) 就是算法训练与验证的 reference quota。

---

# 17. 特殊情况

## Case 1 — Pedestrian-only 已不可接受

如果：

\[
q_r=0
\]

时 pedestrian service 已低于最低标准：

\[
\boxed{
q_r^*=0
}
\]

不能因为“机器人额外影响不大”而继续分配机器人配额。

---

## Case 2 — 全部测试 robot flow 都可接受

继续增加 \(q_r\)，直到找到 breakdown，或将该样本标记为：

> quota above tested upper bound

避免伪造上限。

---

# 18. Ground Truth 数据库结构

最终生成：

```csv
site_id,
cell_id,
width_eff,
ped_flow,
robot_flow,
seed,
mean_ped_speed,
speed_retention,
ped_outflow,
density,
los,
constraint_pass
```

然后聚合得到：

```csv
cell_id,
width_eff,
ped_flow,
max_feasible_robot_flow
```

也就是：

\[
(q_p,W)\rightarrow q_r^*
\]

---

# 19. Quota Algorithm 开发

## 19.1 数据划分

不要随机把同一 cell 的相邻场景拆得到处都是。

建议按 **site / cell hold-out**：

- Training cells；
- Validation cells；
- Test cells。

最终 test cells 必须是算法没见过的真实 sidewalk geometry。

---

## 19.2 Primary algorithm

首先尝试：

\[
x=\frac{q_p}{W}
\]

\[
y=\frac{q_r^*}{W}
\]

拟合：

\[
y=g(x)
\]

并强制：

\[
g'(x)\leq0
\]

最终：

\[
\boxed{
\hat q_r
=
Wg(q_p/W)
}
\]

---

## 19.3 Comparison algorithm

建立二维 monotonic response surface：

\[
\hat q_r=f(q_p,W)
\]

约束：

\[
\frac{\partial f}{\partial q_p}\leq0
\]

\[
\frac{\partial f}{\partial W}\geq0
\]

比较两种算法。

如果 normalized formula 精度已经足够，则优先选择简单公式。

---

# 20. Algorithm Validation

## 20.1 Prediction error

\[
MAE=
\frac{1}{N}
\sum|\hat q_r-q_r^*|
\]

同时报告 RMSE。

---

## 20.2 Over-allocation

\[
E_{over}
=
\max(0,\hat q_r-q_r^*)
\]

报告：

- mean over-allocation；
- maximum over-allocation；
- over-allocation rate。

---

## 20.3 Under-allocation

\[
E_{under}
=
\max(0,q_r^*-\hat q_r)
\]

用于判断算法是否过度保守。

---

# 21. 最关键的闭环验证

算法预测以后，必须把：

\[
\hat q_r
\]

重新输入 held-out SUMO–JuPedSim scenario。

流程：

```text
Held-out real cell
      +
Observed q_p
      +
Measured W_eff
        ↓
Quota Algorithm
        ↓
Predicted quota q_hat_r
        ↓
Run SUMO–JuPedSim again
        ↓
Does pedestrian service still pass?
```

最终计算：

\[
\boxed{
SVR=
\frac{\text{algorithm-recommended scenarios violating pedestrian constraints}}
{\text{all test scenarios}}
}
\]

这比仅说“MAE 很低”更能证明算法可用于监管。

---

# 22. 阈值敏感性实验

主方案：

\[
\delta_v=10\%
\]

另外测试：

\[
5\%,15\%
\]

分别形成：

- strict quota；
- normal quota；
- permissive quota。

最终甚至可以形成三档政策表。

---

# 23. Robot 参数敏感性：只做最少量

因为机器人速度不是论文主线，只安排一个 robustness experiment。

例如：

\[
v_r=
0.8v_r^{ref},
v_r^{ref},
1.2v_r^{ref}
\]

机器人尺寸同理只做小范围变化。

问题只回答：

> Quota formula 是否对 reference robot parameter 的合理变化保持稳定？

如果变化很小，则支持第一篇论文的简化。

如果变化很大，再作为第二篇论文研究：

\[
f(q_p,W,\text{robot class})
\]

---

# 24. 推荐实验矩阵

以下为框架，不在没有现场数据前锁死最终数值。

假设最终得到：

- 6 个 effective width levels；
- 8 个 pedestrian demand levels；
- 10–15 个 robot flow levels；
- 30 seeds。

规模约：

\[
6\times8\times12\times30
=
17,280
\]

个 simulation runs。

实际使用 two-stage threshold search 后，运行量可以显著下降。

---

# 25. 实验阶段划分

## Phase 0 — Collision audit

目标：

确认没有论文已经提出几乎相同的：

\[
(q_p,W)\rightarrow robot\ quota
\]

公式。

输出：

- prior-art table；
- final novelty statement。

---

## Phase 1 — Singapore site reconnaissance

目标：

确定 Bendemeer Road 内适合的真实 footpath cells。

任务：

- 获取 regulation schedule map；
- 现场走查；
- 宽度测量；
- obstacles 记录；
- 选择 Type A/B/C cells。

输出：

- site inventory；
- cell map；
- cell geometry table。

---

## Phase 2 — Pedestrian data collection

目标：

得到真实 \(q_p\)、walking speed 和 baseline conditions。

输出：

- pedestrian flow dataset；
- directional split；
- speed samples；
- observation metadata。

---

## Phase 3 — SUMO–JuPedSim testbed

目标：

建立真实 micro-cell digital testbed。

输出：

- `.net.xml`；
- `.rou.xml`；
- `.sumocfg`；
- additional walkable area / obstacle files；
- reproducible run scripts。

---

## Phase 4 — Pedestrian-only calibration

目标：

证明 SUMO–JuPedSim 至少能够合理重现场地的 pedestrian baseline。

输出：

- calibration parameters；
- observed vs simulated plots；
- hold-out validation error。

---

## Phase 5 — Robot reference model

目标：

建立固定 reference robot。

输出：

- robot vType；
- dimensions；
- speed；
- source / sink；
- fixed routes。

---

## Phase 6 — Ground Truth generation

目标：

对 \(q_p\times W\times q_r\) 做 automated sweep。

输出：

\[
q_r^*(q_p,W)
\]

数据集。

---

## Phase 7 — Quota algorithm

目标：

得到：

\[
\hat q_r=f(q_p,W)
\]

输出：

- engineering formula；
- quota lookup table；
- quota frontier surface。

---

## Phase 8 — Held-out real-site validation

目标：

证明算法在未参与拟合的新加坡真实 micro-cells 中有效。

输出：

- MAE / RMSE；
- over-allocation rate；
- under-allocation；
- service violation rate。

---

## Phase 9 — Robustness

目标：

测试：

- service threshold；
- robot speed small perturbation；
- robot size small perturbation；
- mild geometry complexity。

---

# 26. 核心图表设计

论文至少应有以下图。

## Figure 1 — Problem definition

```text
Pedestrian flow q_p
        +
Effective width W
        ↓
Robot Quota Algorithm
        ↓
Allowed robot flow
```

---

## Figure 2 — Singapore site → micro-cells

真实 Bendemeer Road 区域地图：

```text
Real Footpath
 ├── Cell A1
 ├── Cell A2
 ├── Cell B1
 └── Cell C1
```

---

## Figure 3 — SUMO–JuPedSim digital cell

展示：

- 2D walkable area；
- pedestrian flow；
- robot flow；
- measurement zone。

---

## Figure 4 — Robot-flow degradation curve

对固定 \(q_p,W\)：

\[
q_r
\rightarrow
R_v
\]

并标出 constraint line 与：

\[
q_r^*
\]

---

## Figure 5 — Robot Quota Frontier

横轴：

\[
q_p
\]

纵轴：

\[
W
\]

颜色或高度：

\[
q_r^*
\]

这是全文最重要的结果图之一。

---

## Figure 6 — Algorithm vs Reference

\[
\hat q_r
\quad vs \quad
q_r^*
\]

---

## Figure 7 — Policy table

最终形成类似：

| Width | Low ped flow | Medium | High |
|---|---:|---:|---:|
| Narrow | quota | quota | quota |
| Medium | quota | quota | quota |
| Wide | quota | quota | quota |

这张表最接近实际城市监管工具。

---

# 27. 实验成功标准

论文不是要求算法 100% 精确，而是达到以下逻辑：

### Condition 1

存在稳定的：

\[
q_r^*(q_p,W)
\]

capacity frontier。

### Condition 2

\(q_r^*\) 随 \(q_p\) 增大总体下降，随 \(W\) 增大总体上升。

### Condition 3

简单 \(f(q_p,W)\) 能在 held-out cells 上较好预测 quota。

### Condition 4

算法推荐 quota 被重新放入仿真时，pedestrian service violation rate 很低。

### Condition 5

算法不会通过极端 under-allocation 来“作弊式安全”。

---

# 28. 什么结果也算有价值？

## 情况 A — 简单公式表现很好

最佳结果。

说明：

> robot quota 本质上主要由 pedestrian demand 与 effective width 决定。

可以直接形成工程规范。

---

## 情况 B — 真实复杂 geometry 中明显失效

也有价值。

说明二维 quota rule 只适合 homogeneous sidewalk cells。

论文可以明确适用域：

> straight / locally homogeneous sidewalks。

未来增加 geometry factor。

---

## 情况 C — Robot speed sensitivity 很小

支持本研究当前简化：

> quota problem 主要由 flow + usable width 决定。

---

## 情况 D — Robot speed sensitivity 很大

第一篇仍可以保留 reference robot framing。

后续扩展：

\[
q_r=f(q_p,W,v_r)
\]

但不需要在本篇强行解决。

---

# 29. 数据与代码目录建议

```text
sidewalk-robot-quota/
│
├── data/
│   ├── singapore_sites/
│   ├── pedestrian_counts/
│   ├── geometry/
│   └── processed/
│
├── sumo/
│   ├── cells/
│   ├── routes/
│   ├── configs/
│   └── additional/
│
├── scripts/
│   ├── build_cells.py
│   ├── generate_demand.py
│   ├── run_baseline.py
│   ├── run_robot_sweep.py
│   ├── find_quota_threshold.py
│   └── validate_quota.py
│
├── outputs/
│   ├── baseline/
│   ├── sweeps/
│   ├── quota_labels/
│   └── validation/
│
├── models/
│   └── quota_algorithm/
│
└── reports/
    ├── site_inventory.md
    ├── calibration_report.md
    └── experiment_log.md
```

---

# 30. 第一轮最小可运行实验（MVP）

在正式去现场前，先验证技术链。

只做：

- 1 个 30 m 直线 sidewalk；
- 3 个 width；
- 3 个 pedestrian flow；
- reference robot；
- robot flow 从 0 递增；
- 10 seeds。

目标不是出论文结果，而是确认：

1. SUMO–JuPedSim 能跑；
2. pedestrian-only baseline 正常；
3. robot agent 能进入二维 walkable area；
4. robot flow 增加后可以观察 pedestrian service change；
5. 自动脚本能够找到 \(q_r^*\)。

只有 MVP 成功后再大量建设 Singapore real-site cells。

---

# 31. 这篇论文的实验逻辑一句话

> **先用新加坡真实人行道校准 pedestrian baseline，再在 SUMO–JuPedSim 中对 pedestrian flow、effective width 和 robot flow 做系统 sweep，定义满足 pedestrian service constraints 的 maximum feasible robot quota \(q_r^*\)，最后用这些独立 reference quotas 拟合并验证一个只输入 \(q_p\) 与 \(W\) 的可解释机器人道路配额算法。**

---

# 32. 官方技术与现实背景依据

1. **Singapore Statutes Online** — *Active Mobility (Delta Electronics Int’l (Singapore) Pte. Ltd. — Exemption for Bendemeer Road) Order 2026*, S 374/2026.  
   该 Order 自 16 June 2026 起允许 AIDEN delivery robot 在指定区域的 specified footpaths 按规定条件运行，并规定 programmed speed 不超过 6 km/h。

2. **Eclipse SUMO Documentation** — *SUMO–JuPedSim coupling*.  
   JuPedSim 已作为二维 pedestrian dynamics model 集成进入 SUMO。

3. **Eclipse SUMO Documentation** — *Pedestrian Simulation*.  
   可通过 `--pedestrian.model jupedsim` 启用；Windows SUMO release 已提供集成。

4. **JuPedSim Documentation** — JuPedSim 为 Python interface + C++ core 的 open-source pedestrian dynamics simulator。
