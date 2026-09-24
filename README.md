# PosterPilot

可控的海报生成与评测优化 Agent。基于 **React + FastAPI + LangGraph**，将设计知识检索、主视觉生成、中文排版、多信号评测和人工反馈连接起来。

用户填写活动信息后，系统生成并评测初版海报；用户可以结束任务，也可以提出修改目标。Agent 根据反馈选择工具，完成一轮调整和复评，再暂停等待用户决定。

## 核心能力

- **受约束 ReAct**：LLM 选择检索、文字、布局和背景调整工具，读取 Observation 后继续决策；工具白名单、参数 Schema 和调用预算限制执行范围。
- **原生 HITL**：使用 LangGraph `interrupt`、`Command(resume=...)` 和 SQLite Checkpointer，在同一任务状态中暂停与恢复。
- **RAG 知识增强**：LangChain 组件、Ollama Embeddings 和 Chroma 支持过滤、向量召回、词法混合排序及来源引用。
- **生成与排版分离**：图像模型生成无文字主视觉，Pillow 根据结构化设计确定性绘制中文，避免生图过程改变活动事实。
- **评测驱动优化**：结合版式规则、视觉模型和可选的 DeepGaze 注意力预测；提供注意力辅助布局候选、优化目标检查和轮次对比。
- **案例与字体选择**：有出处的海报案例 Wiki、设计特点选择和 6 款 OFL 中文标题字体。案例字体仅作风格近似，不是恢复原字体。
- **运行可追溯**：工作台展示事件、知识引用、工具轨迹、评测结果及每轮正式海报；SSE 展示事件，轮询同步业务状态。
- **PosterHub 数据回流**：收集每轮证据，整理案例、明确反馈与使用授权，经人工审核后供新任务参考；支持版本记录、撤回与修改重审。
- **海报设计问答助手**：根据问题选择知识检索、审核案例、当前评测、图片分析或轮次历史工具；显示依据与工具记录，用户确认建议后才进入原有优化流程。[使用与实现说明](docs/design-assistant.md)
- **用户记忆与画像**：保留原始消息、记忆事件及场景化画像。明确确认后才更新长期偏好，支持修订、撤销和原话溯源；创建任务可选择使用画像，当前需求优先。
- **一句话需求入口**：默认由 DeepSeek 分类并解析生成、修改或问答需求，修改前确认目标与锁定；可切换为规则加模型回退。尚未接入 Jev。
- **审核决策卡**：从通过目标验收的已审核案例整理工具选择经验，按场景和问题检索后提供给 ReAct；来源撤回或版本变化即停止复用。

### 配套项目：PosterHub

PosterPilot 负责生成与优化，PosterHub 负责案例库、反馈记录与质量管理。二者共用后端和数据库，数据工作台入口为 `#datahub`，并非两个独立部署的微服务。代码中的 `datahub` 模块名及接口路径保持不变。

PosterHub 的主要实现：

- **轮次记录**：保存修改意见、工具动作、前后图和评测结果；按任务与轮次幂等采集，校验图片内容哈希。
- **审核与反馈**：分别记录用户反馈和自动评测结果，支持案例编辑、审核发布、驳回、撤回及修改后重审。
- **版本一致性**：用版本号检查编辑与审核冲突，保留历史快照，不覆盖原始轮次证据。
- **经验复用**：只将审核通过、场景匹配的案例提供给 Agent，保留来源版本，排除当前任务和默认关闭的离线样例。

代码入口：[后台页面](apps/web/src/pages/DataHubPage.tsx) · [API](apps/api/app/api/routes/datahub.py) · [业务服务](apps/api/app/services/datahub_service.py) · [持久化](apps/api/app/persistence/datahub_repository.py) · [Agent 经验上下文](apps/api/app/agent/experience_context.py)

新任务可选择使用已审核经验：只检索适用案例，排除当前任务，保留来源与版本。不把结束任务当作用户接受，不把分数变化当作真实效果提升，也不自动训练模型。

[两项目启动与操作指南](docs/posterdatahub-guide.md) · [实施验收记录](docs/posterdatahub-implementation.md)

