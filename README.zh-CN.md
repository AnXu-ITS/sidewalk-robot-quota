# 行人服务与配送机器人准入

本研究讨论局部人行道的机器人进入流率，而不是用运行许可或机器人总量代替
交通管理。准入流程先检查几何适用性和行人基线服务，再由宽度与行人需求估计
候选流率，通过保守margin调整准入量，并在对应配置和流率下直接检验服务。

[最新论文](paper_CICTP2027/manuscript/ascexmpl-new.pdf) ·
[CICTP2027研究数据](paper_CICTP2027/README.md) ·
[复现说明](paper_CICTP2027/REPRODUCE.md) ·
[D2与CICTP参数沿革](research_versions/README.md)

在164个评估场景中，无margin时136个场景获得正推荐，其中18个服务测试失败；
0.80 margin时98个正推荐均通过。被0.80设置拒绝的38个机会中，32个在其无margin
流率下实际通过，说明保守准入也会损失可用的机器人通行机会。

独立种子检验保留13/13个M0决策和7/15个M1决策。样本按稳健、边界和失败情形
预先分层选取，不能将比例解释为总体可靠率。香港实验分开记录13个原入口配置
与5个入口修复配置。

```bash
python -m pip install -r paper_CICTP2027/requirements.txt
python -B paper_CICTP2027/scripts/reproduce.py
python -B paper_CICTP2027/scripts/build_assets.py
```

数值复现不需要重新仿真。原始D2数据、旧稿和既有公开文件保持保存；当前研究
版本使用独立目录及冻结参数。公开包包含真实逐种子指标和详细诊断，13.6GB的
新增原始轨迹/XML仍留在本地，不上传开发者路径、凭据或原始受限GIS资料。
