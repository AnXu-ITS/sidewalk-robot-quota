# Quota-Law Identifiability & Formula Selection Experiment — 报告（进行中）

> 状态：Phase 0 已恢复主扫描（运行中）；Phase 1–2 完成；Phase 3 驱动就绪（待主扫描完成后排队）；
> Phase 5–10 管线已实现并通过归档 P1b 数据干跑验证（dryrun/ 目录）。
> 术语：q_r* 一律称为 **simulation-derived feasible quota references on
> real-world sidewalk geometries**（非真实世界 ground truth）。

## Phase 0 — 主实验冻结与恢复

- 140 cells / 7 城 / 每 cell 2 个语境流量档 / 30 seeds / 相同判据与扫描逻辑——**未改动**。
- 主扫描已恢复（`p1_multicity.py --n-procs 12`，280 combo / 8,400 基线场景，12 workers
  运行中，~14–16 h）。产出将汇总为 `main_280_reference_table.csv`（含 cell_id/city/
  type/context/W/L/qp/x/扫流结果/per-seed pass/fail/pass fraction/q_r*）。

## Phase 1 — 40 代表性 cell 选择（✅ selected_40_cells.csv / .json）

- 分层：5 训练城 × 6 + 2 测试城 × 5 = 40；每城按宽度档配额（窄2/中2/宽1/超宽1，
  测试城窄2/中1/宽1/超宽1），档内优先 Type-B（曲线）保证几何多样性，seed=7。
- 宽度覆盖 0.21–4.98 m（训练城）、0.43–5.0 m（测试城），含 A/B/C 型。
- **长度层说明**：冻结协议下所有 cell 均为 50 m（仿真器按每分钟流量 + 固定 [15,35] m
  测速区构造，对长度不敏感），"short/medium/long" 分层在本实验中不适用——已如实
  记录，不伪造长度多样性。

## Phase 2 — 解耦设计（✅ decoupled_120_design.csv / decoupled_cells.json）

- 40 cell × 统一 x ∈ {18, 24, 30} = 120 combos；q_p = x·W（与语境无关）。
- **72/120 标 out-of-domain**（宽 cell 的 qp>60 或窄 cell 的 W<1.6），标记不裁剪。
- 效果：补充设计中 W ⊥ x（每 cell 三个相同 x），打破主实验 x∈{5,12,...} 聚类。

## Phase 3 — 补充扫描驱动（✅ p1_decoupled.py，待运行）

- 与主实验完全同协议（同 simulator/criterion/30 seeds/同阶梯/同 qr* 规则），
  只换输入（decoupled_cells.json）；输出 decoupled_baseline/sweep/results.csv。
- 运行时机：主扫描完成后（避免 CPU 争抢），`python p1_decoupled.py --n-procs 12`，
  120 combo ≈ 6–7 h。

## Phase 4 — 边界细化（待数据）

- 计划：主+补充扫描完成后，对"最后 feasible / 首次 infeasible 间隔 ≥2"的 combo
  补扫中间档；预估 ~5% 预算（P1b 证据：43/137 combo 边界在档间）。
- 产出 refined_quota_reference_table.csv 与前后 q_r* 变化表。

## Phase 5–10 — 拟合/验证/诊断管线（✅ fit_models.py，已干跑验证）

模型：A（cWx^p）、A+（cW^αx^p，检验 H0:α=1）、L（加 (L/L0)^γ，检验 H0:γ=0）、
R（C(W)[1−(x/x_crit)^β]+）、SVR 黑盒基线；评估 = 护栏（W_min/x_crit/C(W)/
Q_low/q_max）+ floor 后的部署口径；LOCO-city 主验证 + over/under 分侧报告。

**归档 P1b 数据干跑结果（200 combo / 4 城，仅供管线验证，非最终结论）：**

| 模型 | LOCO MAE | LOCO RMSE | 过配率 | 备注 |
|---|---|---|---|---|
| A | 1.849 | 3.414 | 11.2% | p=−0.871±0.094 |
| A+ | 1.659 | 3.234 | 14.0% | α=0.331（放开 α 提 MAE 但过配恶化） |
| R | 2.025 | 3.356 | 9.8% | β→0.2（网格下限，弱） |
| SVR | 1.668 | 3.156 | 12.4% | 黑盒相对 A 仅 −0.18 MAE |
| L | — | — | — | **γ 不可辨识**（冻结协议下 L 无方差） |

残差（A 模型）：按类型 |e| C=4.29 > B=3.88 > A=3.09；按城市 Amsterdam=5.00 >
其余 ~3.1（阿姆斯特丹留出退化，与 P1b 已知结论一致）。

