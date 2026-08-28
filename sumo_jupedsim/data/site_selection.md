# 新加坡真实场地选址（Bendemeer Road，AIDEN 豁免区）— Phase 1 初步产出

> 生成日期：2026-08-22 · 数据源：`data/osm/bendemeer_road.osm`（Overpass API，osm_base 2026-08-20）
> 分析脚本：`scripts/analyze_osm.py` → `data/footway_candidates.csv`

## 1. 地图覆盖（已下载，无需重新下载）

| 项 | 值 |
|---|---|
| 数据源 | OpenStreetMap，Overpass API 导出，2026-08-20 |
| 节点数 | 8,062 |
| 范围 bbox | lat [1.30896, 1.33326] × lon [103.85524, 103.87527]（≈2.7 km × 2.2 km） |
| 步行相关 way | 1,065（footway 589 / cycleway 105 / residential 148 / service 129 / path 5 / pedestrian 1 / …） |
| 直线 15–60 m 候选（Type-A 初步） | **378** |
| 可切分的直线长段（>60 m） | **154**（最长 512 m） |

> 注：直接网络下载（SSO 法规 PDF）被运行沙箱拦截；本地 OSM 为 3 天前导出，覆盖与新鲜度已足够本轮选址。

## 2. Bendemeer Road 对齐（AIDEN 目标走廊）

Bendemeer Road 本体 2 段（primary，共 ≈180 m）：way `74587409`(154.9 m)、`585630283`(25.9 m)，位于 (1.3166, 103.8624)。

其两侧人行道（footway）为**长直连续段**，可直接切 50 m Type-A cell：

| way id | 长度 | 直线度(max turn) | 距 Bendemeer | 起点 (lat,lon) | 可切 cell 数 |
|---|---|---|---|---|---|
| 253918226 | 403.2 m | 5.2° | 8 m | 1.316885, 103.862695 | ≈8 |
| 253918225 | 408.8 m | 7.8° | 12 m | 1.320001, 103.864656 | ≈8 |
| 873552517 | 259.4 m | 2.2° | 6 m | 1.320710, 103.865363 | ≈5 |
| 661246488 | 251.9 m | 5.7° | 10 m | 1.316834, 103.862441 | ≈5 |
| 481099780 | 51.7 m | 1.2° | 7 m | 1.319826, 103.864812 | 1 |
| 861724208 / 861657033 | 21–22 m | 1.6–9.1° | 8–10 m | 1.3167–1.3170, 103.8625–103.8626 | 连接段 |

合计可切 **≈26–28 个 50 m Type-A 候选 cell**（覆盖算法主实验所需宽度/流量网格绰绰有余）。

## 3. 有效宽度：OSM 几乎无 width 标签 → 必须现场补测

589 条 footway 中仅 **6 条带 width 标签**；带标签的 way 全表仅 9 条：

- `846475681` footway **2.0 m**（210.9 m，距 Bendemeer 30 m）
- `1120776235` footway **1.5 m**（208.9 m）← **窄走廊，恰落在算法 W_min=1.6 m 悬崖区**
- `1464509030` footway **3.0 m**（39.8 m）
- `1355697154` footway 2.0 m、`1079082231` footway 2.0 m、`1189801155` footway 0.5 m（仅剩 5 条）

**结论**：真实场地宽度覆盖 1.5–3.0 m，与算法标定区间 `W∈[1.5,3.0]` 完全一致；但绝大多数 footway 无宽度标签，**`W_eff` 必须按计划书 §8 现场测量**（含灯杆/树池/垃圾桶折减）。

## 4. 进展与下一步（更新 2026-08-22）

**已完成的桌面替代（无现场核验）**：

1. ~~现场核实~~ → ⚠️ 改为**桌面推算**：`estimate_site_flow.py` 按用地 + 地铁邻近度推算
   `W_eff` 与 `q_p`，见 `site_flow_estimate.md`（27 个 cell，住宅/商业/地铁前场三语境）。
2. ~~人流采集~~ → ⚠️ 改为**网上信息推算**：用地-流量先验（Fruin/HCM + Tanaboriboon 1986）。
3. ~~几何数字化~~ → ✅ `netconvert --osm-files` 转 `bendemeer.net.xml`（1227 条行人边）。
4. ~~切块~~ → ✅ `build_cells.py` 裁出 27 个真实 50 m cell → `cells.json`（含真实折线中心线）。
5. ~~改造 simulator.py~~ → ✅ `run_scenario(..., centerline=...)` 支持真实折线走行区 +
   沿程距离度量；修复 netconvert 坐标归一化错位（`--offset.disable-normalization`）。
6. ~~P1 ground-truth 扫描~~ → ✅ `p1_real_site.py`（6 代表 cell × 2 流量档 × 30 seeds，
   早停 sweep）已跑完 → 结果 `experiment_sumo/outputs/p1_real_site/p1_results.csv`、
   报告 `experiment_sumo/reports/p1_real_site_report.md`。
   违规：A-round 6/12、A-floor 3/12、A-iso 1/12；核心发现 = 稠密真实 cell（地铁 qp=78）
   算法过度分配（预测 4.4 vs 真值 0）、曲率使同宽曲线 cell 配额 −25%。

**真正待做（下一轮）**：

- 按 P1 结论重标定 `x_crit`/`C(W)`（稠密段禁行阈值下移至 x≈28）并把曲率折算进 `W_eff`。
- 论文中把 `W_eff`/`q_p` 标注为**先验估计（prior）**，正式实验前对 2–3 个代表 cell 做
  短时人工计数标定。
- 补 Type-B/C 外部验证（转角/障碍/瓶颈）。
