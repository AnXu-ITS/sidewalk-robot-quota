# train_test_mapdata — 统一训练/测试地图数据（2026-09-03）

7 城统一口径的人行道几何+宽度数据。**训练**：NYC / Amsterdam / Melbourne / Taipei / New Taipei；
**测试**：Seattle / Taoyuan。全部 WGS84 经纬度（显式声明 CRS84），宽度统一为米（`width_m`）。

## 文件

| 文件 | 城市 | 用途 | 要素数 | 宽度中位(m) | 几何 |
|---|---|---|---|---|---|
| train_nyc.geojson | 纽约 NYC | train | 464,956 | 2.87 | LineString |
| train_amsterdam.geojson | 阿姆斯特丹 | train | 217,785 | 2.33 | LineString |
| train_melbourne.geojson | 墨尔本（两层合并） | train | 25,453 | 1.97 | Polygon/MultiPolygon |
| train_taipei.geojson | 台北 | train | 18,060 | 1.82 | MultiPolygon |
| train_newtaipei.geojson | 新北 | train | 13,984 | 2.01 | MultiPolygon |
| test_seattle.geojson | 西雅图 | test | 46,085 | 1.52 | MultiLineString |
| test_taoyuan.geojson | 桃园 | test | 10,198 | 2.52 | MultiPolygon |
| train_all.geojson | 训练集合并（740,238 要素） | — | — | — | 混合 |
| test_all.geojson | 测试集合并（56,283 要素） | — | — | — | 混合 |
| manifest.csv | 每城统计卡 | — | — | — | — |

## 统一 schema（每个要素新增字段）

| 字段 | 含义 |
|---|---|
| `city` | 城市 key（nyc / amsterdam / melbourne / taipei / newtaipei / seattle / taoyuan） |
| `city_cn` | 中文名（纽约/阿姆斯特丹/墨尔本/台北/新北/西雅图/桃园） |
| `split` | train / test |
| `width_m` | 人行道宽度（米，主训练目标） |
| `net_width_m` | 净宽（仅台湾 NLMA 有值：SWW_WTH；其余城市为 null） |
| `filler_width_m` | 绿化带宽度（仅西雅图，来自 FILLERWID×0.0254） |
| `width_source` | 宽度值性质：`measured_official`（官方实测：西雅图、台湾3城）/ `derived_bgt`（阿姆斯特丹，官方从 BGT 面推导）/ `derived_area_perimeter`（墨尔本，2×面积/周长推导）/ `derived_planimetric`（NYC，社区项目从航测面推导） |
| `width_qc` | 0=正常；1=异常值（阈值见下）；2=零宽/未硬化路面（西雅图 UIMPRV）；3=缺失 |
| `suitable` | 1=机器人适用；0=不适用（阿姆斯特丹楼梯 `bgt_voetpad op trap`） |
| `layer` | 仅墨尔本：`footpaths`（人行道面图层）/ `roadseg_footway`（道路分段 Footway 类） |

原始字段全部保留（NYC 的 `width` 英尺、西雅图的 58 个 SDOT 属性、NLMA 的 10 个字段、阿姆斯特丹的 19 个网络字段、墨尔本的原始属性等）。

## 处理决策（可复现：build_train_test_mapdata.py）

1. **单位换算**：NYC `width` 英尺×0.3048；西雅图 `SW_WIDTH`/`FILLERWID` 英寸×0.0254；阿姆斯特丹/台湾/墨尔本原值即米。
2. **墨尔本宽度推导**：`width_m = 2×面积/周长`，周长由几何 haversine 逐环计算（与官方 shape_star/shape_stle 属性交叉验证一致，误差 0）。footpaths 只取 `asset_type IN (Road Footway, Road Fotway)`；road_segments 只取 `type='Footway'`（该文件 `width` 字段不可用：Footway 全 null、其余为路缘石断面字符串）。
3. **阿姆斯特丹筛选**：只保留 `wegklasse ∈ {bgt_voetpad, bgt_voetpad op trap, bgt_voetgangersgebied, bgt_inrit}` 且 `gewogenGemiddeldeBreedte>0` 的边（其余 ~35 万 OSM 类边无宽度，剔除）；楼梯 `op trap` 标 `suitable=0`。
4. **西雅图状态过滤**：`CURRENT_STATUS IN (INSVC, PLNRECON)`（剔除 REMOVED 131 / PLANNED 30 / OUTSVC 8 / UNDERCONS 7 / TEMPOUTSVC 1 / 空 5，共 182 条）；95 条空几何丢弃；`SW_WIDTH=0` 的 11,129 条（未硬化 UIMPRV）保留但标 `width_qc=2`（表示"此处无人行道"语义，训练时按需处理）。
5. **异常值阈值**（只标记不删除，`width_qc=1`）：NYC >60 ft 或 <0.5 ft（1,355 条）；西雅图 >240 in（48 条）；阿姆斯特丹 >12 m 或 <0.5 m（10,035 条，其中 <0.5 m 为极小值）；墨尔本 <0.2 m 或 >10 m（612 条）；台湾 >8 m（台北 332 / 新北 209 / 桃园 63）。
6. **台湾拆分**：从 NLMA 全国人行道 2024-12 第 1 部分按 `COUNTY_NA` 拆分（台北市/新北市/桃園市），`width_m=SW_WTH`、`net_width_m=SWW_WTH`、长度保留为原始 `SW_LENG` 字段。**硬剔除规则**：`SW_WTH > 60 m` 直接丢弃（已剔除新北 3 条录入错误要素，含 1 条 500 m）。

## 已知数据质量问题（使用时注意）

1. **台湾已硬剔除 SW_WTH>60 m 的录入错误要素**（新北 3 条，含原 500 m 一条）；剩余 qc=1 的 >8 m 宽铺装/广场类属正常值域外但可能真实，按需处理。
2. **台湾三城的净宽与宽度差距显著**：台北中位 SW_WTH 1.82 m vs SWW_WTH 1.36 m（净宽=扣除街道家具后的可通行宽度，机器人建议优先用 `net_width_m`，但需在论文中说明口径选择）。
3. **墨尔本为推导宽度**（面宽 2A/P），且只覆盖 City of Melbourne 市辖区（约 8×8 km），非大墨尔本。
4. **阿姆斯特丹为步行+自行车综合网络的 BGT 子集**，`bgt_inrit`（车道入口）11,035 条宽度语义为入口宽度，若只研究人行道可用 `wegklasse='bgt_voetpad'` 再筛。
5. **西雅图 MultiLineString**：一条要素可能含多段，做 50 m cell 切分时需先拆分。
6. **桃园测试集与台北/新北训练集同源同国**（都是台湾 NLMA），跨域独立性弱于西雅图测试集；论文中建议把西雅图定位为"跨数据源/跨国"主测试，桃园定位为"省内跨城市"次测试。

## 管线

`build_train_test_mapdata.py`（本目录）从 `..\5newcities\` 与仓库内 NLMA 源文件流式生成以上全部产物，可重跑。