## Phase 9 — 物理一致性审计（解析部分，已写入）

令 x = q_p/W。

**Model A** q̂ = cWx^p（p<0）：
- ∂q̂/∂W = c·x^p·(1−p) > 0 ✓ 恒正；∂q̂/∂q_p = c·p·x^(p−1) < 0 ✓ 恒负。
- q_p→0：x→0 ⇒ x^p→∞ **发散**（必须 Q_low(W) 封顶，final 模型已含）。
- x→x_crit：容量护栏归零 ✓；W<W_min 硬地板 ✓；宽端 q_max=20 ✓。
- 结论：护栏是承重结构，裸公式只在内部域有效。

**Model A+** q̂ = cW^α x^p：
- ∂q̂/∂W 的符号 = sign(α−p)：干跑 α̂=0.331、p̂=−0.789 ⇒ 正 ✓；
  ∂q̂/∂q_p 的符号 = sign(p) ✓。**风险**：若未来估计出 α<p，符号翻转——
  必须作为约束检查（α̂−p̂>0 且 p̂<0），不满足时拒绝该拟合。
- α̂≈0.33 远低于 1 提示宽度效应被 x 共线吸收——正是 decoupled 实验要澄清的。

**Model L**：∂q̂/∂L = q̂·γ/L，符号取决于 γ；γ 在冻结协议下不可辨识（L 无方差）。

**Model R** q̂ = C(W)·[1−(x/x_c)^β]+（β>0，C'(W)>0）：
- ∂q̂/∂x < 0 ✓；∂q̂/∂W > 0 ✓；x→0 时饱和于 C(W)（**无发散**，边界行为优于 A）；
  x→x_c 连续归零 ✓。
- 物理上最规整，但依赖外生 C(W)/x_c 标定，且干跑中 β 打网格下限（拟合弱）。

**边界条件表**（in-domain / extrapolation / out-of-domain 区分）：
- q_p→0：A 发散（护栏封顶）/ R 饱和 → in-domain 需护栏，extrapolation 不声明。
- x→x_crit 邻域：当前主设计**无数据**（33–41.7 空白）→ 容量边界行为属
  extrapolation，论文须标注。
- W→W_min、最大观测宽度（6.92 m）、最大 q_p（144）与 qp>60：超出 final 模型
  标定域（W≤3.0、q_p≤60）→ out-of-domain，按护栏保守处理并单独报告。

## Phase 7 预告 — 合成可辨识性预测（synthetic_D2_preview.py，400 次噪声试验）

在真实扫描完成前，用与主实验相同的生成模型（c=27.166、p=−0.933、σ=1.5、离散化+
截尾）预测 decoupled 实验对 p 可辨识性的增益：

| 数据集 | p̂（真值 −0.933） | std | 95% CI 宽 | LOCO 7 折 p 的折间 std | 折间 range |
|---|---|---|---|---|---|
| D1 = 280 | −0.968 | 0.050 | 0.198 | **0.054** | 0.168 |
| D2 = 280+120 | −0.972 | 0.044 | 0.173（−13%） | **0.014** | 0.047 |

**预测结论**：decoupled 实验的主要收益不是整体 CI 缩窄（仅 ~13%），而是
**跨城市折间稳定性提升 ~3.9×**（std 0.054→0.014）——因为 {18,24,30} 给每城
提供了共同 x 锚点，各城 fold 不再被自身语境聚类偏置。这正是 Q2 的预期答案：
p 的"城市间一致性"将由补充实验确立。x 的 log 覆盖范围不变（0.97 个数量级），
改善的是内部密度与折间一致性。

## Q1–Q6 回答（草案，基于设计表 + 归档 P1b + 合成预测；最终数字待真实数据）

**Q1 原始 280-combo 是否仍然有效？**
- 校准/参考价值：有效——280 个真实几何真值点用于标定护栏（C(W)/Q_low/W_min 邻域）与
  作为 D1 基线数据集。
- 连续律辨识价值：受限——x 只取 8 个聚类值（76% 在 {5,12}），无法单独支撑
  "连续幂律"声明；连续性的证据责任转移给 D2（+decoupled 后）。

**Q2 decoupled 对 p 的改善？**
- 合成预测：整体 CI 宽 −13%，LOCO 折间 std 0.054→0.014（−74%）。
- 待真实数据：identifiability_comparison.csv 给出实测对比。

**Q3 固定 W^1 是否有数据支持？**
- 干跑（P1b）：α̂=0.331（CI 待全量），放开 α 使 MAE 1.849→1.659 但过配率
  11.2%→14.0%（危险侧恶化）；α<1 疑为 x 共线伪影。
