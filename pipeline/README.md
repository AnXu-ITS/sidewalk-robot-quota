# pipeline — 7城真实标定管线（2026-09-03，已具备启动条件）

目标：用真实城市人行道几何+实测宽度重新标定配额公式（合成标定集只做对照基线）。
训练城：NYC / Amsterdam / Melbourne / Taipei / New Taipei（100 cell / 200 combo）；
测试城：Seattle（主）/ Taoyuan（次）（40 cell / 80 combo）。

## 管线链路（全部已验证）

1. `sample_cells.py` — 候选池：线城切 50 m 段 / 面城凸包弦 / 阿姆斯特丹按节点链式串接（转向≤60°、宽度按长度加权）。**所有 cell 恰好 50 m**（尾段<40 m 丢弃，与驱动 L=50 严格一致）。
2. `select_cells.py` — 分层抽样：每城 20 cell（窄<1.6：7 / 中1.6–2.4：7 / 宽2.4–3.5：4 / 超宽≥3.5：2），seed=42、同源≤2、间距≥100 m。
3. `download_poi.py` — Overpass 分块下载（4 cell/块、双端点、3 次重试）→ `osm/<city>_poi.osm`。
4. `annotate_flow.py` — 语境分类（residential/commercial/MRT-frontage/tourism-mixed）+ `q_p_peak = x_ctx × W_eff`；带 POI 覆盖守卫。
5. `project_cells.py` — centerline 经纬度→局部米制（equirectangular），原几何存 `centerline_ll`。
6. `sim/` — 归档实验脚本副本（config/simulator/run_batch/worker/p1_multicity 等 31 个），已改 `CELLS_JSON` 指向 `sim/data/cells.json`；`config.py` 读 `SUMO_HOME` 环境变量（= C:\Program Files (x86)\Eclipse\Sumo，1.27.1 + JuPedSim）。

## 烟测结果（2026-09-03）

- 3 cell × 2 qp × 3 seeds 全链路通过：基线 → Case-1 判零 → 升序扫流 → qr* 推导。
- 修复了两个真 bug：(1) centerline 坐标口径（经纬度 vs 米）导致测速区永远采样为空——已通过 project_cells 修复，修复后 mean_speed 正常、配额行为与 P1b 标定一致（W=1.68/qp=8 → qr*=10）；(2) 阿姆斯特丹链式 cell 尾段合并导致长度 50–90 m——改为严格 50 m。
- 已知边界：W<1.0 m 的 cell（机器人 0.96 m 物理不可通行）在 3-seed 烟测中出现 above_upper 假象，**拟合阶段按 `W < 1.0` 标记 physically_impassable 剔除**（与 P1b 的 W=0.5 窄缝处理一致），准入护栏 W_min=1.6 兜底。

## 启动大规模训练

```powershell
cd C:\Users\xuan1\Desktop\UOL学习\配送机器人workbench\pipeline\sim\scripts
python p1_multicity.py --n-procs 12          # 全量 140 cell / 280 combo / 30 seeds
python p1_multicity.py --skip-sim            # 断点续跑/重推导
```

- 规模预估：280 combo ≈ P1b（200 combo / 10.5 h）的 1.4 倍 ≈ **14–16 h 墙钟**（12 workers），可断点续跑。
- 跑完后：`rescore_seedwise_full.py`（per-seed 判据重打分）→ 拟合（合成=对照基线，真实=主模型，5 城训练 + LOO-CV，Seattle/Taoyuan 留出测试）。

## 协议要点（测试前冻结，事后不改）

1. seeds=30（config N_SEEDS_SWEEP）；判据：per-seed ≥29/30 为主口径，mean 为上界（与论文主口径一致）。
2. q_max=20 扫描上限（config ROBOT_FLOWS_ALL）。
3. 语境分布（POI 实测）：residential 106 / commercial 31 / MRT-frontage 3 / tourism 0——商业+站前合计 24%，高流区覆盖偏少是本次选样的真实构成，报告时如实标注（POI 覆盖守卫：7/20 NYC、4/20 桃园 cell 200 m 内无任何 POI，为真实郊区，非数据缺失）。
4. 测试城（Seattle/Taoyuan）ground-truth 与训练城同批跑出，拟合阶段再按 split 字段切分；模型与协议冻结后再看测试结果。
5. 合成标定集角色：synthetic-only 对照基线（旧 quota_params_final.json），不进主模型训练池。
