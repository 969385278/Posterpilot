# PosterPilot + PosterHub 操作与代码指南

## 两个项目分别负责什么

PosterPilot 负责活动需求、设计知识检索、主视觉生成、确定性中文排版、自动评测与人工决定后的受约束优化。
PosterHub 负责保存每轮证据、整理设计案例、记录明确反馈、人工审核，以及向后续任务提供适用经验。原开发名为 PosterDataHub，内部 `datahub` 模块和接口路径保持不变。

这是一个仓库内两个相连的产品模块：共用 FastAPI 与业务数据库，前端有独立工作台入口。不声称已拆成独立微服务或企业数据中台。

## 一、无付费调用的本机演示

在项目根目录打开 PowerShell。首次安装（已有依赖可跳过）：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e "apps/api[dev]"
npm.cmd --prefix apps/web ci
```

先生成离线演示数据；可重复运行，不删除已有记录：

```powershell
.\scripts\start_datahub_demo.ps1 -Mode Seed
```

随后在两个终端分别运行：

```powershell
.\scripts\start_datahub_demo.ps1 -Mode Api
```

```powershell
.\scripts\start_datahub_demo.ps1 -Mode Web
```

打开 <http://127.0.0.1:5193/#datahub>。API 文档为 <http://127.0.0.1:8793/docs>。
终端按 Ctrl+C 停止对应服务。端口被占用时不要强行结束无关进程，可通过 `-ApiPort` 和 `-WebPort` 换端口；两个终端必须使用相同的 API 端口参数。
脚本优先使用仓库 `.venv`，也可用 `-PythonExe '你的环境/python.exe'` 指定已安装依赖的 Python。

演示数据保存在 `data/datahub-demo/`，与正常任务隔离。模型输出和图片由固定测试依赖产生，没有付费模型调用。脚本验证真实的 API、LangGraph、渲染、审核与存储逻辑，但不能证明模型自主学习或审美提升。

正常使用仍按 README 的配置和启动方式运行，访问正常前端的 `#datahub`。新版任务会自动回流；正常检索默认排除离线案例。

## 二、建议按这个顺序体验

1. 在案例库选择一个“第 1 轮”的案例。左侧对照初版与本轮图片，查看原始意见、工具参数、执行结果与评测条件。
2. 查看反馈。没有明确收集就保持“未明确评价”，不能因为点击结束或分数较高便填“用户接受”。离线样例反馈会标为演示来源。
3. 整理问题、复用建议、适用条件、限制与授权依据。填写的是可迁移经验，例如“先检查标题与背景的对比度”，而不是固定复用旧活动的时间、地点或字号。
4. 保存后回到待审核状态。检查自动列出的门禁问题，再填写审核说明并批准、驳回或撤回。修改已发布内容也必须重审。
5. 在“检索验证”中选择文化活动，输入“标题不醒目”；体验离线样例时勾选“包含离线演示案例”。对照关闭与开启历史经验的输入差异。
6. 返回 PosterPilot 创建新任务，开启“历史案例”选项。Agent 控制台会列出参考来源和版本；这表示资料已提供，不表示模型一定采用或动作已经有效。
7. 撤回已发布案例，再次检索应不再返回它。之前任务保存的历史参考仍可查看。

从来源任务进入工作台时会默认只显示该任务，检索试验也排除该任务，防止把自身结果当成独立经验。需要做跨任务演示时从独立 `#datahub` 入口进入。
自动收集失败不应改变已经生成的海报状态；从任务工作台进入数据工作台后，可点击“重新收集此任务”重试。

## 三、文件职责与功能对应

以下路径均相对于项目根目录。