[简历功能补全与当前验收状态](docs/resume-implementation-audit.md)：记录新增实现、验证结果和未完成项。
用户记忆、决策卡可在 PosterHub 对应页签管理。“工具与能力”页提供代码注册的工具目录、
实际回归报告、审查发布/撤回，以及失败证据归集和人工分类。两个新增文字工具默认不启用，
通过当前代码的回归和审查后才进入 ReAct 可用目录；代码变化会使发布失效。
“视觉素材”页支持图片上传、像素去重/近似提示、来源与使用权、主色提取、视觉模型候选、
版本审核、撤回和语义索引。只有已审核资料进入生成与问答；模型不可用或索引过期时明确退回
词法检索。语义向量来自素材描述文本，不是图片向量；独立效果实验仍在建设中。
功能测试结果不等于简历中的效果百分比。

[可复现实验说明](docs/reproducible-evaluations.md)：提供同条件纯向量/混合排序对照、意图路由
开发集评测和记忆更新规则对照，保存输入、代码、模型版本与逐条结果。现有数据不是独立评测集。

素材检索真实模型检查（需要本地 Ollama 已安装 `bge-m3`）：
`python scripts/verify_visual_asset_retrieval.py`。脚本在 `work/` 下创建独立数据目录，保留输入、
来源、模型摘要和逐条结果；这是三条试查，不是独立标注评测集。

新增 [素材与知识补全说明](docs/content-enrichment-report.md)：15 张有来源的参考海报、14 条审核知识、3 组真实渲染前后对照。首页展示为公共领域背景的固定排版演示，非生图模型输出；未通过可读性检查的样例明确标记，不作为成功经验发布。使用 `scripts/start_showcase.ps1 -Mode Api` 和 `-Mode Web` 启动独立素材演示（默认 8794/5194）。

无需付费 API 的演示：运行 `scripts/start_datahub_demo.ps1 -Mode Seed` 生成固定测试数据，再分别启动 `-Mode Api` 和 `-Mode Web`，访问 `http://127.0.0.1:5193/#datahub`。需先安装项目依赖，详见操作指南。离线图片和决策均为明确标记的测试样例，不证明真实模型质量提升。

### 能力边界

- 这是**固定生成工作流 + 单个受约束 ReAct 循环 + 人工决策**，不是多 Agent 系统。
- 代码约束优化轮上限和工具预算，用户决定是否在上限内继续。工具先修改结构参数，轮末统一渲染和完整复评。
- DeepGaze 预测视觉注意分布，不是真实眼动，也不是审美优劣或实际传播效果的证明。
- 支持可控文字和布局调整，不支持任意主视觉对象的精确局部编辑。
- `BackgroundTasks` 是进程内后台任务，不是生产级可靠队列。SSE 不承诺模型 token 级实时输出。

## 案例展示


### AI 视觉迭代示意：《梦红楼》淡彩人物画版

米色绢纸底、细线人物与赭红淡彩，搭配纵向毛笔行书；以少量枝石和留白衬托主角。迭代重点：适度放大左下角活动信息，调整日期、时间的分行与间距。

| 初版（淡彩人物画） | 迭代优化版（信息排版） |
|---|---|
| <img src="docs/demo/assets/menghonglou-ink-initial.png" alt="梦红楼淡彩人物画初版，AI 风格参考生成示意" width="420"> | <img src="docs/demo/assets/menghonglou-ink-optimized.png" alt="梦红楼淡彩人物画排版迭代版，非 Agent 运行结果" width="420"> |

[迭代说明、参考图来源边界与提示词](docs/demo/menghonglou-ink-iteration.md) · [此前的摄影社书法风格示意](docs/demo/assets/calligraphy-photography-concept.png)

## 代码结构

