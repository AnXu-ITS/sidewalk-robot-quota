# 配送机器人进入人行道后的道路配额算法：研究方向更新版

> **Research Direction Update | 2026.08**  
> **Working title:** *How Many Delivery Robots Can a Sidewalk Handle? A Pedestrian-Priority Quota Algorithm for Sidewalk Robot Traffic*

---

## 0. 本轮更新的核心变化

原研究方向将自主配送机器人视为一种新的 pedestrian–robot mixed traffic，重点研究 robot flow 对 pedestrian capacity、LOS、fundamental diagram 与监管阈值的影响。

本轮将研究目标进一步收紧为一个更明确、可落地、可验证的交通工程问题：

> **给定一段人行道的行人流量 \(q_p\) 和有效宽度 \(W\)，设计一个只依赖这两个核心输入的机器人道路配额算法，输出该人行道在不显著损害行人服务水平前提下允许进入的最大配送机器人流量 \(q_r^{quota}\)。**

研究不再以“机器人如何在人群中导航”为主线，也不以机器人速度、感知、路径规划或复杂社会导航策略为主要贡献。机器人在第一篇论文中被标准化为一个 **reference robot**，其尺寸、目标速度和基本避让模型固定。

最终产物应当是一个交通工程师可以直接使用的 quota rule，而不是一个机器人控制器。

---

# 1. 终极研究目标

## 1.1 最终要解决的问题

对于任意局部人行道设施，只要获得：

1. **当前或设计行人流量 \(q_p\)**；
2. **人行道有效宽度 \(W\)**；

算法即可输出：

\[
\boxed{
\hat q_r = f(q_p,W)
}
\]

其中：

- \(q_p\)：pedestrian flow，例如 ped/min；
- \(W\)：effective sidewalk width，例如 m；
- \(\hat q_r\)：recommended robot quota，例如 robot/min。

其含义不是“机器人最多物理上塞得下多少”，而是：

> **在维持 pedestrian-first 服务标准的前提下，这段人行道最多应允许多少机器人进入。**

---

## 1.2 论文最终不应该只回答

- “机器人让行人平均速度下降了多少？”
- “机器人流量增加后 LOS 是否下降？”
- “机器人与行人会不会发生局部冲突？”

这些都只是形成 quota rule 的中间证据。

论文真正要回答的是：

\[
\boxed{
\text{Pedestrian flow} + \text{Sidewalk width}
\rightarrow
\text{Maximum admissible robot flow}
}
\]

即：

> **How many delivery robots should be admitted to a sidewalk under a given pedestrian demand and sidewalk width?**

---

# 2. 研究对象重新定义

## 2.1 从机器人导航问题转向公共空间配额问题

研究对象不再是单台机器人，而是：

> **人行道作为一种稀缺公共交通空间，如何在 pedestrian priority 前提下分配一部分通行容量给 autonomous delivery robots。**

因此研究逻辑从：

\[
\text{Pedestrian environment}
\rightarrow
\text{Robot performance}
\]

转为：

\[
\text{Pedestrian demand} + \text{Sidewalk geometry}
\rightarrow
\text{Available robot quota}
\]

机器人不是被评价的主体，而是占用 pedestrian facility capacity 的新增交通参与者。

---

## 2.2 第一篇论文的刻意简化

为了得到可解释、可推广的 quota algorithm，第一篇论文主动固定以下因素：

- robot reference dimensions；
- robot nominal speed；
- basic collision-free / avoidance behavior；
- robot route direction规则；
- pedestrian behavior model；
- local facility type。

主实验只系统改变：

\[
q_p,\quad W,\quad q_r
\]

即：

- 行人流量；
- 有效人行道宽度；
- 机器人流量。

机器人速度不是主变量。

机器人速度、尺寸或行为差异只在最后做少量 sensitivity analysis，用来证明 quota algorithm 对合理参数扰动是否稳定，而不发展成另一篇机器人导航论文。

---

# 3. 核心科学问题

## RQ1 — 配额是否可计算？

给定 \(q_p\) 与 \(W\)，是否存在稳定、可重复识别的最大可接受机器人流量：