| 文件 | 负责的功能 |
| --- | --- |
| `apps/api/app/agent/experience_evidence.py` | 每轮结束保存需求、布局、动作、评测与参考快照 |
| `apps/api/app/agent/nodes/evaluate.py` | 评测后写入本轮证据；不是每个工具动作都生成版本 |
| `apps/api/app/services/run_service.py` | 任务状态完成后自动收集，收集失败记录待重试事件 |
| `apps/api/app/schemas/datahub.py` | 案例、反馈、审核版本和检索参数的结构与校验 |
| `apps/api/app/persistence/models.py` | 业务数据库中的案例表，任务与轮次唯一约束 |
| `apps/api/app/persistence/datahub_repository.py` | 幂等插入、读取、按预期版本更新，防止覆盖并发修改 |
| `apps/api/app/services/datahub_service.py` | 图片副本与校验、整理、质量门禁、审核与经验检索 |
| `apps/api/app/api/routes/datahub.py` | 案例、反馈、质量、审核、图片、统计和检索 API |
| `apps/api/app/agent/experience_context.py` | 根据当前需求检索，处理关闭开关与检索失败回退 |
| `apps/api/app/agent/nodes/plan_design.py` | 初版规划前获取案例参考 |
| `apps/api/app/agent/nodes/react_decide.py` | 每次优化决策前重新获取当前可用案例 |
| `apps/api/app/agent/prompts/design.py`、`prompts/react.py` | 将历史内容作为参考数据，不得覆盖当前要求或权限 |
| `apps/web/src/api/datahub.ts` | 工作台调用 API 的类型与请求函数 |
| `apps/web/src/pages/DataHubPage.tsx` | 案例、反馈、审核、前后对照与检索试验界面 |
| `apps/web/src/styles/datahub.css` | 工作台排版、图片尺寸、主题及窄屏样式 |
| `apps/web/src/features/brief/BriefForm.tsx` | 新任务的案例参考开关 |
| `apps/web/src/features/agent/AgentConsole.tsx` | 显示历史参考候选和版本，不冒充采纳证明 |
| `apps/api/app/datahub_demo.py` | 隔离的固定模型决策与演示应用工厂 |
| `scripts/verify_datahub.py` | 跑通真实业务链路，生成机器可读验证报告 |
| `scripts/start_datahub_demo.ps1` | 准备离线数据、启动 API 或 Web |
| `apps/api/tests/services/test_datahub.py` | 审核门禁、版本冲突、撤回、证据和引用边界测试 |
| `apps/api/tests/services/test_datahub_integration.py` | 整体数据闭环、回流故障不影响海报与重试恢复 |
| `apps/web/src/pages/DataHubPage.test.tsx` | 表单、错误、审核、版本展示与检索交互测试 |

## 四、数据与经验边界

- 原始证据按任务与轮次唯一保存，内容改变后不能悄悄覆盖。图片复制到内容校验值命名的目录，源任务文件被清理后仍能追溯。
- 整理版本独立于海报轮次：修改建议或反馈会增加整理版本并取消旧审核；审核记录保留当时内容快照。
- 只有已批准、质量检查通过、授权明确的案例进入候选。明确拒绝的反馈保留用于分析，不作为正向经验。
- 当前检索是小规模文本二元片段匹配，过滤海报类型、同一任务和演示来源，再按相关性取最多三条并去重。它不是语义向量检索或图像相似检索；原有设计知识 RAG 仍独立工作。
- 提供问题、建议、适用条件、限制、画布与来源，不直接传递旧活动事实和原始工具参数。人工整理内容仍需要检查，提示词边界并不等于解决了所有提示注入风险。
- 审核允许参考、用户接受、可比较的分数变化是三种独立信息。缺少评测信号时不补造数值，条件不匹配时保留 `not_comparable`。
- 这是本机单用户工具，没有登录、租户隔离、企业审批身份、可靠任务队列、自动训练、自动 Skill 沉淀或用户画像。
- 当前任务状态依靠 LangGraph checkpoint；跨任务经验通过外部检索提供。没有通用 token 预算或模型摘要压缩机制。

## 五、复现验证与结果解读

```powershell
$env:PYTHONPATH = "$PWD/apps/api"
.\.venv\Scripts\python.exe -m pytest apps/api/tests -q
npm.cmd --prefix apps/web run test
npm.cmd --prefix apps/web run build
.\scripts\start_datahub_demo.ps1 -Mode Seed
```

报告位于 `data/datahub-demo/verification.json`，包含三次任务与案例 ID，可在工作台定位来源。
它验证开启经验时有参考、关闭时无参考、当前任务排除、撤回生效、重新打开数据库仍可读取等功能，并保留四个固定查询探针。
四个探针通过只说明这些测试输入符合预期，不能当作行业检索准确率。离线对照也不能作为真实生成质量的 A/B 实验。

实际测试结果和浏览器验收状态见 [实施与验收](posterdatahub-implementation.md)。