```text
posterpilot/
├─ apps/
│  ├─ api/
│  │  ├─ app/
│  │  │  ├─ api/routes/   HTTP API：任务、问答、画像、案例、决策卡、工具和素材
│  │  │  ├─ agent/        LangGraph 编排、共享状态、节点、提示与工具执行
│  │  │  ├─ services/     业务规则、意图路由、用户记忆和审核发布
│  │  │  ├─ persistence/  SQLite/SQLAlchemy、仓储与运行所有权
│  │  │  ├─ schemas/      请求、模型输出、状态和工具参数的数据契约
│  │  │  ├─ providers/    DeepSeek、Ark、Ollama 等外部模型适配
│  │  │  ├─ rag/          知识过滤、向量召回、混合排序与来源
│  │  │  ├─ poster/       模板、Pillow 排版、动作校验与事实保护
│  │  │  ├─ evaluation/   可读性、版式、注意力及目标验收
│  │  │  ├─ experiments/  检索、记忆、决策和工具集对照实验支持
│  │  │  └─ core/         配置、项目路径和日志
│  │  └─ tests/           后端单元、契约、API 和回归测试
│  ├─ web/                正式 React + TypeScript 工作台
│  ├─ learn/              独立 Python 本地学习台，无需模型密钥
│  └─ execution-learner/   独立 React/Remotion 代码执行教学网页
├─ services/deepgaze/      可选的注意力预测服务及独立测试
├─ data/
│  ├─ knowledge/          规则卡、来源清单、已选案例与检索开发集
│  ├─ evaluation/         意图、记忆等开发回归样例
│  ├─ templates/          竖版海报布局模板
│  ├─ fonts/              可分发中文字体及许可证
│  ├─ media/              已整理素材及来源
│  └─ showcase/           演示场景与审核结果清单
├─ infra/                 Ollama、Chroma 的 Docker Compose 配置
├─ scripts/               启动、入库、素材准备、评测与统一验证
├─ docs/                  架构、操作指南、实验协议、计划及历史验收
├─ work/                  本地实验快照/原始响应/报告，不上传 Git
├─ output/、outputs/      本地导出文档和预览，不上传 Git
├─ .env.example           可提交的配置模板；真实 .env 仅存本机
└─ package.json           统一启动、测试和构建入口
```

### 正式应用、学习工具与运行数据

正式产品由 `apps/web` + `apps/api` 组成；PosterHub 是其中的数据管理功能，不是独立服务。
`services/deepgaze` 可选。两个学习网页是独立入口，保留不同的教学方式，不参与正式生成流程，
不能把教学回放当作真实模型运行。详见 [Python 学习台](apps/learn/README.md) 与
[代码执行学习器](apps/execution-learner/README.md)。根目录的 `开始学习.cmd` / `停止学习.cmd`
对应前者。

`data/` 同时是默认运行数据根目录：本机还可能出现 `runs/`、`chroma-runtime/`、
`datahub-assets/`、`visual-assets/`、`tool-harness/` 和 SQLite 文件，这些不随仓库发布。
数据库、检查点、索引和发布记录不是缓存垃圾；删除会丢失任务、记忆或审核状态。
不要在服务运行时删除数据库的 WAL/SHM 文件和 `.runtime.lock`。

### 从入口读到执行

- 页面与请求：`apps/web/src/pages/WorkspacePage.tsx`、`apps/web/src/api/client.ts`
- 任务服务：`apps/api/app/api/routes/runs.py`、`apps/api/app/services/run_service.py`
- 编排与恢复：`apps/api/app/agent/graph.py`、`apps/api/app/agent/executor.py`
- 决策与执行：`apps/api/app/agent/nodes/react_decide.py`、`apps/api/app/agent/tools/react_tools.py`
- 知识检索与渲染：`apps/api/app/rag/`、`apps/api/app/poster/`

详见[文件职责与功能映射](docs/framework-and-feature-map.md)和[请求生命周期](docs/request-lifecycle.md)。

### 文档与实验导航

|需要了解什么|入口|
|---|---|
|启动、PosterHub 审核与操作|[操作指南](docs/posterdatahub-guide.md)|
|后端模块及请求链路|[功能映射](docs/framework-and-feature-map.md)、[生命周期](docs/request-lifecycle.md)|
|问答助手与确认修改|[问答助手](docs/design-assistant.md)|
|评测脚本、输入和指标边界|[可复现实验](docs/reproducible-evaluations.md)、[评测协议](docs/interview-evaluation-protocol.md)|
|当前本地实验放在哪里|[实验记录导航](docs/evaluation-evidence-map.md)|
|哪些文件被清理、哪些应保留|[清理记录](docs/repository-cleanup-20260925.md)|
|未来方案|[团队工作台计划](docs/team-workbench-upgrade-plan.md)，不代表已实现|

