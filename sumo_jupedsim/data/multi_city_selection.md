# 多城市选网规范（Quota 算法真实路网训练集）

生成时间：2026-08-22
状态：4 城已定（新加坡/伦敦/东京/阿姆斯特丹），本规范定义特征分层、采样区、流量 prior 与下载管线。

## 1. 目标与原则

- 训练一个**通用配额算法** `q̂_r = f(q_p, W_eff, 几何复杂度)`，输入轴为
  `(W_eff, q_p, 几何类型, 语境)`。
- **抽样单位是 cell（50 m 走廊段），不是城市**。城市只是获取多样化 cell 的容器。
- 训练信号 = **真实几何 + 仿真物理**推出的 `q_r*`（SUMO/JuPedSim），非现场实测配额
  （该规则尚不存在可测数据）。

## 2. 特征轴与覆盖预算（~100 cell）

| 轴 | 分层 | 目标 cell 数 | 备注 |
|---|---|---|---|
| 宽度 W_eff | 1.0–1.5 m（窄） | ~20 | 撞 W_min=1.6 悬崖的样本 |
| | 1.5–1.8 m（悬崖，最密） | ~30 | **信息量最大** |
| | 1.8–2.4 m（中） | ~25 | |
| | 2.4–3.5 m（宽） | ~20 | |
| | >3.5 m（超宽，可选） | ~10 | 被 q_max=20 主导，低优先 |
| 几何类型 | A 直线 | ~40 | Bendemeer 已有 27 |
| | B 曲线 | ~20 | 阿姆斯特丹运河 |
| | C 瓶颈（杆/树池/桥/站台） | ~25 | 伦敦/东京 |
| | D 路口/换乘前场 | ~15 | 东京/伦敦车站 |
| 语境 | 住宅 | ~35 | |
| | 商业 | ~30 | |
| | 换乘前场 | ~25 | |
| | 旅游/混行 | ~10 | |

（三轴重叠，非相加；总 ~100 cell。）

## 3. 四城分工与采样区（bbox）

| 城市 | 分工（补什么） | 采样区 | bbox (S,W,N,E) |
|---|---|---|---|
| **新加坡**（锚点） | 基线 + 宽段 + 少量 B/C | Bendemeer（已有 27 cell） | 已下载 `osm/bendemeer_*.osm` |
| **伦敦** | 窄 + 瓶颈 + 高客流 | Soho / Covent Garden / West End | 51.506, -0.144, 51.518, -0.118 |
| **东京** | 超窄 + 杆/贩卖机瓶颈 + 换乘前场 | 新宿站 + 歌舞伎町 | 35.685, 139.693, 35.700, 139.708 |
| **阿姆斯特丹** | 曲线 + 桥瓶颈 + 人骑混行 | Jordaan + 运河带 | 52.358, 4.868, 52.378, 4.902 |

**每城 cell 配额**（目标）：新加坡 ~35（已 27），伦敦 ~25，东京 ~25，阿姆斯特丹 ~15。

## 4. 流量档采样（每 cell 2–3 档，按 x=q_p/W 打点）

不在"城市专属流量常数"上做文章，而是对每 cell 按目标单位流量 `x` 反推 `q_p = x·W`：

| x 目标 | 用途 | 示例 (W=1.5) | 示例 (W=2.5) |
|---|---|---|---|
| ~10 | 幂律低端 | 15 | 25 |
| ~20 | 幂律中部 | 30 | 50 |
| ~28–32 | **容量边界（最值钱）** | 42–48 | 70–80 |

每 cell 优先采**峰低/峰高**两档，若语境流量先验允许，加第三档打容量边界。

## 5. 统一流量 prior（保持算法通用）

`q_p = x_ctx · W_eff`，`x_ctx` 为**语境→单位宽度流量**（ped/min/m），沿用 Fruin/HCM LOS +
Tanaboriboon et al. 1986 新加坡标定（自由流 ~1.25 m/s 一致）：

| 语境 | 峰时 x_ctx | 非峰 x_ctx |
|---|---|---|
| 住宅 | 5–12 | 1.5–3 |
| 商业 | 15–25 | 4–7 |
| 换乘/地铁前场 | 30–45 | 8–12 |
| 旅游/混行 | 20–35 | 6–10 |

城市差异只通过**语境构成 + 几何**进入模型，不引入"城市专属流量常数"。

## 6. 下载与处理管线

1. **下载**（Overpass API，`curl.exe -X POST --data-urlencode data@query`）：
   - `<city>_road.osm`：`highway∈{footway,pedestrian,path,living_street}` 或
     `foot∈{yes,designated}` 或 `sidewalk∈{both,left,right,yes}` 的 way + 节点。
   - `<city>_poi.osm`：`amenity`、`shop`、`landuse`、`railway`(station/subway_entrance)、
     `building`（用于语境分类）。
   - 输出目录 `sumo_jupedsim/data/osm/<city>/`。
2. **几何分类**：`analyze_osm.py` ✅ 已参数化（`--osm <city> --out <city>.csv`，A/B/C/D 判别）。
3. **切块**：`build_cells.py` ✅ 已参数化（`--city`、§2 预算分层选取、统一 `cells.json` 带 city 字段，50 m cell，切点对齐 crossing/barrier）。
4. **流量推算**：`estimate_site_flow.py` ✅ 已参数化（读 `cells.json`，用各城 `<city>_poi.osm` 的 shop/amenity/landuse/railway 做 POI 语境分类，回写 `context`/`q_p`；新增 §5 的"旅游/混行"档。见 `context_coverage.md`）。
5. **ground truth**：`p1_multicity.py` ✅（参数化版 `p1_real_site`：四城全 cell、分层抽样 `--limit`、30 seeds、早停 sweep、断点续跑）。输出 `outputs/p1_multicity/multicity_results.csv`（带 city 字段）。

## 7. 复验与训练策略

- **训练集**：新加坡 + 伦敦 + 东京（~85 cell）——拟合 C(W) 与（若样本足够）幅度。
- **外部效度 holdout**：阿姆斯特丹（~15 cell）——不参与拟合，测跨城迁移。
- 保留合成 `(c,p)` 幂律 + A-floor 部署规则，除非真实 cell 累积 ≥50–100 才在
  合成+真实合并上重拟幅度。
- 明确排除：威尼斯式台阶/桥（轮式不可通行）属"排除规则"，不进配额训练集。

## 8. 下一步

- [x] 下载伦敦/东京/阿姆斯特丹 OSM（`osm/<city>/`，road + poi，`download_osm.py`）。
- [x] 参数化 `analyze_osm.py` / `build_cells.py` 支持多城市与 B/C/D 类型。
- [x] 每城跑 §3 采样区 → 生成 cell 清单，按 §2/§4 网格核对覆盖（见 `cell_coverage.md`：A/B/C/D = 40/20/25/15 全达标，窄 19/20、中 23/25、宽 18/20、超宽 5/10（可选档）；语境轴见 `context_coverage.md`：住宅 45 / 商业 20 / 前场 14 / 旅游混行 21）。
- [ ] 跑 ground truth 并复验（`p1_multicity.py`：先 ~20 代表 cell 验证，再全量 100 cell 后台分批；`fit_multicity.py` 做三城训练 + 阿姆斯特丹留出 + Type-B/C 验证）。