\[
q_r^*(q_p,W)
\]

使得机器人流量在该值以下时 pedestrian service 基本保持可接受，而超过该值后性能开始明显退化？

---

## RQ2 — 是否可以形成简单的工程算法？

simulation-derived quota surface 是否能够被压缩为：

\[
\hat q_r=f(q_p,W)
\]

并满足：

\[
\frac{\partial \hat q_r}{\partial q_p}\leq 0
\]

\[
\frac{\partial \hat q_r}{\partial W}\geq 0
\]

即：

- 人越多，允许机器人越少；
- 人行道越宽，允许机器人越多。

---

## RQ3 — 算法能否在真实新加坡人行道几何中保持有效？

算法不只在人工长走廊中验证，而是在新加坡真实 footpath geometry 切分得到的多个局部 sidewalk cells 中验证。

---

## RQ4 — 配额算法是否“安全侧保守”？

对于交通监管而言：

\[
\hat q_r > q_r^*
\]

比

\[
\hat q_r < q_r^*
\]

更严重。

因此算法不仅要追求平均误差低，还应尽量避免 **over-allocation**。

---

# 4. Ground Truth：算法到底和什么比较？

## 4.1 不使用现实中的“现成机器人配额”作为 Ground Truth

现实中几乎不存在一个数据库告诉我们：

> “宽度 2.4 m、人流 35 ped/min 的人行道应允许 7.2 robot/min。”

因此本研究不依赖不存在的现实标签。

Ground Truth 由经过真实场地校准的 microscopic simulation 独立生成。

更严谨的论文术语建议使用：

- **simulation-derived reference quota**；
- **maximum feasible robot quota**；
- **benchmark quota**；

而不是在没有真实大规模机器人实验时过度声称为 absolute empirical ground truth。

---

## 4.2 最大可行机器人配额

对任意：

\[
(q_p,W)
\]

首先运行 pedestrian-only baseline：

\[
S_0(q_p,W)
\]

然后逐步增加机器人流量：

\[
q_r=0,\Delta q_r,2\Delta q_r,\ldots
\]

得到 mixed-flow 状态：

\[
S(q_p,W,q_r)
\]

定义：

\[
\boxed{
q_r^*
=
\max
\left\{
q_r:
\Pr\left[C_p(q_p,W,q_r)=1\right]\geq 0.95
\right\}
}
\]

其中 \(C_p\) 表示 pedestrian service constraints 是否全部满足。

这里的 0.95 表示：

> 在不同随机种子下，至少 95% 的仿真重复实验都能满足行人服务要求，该机器人流量才被认为“可接受”。

这比仅比较平均值更适合作为监管配额。

---

# 5. Pedestrian-first 服务约束

第一篇论文建议采用 **相对基线 + 绝对底线** 的方式。

## 5.1 主约束：平均步行速度保持率

\[
R_v=
\frac{\bar v_p(q_r)}
{\bar v_p(0)}
\]

基准方案：

\[
R_v\geq 0.90
\]

即机器人加入后，行人平均速度相对于相同场地、相同行人需求下的 pedestrian-only baseline 下降不超过 10%。

---

## 5.2 通行稳定性约束

\[
R_q=
\frac{q_{p,out}}{q_{p,in}}
\]

在稳定观察窗口内，应接近 1。

如果持续出现：

\[
q_{p,out}<q_{p,in}
\]

并形成不断增长的 accumulation / queue，则说明该 robot flow 已造成设施失稳。

---

## 5.3 LOS / density 绝对底线

在条件允许时加入一个 pedestrian LOS 或局部密度底线。

原则是：

> 即使相对无机器人 baseline 只下降 5%，也不能允许人行设施本身已经进入不可接受拥挤状态。

若 pedestrian-only baseline 已经不满足最低服务标准，则：

\[
q_r^*=0
\]

---

## 5.4 阈值敏感性

10% 不作为不可讨论的“真理”。

应至少测试：

\[
\delta_v=5\%,10\%,15\%
\]

从而得到：