`docs/*plan*` 是设计计划；`*implementation*`、`*status*` 和验收记录是当时的快照，
不能将其中的待办、目标值或旧统计直接当成当前效果。`docs/demo/` 保留演示及来源说明，
不同图像版本有引用关系，不因文件较旧而删除。

## 本地启动（Windows）

启动脚本面向 Windows PowerShell。需要 Python 3.12、Node.js 22.12+（或受 Vite 支持的较新版本）、npm 和 Docker。正文中文字体优先使用 Windows 系统字体；其他系统需自行配置合法中文字体，不能直接照搬 Windows 字体路径。

### 1. 安装依赖

```powershell
git clone https://github.com/969385278/Posterpilot.git posterpilot
cd posterpilot
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e "apps/api[dev]"
npm --prefix apps/web ci
Copy-Item .env.example .env
```

在本地 `.env` 填写 `DEEPSEEK_API_KEY`、`ARK_API_KEY`，并按账户可用模型调整模型名称。不要提交真实密钥。默认使用 DeepSeek 文本/视觉接口与 Ark Seedream 生图；可用 `VISION_PROVIDER=ark` 切换视觉适配器。平台必须实际支持所填模型及多模态接口，代码提供适配不代表任意模型均可用。

### 2. 检索依赖与索引

```powershell
docker compose -f infra/docker-compose.yml up -d ollama chroma
docker compose -f infra/docker-compose.yml exec ollama ollama pull bge-m3
.\.venv\Scripts\python.exe scripts/validate_knowledge.py
.\.venv\Scripts\python.exe scripts/build_knowledge_index.py
```

公开版本保留经整理的设计规则卡和来源引用，**不包含未确认再分发授权的原始 PDF 及其提取全文**。`source_chunks.jsonl` 在公开版本中为空，不影响已有规则卡索引。接入自己的 PDF 前，需确认使用/发布权限，再补充本地来源清单。

### 3. 启动 API 与前端

在两个终端分别运行：

```powershell
npm run dev:api
npm run dev:web
```

- 工作台：`http://127.0.0.1:5173`
- API 文档：`http://127.0.0.1:8787/docs`

Chroma 在首次知识检索时连接；服务未启动不会阻断本地画像、案例、素材和工具管理。
检索失败会保留 `vector_store_unavailable` 状态及空结果，后续请求可重试连接。
本地管理可用不代表模型调用或知识检索已就绪，生成仍需配置真实模型服务。

本地 SQLite API 使用单 worker，同一任务数据库仅允许一个 API 实例。重启时将上次遗留的
排队中或执行中任务标记为“执行中断”，保留已有产物；不会自动重放模型请求。
等待人工确认的任务保持原状态，可继续查看与提交决策。内存库、SQLite URI 与其他数据库
不自动执行此恢复流程，需要另行配置进程协调。请勿在 API 运行时删除 `.runtime.lock` 文件。

DeepGaze 不可用时，系统应明确标记该信号缺失，并保留其他评测结果，不能把缺失信号视为真实得分。

### 4. 可选 DeepGaze

```powershell
py -3.12 -m venv .venv-deepgaze
.\.venv-deepgaze\Scripts\python.exe -m pip install -e "services/deepgaze[dev]"
.\.venv-deepgaze\Scripts\python.exe -m pip install -r services/deepgaze/requirements-model.txt
npm run dev:deepgaze
```

模型依赖与 GPU/CUDA 版本有关，需按本机环境核对，权重不随仓库分发。详见 [DeepGaze 说明](docs/deepgaze-feasibility.md)。完成全部环境准备后，可用 `npm run dev` 启动完整开发环境。

## 测试与验证

```powershell
.\.venv\Scripts\python.exe -m pytest apps/api/tests -q
.\.venv\Scripts\python.exe -m ruff check apps/api scripts
npm --prefix apps/web test
npm --prefix apps/web run build
.\.venv\Scripts\python.exe scripts/evaluate_retrieval.py --offline
```