- 待真实数据：D2 上重估 α；若 α̂ 的 CI 含 1 或 LOCO 无实质改善 → 保留 W^1。

**Q4 长度 L 是否有独立预测价值？**
- 冻结协议下不可辨识（L 全部 50 m、仿真器长度不敏感）——结论不是"γ=0"而是
  "γ 不可测"；要检验长度效应需协议修订（测速区随长度缩放），超出本实验范围。
- 论文表述：主公式不含 L；长度效应列为 future work / 已知限制。

**Q5 最终推荐公式？**
- 方向（待定稿）：若 α̂ CI 含 1 且 A 与 A+ 的 LOCO 差小 → 选 A（两参数），
  理由句（任务规定模板）写入；护栏栈 = W_min/x_crit/C(W)/Q_low/q_max + floor；
  适用域 = 标定域（直线~轻弯、W≤标定域、qp≤域上限），超宽/高流按 out-of-domain 处理。

**Q6 能/不能声称什么？**
- 可以：simulation-derived quota relationship；real-world sidewalk geometries 上的
  cross-city generalization（LOCO + Seattle/Taoyuan 冻结外测）；interpretable
  two-parameter quota law with guardrails。
- 不能：real-world robot capacity ground truth（仿真参考值，非实测容量）；
  universal law（7 城样本）；safety guarantee beyond simulation conditions。

## 执行事故记录（2026-09-04）

- **现象**：主扫描 Phase A 在 qp=75 高流基线（TPE W=2.99 / TAO W=5.0 商业档，
  双向 2250 人/小时）上陷入 JuPedSim 死循环——12 个 SUMO 子进程各空转 ~17.5 h
  CPU（~62,000 s/进程）、fcd 无输出，Phase A 约 95% 完成但卡死，无任何 CSV 产出。
- **根因**：simulator.py 的 sumo subprocess.run 无超时；部分高密度场景
  （qp≥75、宽走廊不放行 spawn 上限）触发 JuPedSim 病理行为。
- **修复（执行层，不改实验设计）**：config.py 增加 `SIM.timeout_sec=300`（健康
  场景中位 ~2 s 的 130 倍余量）；超时场景记录为**保守失败**（mean_speed=0、
  density=99、flow_ratio=0、`timed_out=1`）→ 该 combo 按判据自然归零，绝不误放行。
- **对协议的影响**：cells/seeds/判据/扫描逻辑均未变；仅增加进程级时间上限与
  失败语义。受影响的 combo 将在结果表中以 `timed_out` 列明示。
- 主扫描已重新启动（Phase A 从头重跑，~30–40 min），看门狗在岗。

## 待完成

1. 主扫描完成 → `consolidate_reference.py --kind main` 生成 main_280_reference_table.csv
   （含 mean 与 per-seed ≥29/30 双口径 qr*、pass_frac_at_star/next）。
2. 跑 p1_decoupled.py（120 combo）→ decoupled_120_reference_table.csv。
3. `refine_boundary.py --plan`（识别边界在档间的 combo）→ `--run`（补扫中间档）
   → refined_quota_reference_table.csv（含 before/after 变化）。
4. full_reference_dataset.csv（280+120+细化合并）。
5. fit_models.py 正式运行（D1=280 vs D2=280+120 可辨识性对比、LOCO、残差、
   公式选择表、物理审计）→ 其余规定文件。
6. 完成本报告 Phase 6–10 与 Q1–Q6 的最终回答。

## 管线脚本状态（全部已实现并干跑验证）

| 脚本 | 用途 | 干跑验证 |
|---|---|---|
| consolidate_reference.py | 主/补充扫描 → 参考表（双口径 qr*、pass 分数） | ✅ 归档 P1b：200 combo，70 个 mean vs per-seed 分歧（与审计一致）；tag 格式已对齐驱动（qp 用 %g） |
| refine_boundary.py | Phase 4 边界细化：--plan 识别 borderline、--run 补扫 | ✅ 归档 P1b：39 combo / 1,830 场景计划 |
| fit_models.py | Phase 5–10 全管线 | ✅ 全部 6 个 CSV/JSON 输出齐备 |
| p1_decoupled.py | Phase 3 补充扫描驱动 | ✅ 3-combo 烟测通过（含 --limit、空 sweep 修复） |
| merge_datasets.py | 合并 280+120+细化 → full_reference_dataset.csv | 待数据 |
| run_all_analysis.py | 一键分析链（consolidate→refine→merge→fit D1/D2） | 待数据 |