- conservative quota；
- base quota；
- permissive quota。

这样监管者可以根据不同政策偏好选择配额强度。

---

# 6. 配额算法的推荐形式

## 6.1 基础形式

最终算法：

\[
\boxed{
\hat q_r=f(q_p,W)
}
\]

算法只需要两个主输入。

不建议第一篇论文直接使用复杂深度神经网络，因为二维输入问题更适合形成透明、可解释的交通工程公式。

---

## 6.2 推荐的 normalized formulation

先计算单位有效宽度的 pedestrian demand：

\[
x=\frac{q_p}{W}
\]

再定义单位宽度 robot quota：

\[
y=\frac{q_r^*}{W}
\]

拟合单调函数：

\[
y=g(x)
\]

最后得到：

\[
\boxed{
\hat q_r
=
W\cdot
g\left(\frac{q_p}{W}\right)
}
\]

并强制：

\[
g'(x)\leq0
\]

直观含义：

> 当单位宽度承担的行人需求越高，剩余可分配给机器人的通行资源越少。

---

## 6.3 与二维模型同时比较

建议同时建立：

### Model A — Width-normalized engineering curve

\[
\hat q_r
=
Wg(q_p/W)
\]

### Model B — 2D monotonic quota surface

\[
\hat q_r=f(q_p,W)
\]

其中约束：

\[
\partial f/\partial q_p\leq0
\]

\[
\partial f/\partial W\geq0
\]

如果 Model A 与 Model B 精度差异很小，优先采用 Model A，因为更容易转化为规范、表格或查图。

---

# 7. 真实场地：新加坡 sidewalk micro-cells

## 7.1 为什么使用真实场地

本研究不希望最终算法只对一个理想矩形 corridor 有效。

因此采用：

> **真实新加坡 footpath → 几何数字化 → 切分为局部 homogeneous sidewalk cells → 仿真实验**

---

## 7.2 推荐主案例：Bendemeer Road

新加坡 2026 年已针对 AIDEN delivery robot 在 Bendemeer Road 指定区域和指定 footpaths 发布专项豁免。

因此 Bendemeer Road 具有三重价值：

1. 真实新加坡公共 footpath；
2. 与 autonomous delivery robot 具有直接监管关联；
3. 可将研究结论直接解释为 future fleet-level quota problem。

---

## 7.3 “切小块”的方法

不把整个 Bendemeer 路网一次性建成复杂 simulation。

将真实 footpath 按局部几何变化切分为：

\[
Cell_1,Cell_2,\ldots,Cell_n
\]

每个 cell 建议长度约：

\[
20-50\,m
\]

切分点包括：

- sidewalk width 明显变化；
- 固定障碍物出现/消失；
- 转角；
- driveway；
- crossing；
- entrance / bus-stop-like disturbance；
- bottleneck。

### 第一篇核心算法只使用 Type-A cells

Type-A：

- 直线或近似直线；
- 宽度在 cell 内基本稳定；
- 无大型动态干扰；
- 无信号交叉口；
- pedestrian flow 可近似稳定输入。

这些 cells 用于建立：

\[
(q_p,W)\rightarrow q_r^*
\]

### 复杂 cells 用于外部验证

转角、瓶颈、障碍物、出入口等作为 robustness / transferability test。

如果算法在复杂位置失效，也可以形成第二阶段研究：

\[
(q_p,W,\text{geometry factor})
\rightarrow q_r^*
\]

但不让第一篇论文失控。

---

# 8. 有效宽度而不是名义宽度

真实人行道会有：

- 灯杆；
- 树池；
- 垃圾桶；
- 护栏；
- 固定设施；
- 临街家具。

因此核心输入建议定义为：

\[
W=W_{\mathrm{eff}}
\]

即 **effective usable sidewalk width**。

这样即使真实几何复杂，算法仍保持只有两个输入：

\[
q_p,\quad W_{\mathrm{eff}}
\]

而不是把每个障碍物都变成新的模型变量。

---

# 9. 仿真技术路线：SUMO–JuPedSim

正式名称为：