安装独立 DeepGaze 开发依赖后可运行 `npm run verify`，统一脚本为 `scripts/verify.ps1`；已移除重复且引用旧路径的 `verify-project.ps1`。单元测试使用可替换依赖，不代表每次都会真实生图或 GPU 推理。历史发布检查见 [发布检查](docs/publication-check.md)，本次检查及尚存问题见 [清理记录](docs/repository-cleanup-20260925.md)。

## 发布说明与许可

这是从原本地 GazePoster 项目整理的独立发布副本，品牌、包名和 `POSTERPILOT_` 前缀已统一。新安装使用新的默认数据库/知识集合，不携带旧任务数据、密钥或历史提交。旧 `.env` 不能不经检查直接复用。

仓库排除了简历、头像、原始设计 PDF、旧摄像头/表情代码、虚拟环境、模型缓存、日志、数据库和运行产物。示例海报是明确选取的演示资料。

第三方字体、案例和模型各有独立许可，见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。本次公开代码及明确列出的演示资料，未擅自选择 MIT 等整仓开源许可；第三方许可不代表整个项目使用同一许可。

## 2026-09-24：DeepSeek 临时替代 Jev

生产服务默认 `INTENT_ROUTING_MODE=deepseek`：使用现有 DeepSeek 文本接口一次完成意图分类与需求解析，返回 `route_method=llm_direct`、`fallback_used=false`、`classifier_confidence=null`。这是通用模型直接解析，不代表 Jev 级联或经过校准的决策概率。原规则加低置信度回退仍可通过 `INTENT_ROUTING_MODE=rules` 使用。原话校验、活动事实校验、确定性控制解析和用户确认继续生效。

`VISION_PROVIDER=deepseek` 默认复用 `DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL` 与 `DEEPSEEK_TEXT_MODEL`；可用 `DEEPSEEK_VISION_MODEL` 覆盖视觉模型。请求通过 `/chat/completions` 发送文字与 `image_url`（含本地图片 data URL）。`VISION_PROVIDER=ark` 可恢复旧视觉配置。

Seedream 仍使用 `ARK_API_KEY`、`ARK_BASE_URL` 和 `ARK_IMAGE_MODEL`。因此默认需要两套凭证：DeepSeek 与 Seedream。平台若使用其他网关，必须提供对应 base URL 与精确模型 ID。用户提到的“DeepSeek v4.1 flash”尚未在实际平台上联调，不能把显示名称当作已验证的 API 模型 ID；现有模型默认值未猜测替换。

以上为适配方式说明。后续本地路由、编辑、记忆和工具选择实验分别保存了真实模型响应，证据范围见 [实验记录导航](docs/evaluation-evidence-map.md)；这些实验不证明所有模型配置和能力均已通过。Jev 仍未接入，相关分流和成本数字属于情景估算。

### 本机 Chroma（不用 Docker）

在独立终端运行 `.\scripts\run_chroma.ps1`（默认 localhost:8000，持久化目录 `data/chroma-runtime`），然后运行 `.\.venv\Scripts\python.exe scripts/build_knowledge_index.py` 建立审核知识索引。停止服务时在该终端按 Ctrl+C。端口修改后同步设置 `.env` 的 `CHROMA_URL`。Ollama 与 bge-m3 仍需可用。

DeepGaze 使用独立 `.venv-deepgaze` 环境；安装时先运行 `python -m venv .venv-deepgaze`，再运行 `.\.venv-deepgaze\Scripts\python.exe -m pip install -e services/deepgaze -r services/deepgaze/requirements-model.txt`。启动命令为 `.\scripts\run_deepgaze.ps1`。`/health` 只证明服务存活，首次真实 `/v1/predict` 才能证明模型及权重可用。

### 初版文字可读性

生成背景后，初次排版会检查文字包围框的背景采样对比，从设计色板和中性黑白色中选择更清晰的文字颜色；必要时关闭固定暗色渐变。选择结果写入布局的文字颜色和 `readability_scrims`，旧布局缺省保留渐变。该步骤仅用于初版，后续修改按明确参数和锁定执行。采样对比达标不代表所有字形、复杂背景或真人阅读体验都已通过验收，视觉评测意见仍保留。
