# 网络素材与知识补全记录

日期：2026-09-20。代码目录：`F:/workspace/posterpilot`。

## 实际补齐了什么

| 缺口 | 本次补充 | 用户在哪里看到 |
| --- | --- | --- |
| 案例偏历史装饰风格 | 从 6 张新候选中选入 4 张科学招募、阅读、社区节庆参考；总计 15 张 | 创建页面展开“选择参考海报”，可搜索、查看来源并按维度选用 |
| 批准设计规则较少 | 新增 8 条有来源的规则，共 14 条批准卡、5 条待验证卡 | 真实 Ollama/Chroma 检索和 Agent 知识引用 |
| 演示只重复一幅几何图 | 3 个公共领域背景，科学讲座、文化活动、摄影社招新各 1 组 | 首页前后对照；数据工作台的每轮案例与审核记录 |
| 首页/预览只使用旧单张素材 | 换成真实渲染的星云样例，补充来源、许可和生成边界 | 首页、空白输出预览 |
| 创建表单只有一个过时样例 | 三种活动的一键填入，保留艺术字选择 | 创建表单，不点击生成不会提交 |

保留测试中的固定几何素材，它承担回归测试职责，不再是用户展示的唯一素材。没有新增未授权字体、转载整本 PDF 或把外部图片伪装成模型作品。

## 可直接查看

启动后访问 `http://127.0.0.1:5194/`，首页向下查看三组排版对照；数据工作台为 `http://127.0.0.1:5194/#datahub`。

这里是单独的数据目录 `data/reviewed-showcase`，不是正式任务数据库。无需付费模型调用：

```powershell
# 项目根目录执行；先安装项目依赖。两个终端分别启动 API 和 Web。
./scripts/start_showcase.ps1 -Mode Api -PythonExe ./.venv/Scripts/python.exe
./scripts/start_showcase.ps1 -Mode Web
```

本机验证实际使用的 Python 是 `F:/workspace/GazePoster/.venv/Scripts/python.exe`，可代入 `-PythonExe`。普通启动仍走原有模型 Provider，不会偷偷换成这些图片。

第一次在新机器上准备数据：`-Mode Seed`。重建需显式执行 `python scripts/prepare_showcase.py --regenerate`；保留旧任务便于追溯。审核发布执行 `python scripts/prepare_showcase.py --publish-reviewed`，要求 `data/showcase/reviewed-results.json` 中的图片哈希与实际输出一致，不能把旧审核套到新图上。

## 三组实际结果

| 场景 | 实际动作 | 复核结果 | 允许作为正向经验 |
| --- | --- | --- | --- |
| 看见星云 | 时间地点字号调整为 42，实际重新渲染 | 当前目标检查通过，文字与主视觉完整 | 是，仅在显式包含离线案例时可检索 |
| 花间一课 | 同样放大时间地点 | 副标题与活动信息局部背景对比未通过 | 否，保持 candidate，展示不足 |
| 山河入镜 | 同样放大时间地点 | 亮云层上的副标题局部对比未通过 | 否，保持 candidate，展示不足 |

三组综合分对比均为 unchanged，不编造分数提升。规则检查是实际执行；视觉大模型和 DeepGaze 在此演示中未调用。文字背景抽样不能证明真实阅读、注意力或 WCAG 合规。没有采集任何真实用户反馈，全部保持 unknown/not_collected，点击结束任务不等于满意。

实际渲染元数据确认标题分别使用 ZCOOL QingKe HuangYou Regular、Ma Shan Zheng Regular、Long Cang Regular，三组标题都未溢出，并非只在表单里显示了字体名称。对应恢复测试也验证实际字体结果。

`apps/web/public/showcase/index.json` 含实际工具轨迹、检查结果、图像哈希和来源；前端 manifest 由同一脚本生成。`data/showcase/scenarios.json` 是唯一人工维护的场景列表。每组海报初版与调整版都经过逐张视觉检查。

数据工作台中可能看到开发失败重试保留的早期候选记录；它们没有发布，不进入普通经验检索。正式检索默认排除整个 offline_demo 类型。界面的“检索验证”中，勾选包含离线案例后，查询“科学讲座时间地点字号太小”返回 1 条；不勾选返回 0 条，浏览器实测一致。

## 来源与取舍

新增 Wiki 来源页：

- [NASA Explorers Wanted](https://commons.wikimedia.org/w/index.php?curid=128994779)：冷暖反差、人物行动方向与底部标题。
- [NASA Surveyors Wanted](https://commons.wikimedia.org/w/index.php?curid=128994776)：大面积暖色、人物比例与信息分区。
- [Back to books](https://commons.wikimedia.org/w/index.php?curid=31824857)：蓝绿双色、阅读主题与文字层级。
- [Wikimania 2022 社区节庆](https://commons.wikimedia.org/w/index.php?curid=122316577)：Katie Crampton (WMUK)，CC BY-SA 4.0；署名与许可链接随数据进入 UI，原图内容不改动，横版不拉伸成竖版。

前 3 张来源页标注公共领域；另 2 张新候选因信息过密和只是海报现场照片被排除。背景素材单独见 `data/media/README.md`，不把参考案例原图直接当作新的活动事实。

新规则使用实际读取的 [NN/g 视觉设计原则](https://www.nngroup.com/articles/principles-visual-design/)、[视觉层级](https://www.nngroup.com/articles/visual-hierarchy-ux-definition/)、[W3C G18](https://www.w3.org/WAI/WCAG22/Techniques/general/G18)、[最小对比度](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html) 与 [文字间距](https://www.w3.org/WAI/WCAG22/Understanding/text-spacing.html)。只保存简短证据片段与响应哈希，不整篇转载。静态 PNG 不被宣称满足可调整文字间距的网页要求。

## 修复与验证

- 非空检索结果包含 `HttpUrl`，此前会在 LangGraph SQLite checkpoint 序列化时失败。现在仅把 URL 的保存表示改为字符串，恢复时仍由 Pydantic 验证为 HttpUrl；没有启用 pickle 兜底。已增加往返与实际恢复测试。
- 统一了旧对比度、层级、邻近原则卡片的中文表达；不更改测试预期 ID、不降低召回门槛。真实向量检索曾漏掉时间地点分组规则，修正后通过。
- 19 张卡片（14 approved）、5 个来源登记、16 条固定检索用例通过 Schema 检查；未未经审查提升原有 5 条候选状态。
- 本地 Ollama `bge-m3:latest` + Chroma：Recall@3=1.000，MRR=0.802。离线词法回归：1.000 / 1.000。仅代表这 16 条开发回归用例，不是独立评测集或线上准确率。
- 后端完整测试：247 passed；前端：46 passed；生产构建通过。
- 浏览器检查：首页图片、三场景切换、初版/调整版说明、深浅色、390px 窄屏、表单填入、15 个案例列表及新 CC BY-SA 案例、数据工作台真实审核状态和检索隔离。
- 图片逐项 SHA256、许可、来源字段与公开 manifest 一致性通过测试；被拒素材不进入目录。未调用付费模型，未上传 GitHub。

## 页面设计范围

按前端设计技能做保留式调整：现有 React/CSS、蓝色强调与深浅主题不变，保留导航和流程。设计尺度采用低变化/无额外动画/适中密度（4/1/4）；只新增切换式图像对照，不把业务工作台改成营销页。使用已核验的真实来源图片，而非额外生图，符合本次“找网络素材”的要求。

浏览器验证属于功能与视觉验收，没有运行 Lighthouse 性能基准，不声称生产性能或真实模型效果达标。