> **SUMO–JuPedSim coupling**

在 SUMO 中可直接调用 JuPedSim pedestrian model：

```text
--pedestrian.model jupedsim
```

或在 SUMO configuration 中设置：

```xml
<pedestrian.model value="jupedsim"/>
```

JuPedSim 提供二维 pedestrian dynamics，适合真实人行道 walkable area，而 SUMO 负责场景、路网、需求与输出组织。

Windows 的 SUMO release 已可集成 JuPedSim，因此第一阶段无需自己维护两个独立仿真器之间的复杂通信框架。

---

# 10. Reference Robot

为了不让研究滑向 robot navigation，第一篇论文定义一个标准 reference robot：

\[
R_0=
(d_r,v_r,\pi_r)
\]

其中：

- \(d_r\)：固定机器人几何尺寸；
- \(v_r\)：固定 nominal speed；
- \(\pi_r\)：固定 basic movement / collision-free behavior。

机器人只作为一种具有固定空间占用和目标速度的移动 agent。

主实验中：

\[
R_0=\text{constant}
\]

不把 robot speed 做成主 factorial variable。

最后只进行很小范围 sensitivity：

\[
v_r^{ref}\pm 20\%
\]

用于判断 quota rule 是否严重依赖速度假设。

---

# 11. 实验生成 Ground Truth 的逻辑

对于每个真实或标准化 sidewalk cell：

1. 固定 \(W\)；
2. 设定 pedestrian demand \(q_p\)；
3. 先运行 pedestrian-only baseline；
4. 逐步增加 robot flow \(q_r\)；
5. 每个组合运行多个随机种子；
6. 判断 pedestrian service constraints；
7. 找到最大可行 \(q_r^*\)；
8. 将：

\[
(q_p,W,q_r^*)
\]

保存为 quota dataset。

最终数据集形式：

| Pedestrian flow \(q_p\) | Effective width \(W\) | Reference quota \(q_r^*\) |
|---:|---:|---:|
| 20 ped/min | 1.8 m | ... |
| 40 ped/min | 1.8 m | ... |
| 60 ped/min | 1.8 m | ... |
| 20 ped/min | 2.4 m | ... |
| 40 ped/min | 2.4 m | ... |

再用这些独立生成的 reference labels 拟合 quota algorithm。

---

# 12. 算法验证指标

不能只使用 MAE。

## 12.1 Quota MAE

\[
MAE=
\frac{1}{N}
\sum_i
|\hat q_{r,i}-q_{r,i}^*|
\]

---

## 12.2 Over-allocation Error

\[
E_{over,i}
=
\max
(0,\hat q_{r,i}-q_{r,i}^*)
\]

这是最重要的错误类型。

---

## 12.3 Over-allocation Rate

\[
OAR=
P(\hat q_r>q_r^*)
\]

---

## 12.4 Under-utilization

\[
U_i=
\max(0,q_r^*-\hat q_r)
\]

用于衡量算法是否过度保守。

---

## 12.5 Service Violation Rate

最关键的最终验证不是“预测值接近标签”，而是：

> 将算法推荐的 \(\hat q_r\) 真正重新放回独立仿真场景后，有多少场景导致 pedestrian service constraints 被违反？

理想目标：

\[
SVR\rightarrow 0
\]

同时 quota 不能过度保守。

---

# 13. 核心实验与验证逻辑

完整证据链：

```text
Singapore real sidewalk
        ↓
Field geometry + pedestrian counts
        ↓
Real-site micro-cells
        ↓
Pedestrian-only calibration
        ↓
SUMO–JuPedSim mixed-flow simulation
        ↓
Exhaustive robot-flow sweep
        ↓
Maximum feasible quota q*r
        ↓
Quota dataset
        ↓
Interpretable quota algorithm
        ↓
Held-out real-site validation
        ↓
Pedestrian-priority robot quota rule
```

---

# 14. 第一篇论文的范围

## 必须做

