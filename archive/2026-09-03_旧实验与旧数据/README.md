# 归档：旧实验与旧数据（2026-09-03 之前）

本目录归档 **2026-09 大规模重构之前** 的实验、计划与数据。

> **不要引用这些结果。** 一切方法与结果以仓库根目录的
> `final_freeze/`（冻结方法）与 `data/final/`（D2 数据）为准。

## 内容

| 子目录 / 文件 | 说明 |
|---|---|
| `experiment/` | 早期合成直线走廊校准实验（scripts + outputs + figures + reports） |
| `experiment_sumo/` | 早期 SUMO 实验（含 bend 位置 / 弯道扫描） |
| `sumo_jupedsim/` | P1b 多城市（Amsterdam / London / Singapore / Tokyo）4 城细胞数据与脚本 |
| `实验进度与下一步计划_2026-08-22.md` | 旧版进度与计划 |
| `配送机器人_实验计划书_SUMO_JuPedSim_新加坡.md` | 旧版实验计划书 |
| `配送机器人_研究方向_Quota算法更新版.md` | 旧版研究方向 |
| `README.zh-CN.md` | 旧版中文 README |

## 归档原因

- 实验由「合成直线走廊」重构为「7 城真实人行道重标定」
  （280 主实验 + 120 解耦 = 400 条 D2 组合）。
- 参考配额判定规则由旧版修正为 **每种子 ≥ 29/30**。
- 边界精化（refinement）与解耦实验（decoupled）为重构后新增。

历史仍可通过 git 历史（commit `c5bf01d` 及更早）查看；本目录只是把旧文件显式归档以便浏览。