- 新加坡真实 sidewalk geometry；
- pedestrian flow 实测或可靠现场观测；
- SUMO–JuPedSim；
- pedestrian-only baseline calibration；
- standardized reference robot；
- robot-flow sweep；
- simulation-derived maximum feasible quota；
- \(q_p+W\rightarrow q_r\) 配额算法；
- held-out validation；
- threshold sensitivity。

## 暂时不做

- 端到端机器人感知；
- ROS / Autoware；
- SLAM；
- 多机器人协同路径规划；
- 配送订单调度；
- 电池；
- 收益最大化；
- 大规模城市配送网络；
- 多种复杂 robot navigation policy 对比；
- 把 robot speed 作为核心研究变量。

---

# 15. 最终论文应形成的三个核心成果

## Output 1 — Sidewalk Robot Quota Frontier

二维边界：

\[
q_r^*=F(q_p,W)
\]

展示不同 width × pedestrian demand 下最大机器人流量。

---

## Output 2 — 可执行配额公式

例如最终可能得到：

\[
\boxed{
q_r^{quota}
=
Wg(q_p/W)
}
\]

或一个分段 monotonic equation / lookup table。

---

## Output 3 — 新加坡真实场景验证

证明：

> 一个仅依赖 pedestrian flow 和 effective sidewalk width 的简单 quota rule，在未参与拟合的真实新加坡 sidewalk cells 中，仍能以较低 over-allocation rate 维持 pedestrian service constraints。

---

# 16. 论文贡献重新表述

原方向最强的贡献是：

> “机器人流量 → pedestrian capacity / LOS → fleet-level regulation”。

本轮进一步收敛后，论文贡献可以写成：

1. **提出 pedestrian-priority sidewalk robot quota 问题**：把配送机器人从单机设备管理提升为公共人行空间的流量配额问题。
2. **定义 simulation-derived maximum feasible robot quota**：通过独立 microscopic simulation sweep 形成 \(q_r^*\) reference labels。
3. **建立只使用 pedestrian flow 与 effective sidewalk width 的可解释配额算法**。
4. **在新加坡真实 footpath geometry 上完成校准与 out-of-sample 验证**。
5. **把研究结果直接转化为 robot/min、time-window cap 或 geofenced fleet quota，而不是只报告平均速度变化。**

---

# 17. 推荐论文标题

## 首选

**How Many Delivery Robots Can a Sidewalk Handle? A Pedestrian-Priority Quota Algorithm for Autonomous Delivery Robot Traffic**

## 交通工程取向

**A Sidewalk Robot Quota Model Based on Pedestrian Demand and Effective Width**

## 强调新加坡真实场景

**From Sidewalk Capacity to Robot Quotas: A SUMO–JuPedSim Study Using Real Singapore Footpaths**

---

# 18. 一句话研究定义

> **本研究的终极目标不是解释机器人怎样在人群中走，而是建立一个只输入人行道人流量和有效宽度，就能输出最大可接受配送机器人流量的道路配额算法，并通过真实新加坡场地校准的 SUMO–JuPedSim 微观仿真实验生成独立 reference quota、验证算法的准确性与安全侧可靠性。**

---

# 19. 本轮方法依据与工具说明

- 原研究方向已明确提出将配送机器人从单次 HRI 问题提升为 fleet-scale pedestrian facility performance / regulation 问题。
- Singapore 2026 年的 Bendemeer Road AIDEN exemption 为真实场地和监管背景提供了直接案例。
- SUMO 官方已集成 JuPedSim pedestrian model；Windows release 可直接使用，配置名为 `jupedsim`。
- SUMO–JuPedSim 适合把 pedestrian facility 转为二维 walkable area，并支持真实几何、obstacles 与 pedestrian flow。

### 主要资料

1. Singapore Statutes Online. *Active Mobility (Delta Electronics Int’l (Singapore) Pte. Ltd. — Exemption for Bendemeer Road) Order 2026*, S 374/2026.
2. Eclipse SUMO Documentation. *SUMO–JuPedSim coupling*.
3. Eclipse SUMO Documentation. *Pedestrian Simulation / Model jupedsim*.
4. JuPedSim Documentation. *JuPedSim pedestrian dynamics simulator*.
