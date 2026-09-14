# PosterPilot 框架、文件职责与功能代码映射

> 生成日期：2026-07-13  
> 项目目录：`F:\workspace\PosterPilot`  
> 说明：本文以当前实际文件为准，不把规划中的文件描述为已实现。

## 1. 状态说明

本文使用以下状态：

- **已完成（新架构）**：Python/FastAPI、React 或新 RAG 代码已经存在，并有测试或构建验证。
- **已迁移数据**：旧版数据已经转换到新格式，但内容仍可能需要人工审核。
- **旧版归档**：原 Node.js、原生 TypeScript、摄像头和表情实现已移入 `before/`，不参与当前运行、构建和测试。
- **仅有契约**：Pydantic 类型已经定义，但对应业务执行器尚未实现。
- **尚未实现**：架构文档中已有设计，当前代码目录中还没有对应实现。
- **生成文件**：依赖安装、Python 运行或 TypeScript 构建自动生成，不应手工修改。

当前整体进度约为 98%。已完成新工程骨架、领域 Schema、SQLite、产物保存、PDF 文本处理、知识数据迁移和 RAG 检索、三类模板、Pillow 中文渲染、DeepSeek/Ark/ComfyUI Provider、硬规则评测、评分聚合、DeepGaze 独立服务、Human-in-the-loop ReAct 优化闭环、FastAPI 人工决策接口与 SSE 事件流，以及可展示轮次海报、评分、热力图、RAG 引用和工具轨迹的 React 工作台。旧实现也已完成归档。剩余边界是使用有效的真实外部服务配置完成一次端到端验收。

> **2026-07-13 修订优先级**：本文此前“模型 Provider、模板渲染、DeepGaze 未实现”的旧描述已失效；以第 4.6 节、第 4.9 节和第 16 节的修订状态为准。

## 2. 当前架构概览

```text
apps/web                       React 简洁工作台：首页、需求输入、执行轨迹、结果对比与历史
    |
    | HTTP + SSE
    v
apps/api                       FastAPI 新主后端：任务 API、SSE、Agent 执行与产物下载
    |-- schemas                数据契约
    |-- persistence            SQLite 任务记录
    |-- services               任务产物保存
    |-- rag                    PDF、知识卡片、检索与引用
    |-- providers              DeepSeek、Ark、ComfyUI 与 Ollama 适配器
    `-- agent                  确定性生成 Workflow + Human-in-the-loop ReAct 优化轮次

Chroma + Ollama                Docker 服务，供向量检索与 Embedding 使用
services/deepgaze              独立 GPU 注意力预测服务（模型预测，不是用户眼动）

before/                       旧 Node/TypeScript/摄像头项目归档，不参与当前运行
```

## 3. 根目录文件

| 文件 | 写了什么 | 负责什么 | 当前状态 |
|---|---|---|---|
| `.env.example` | 火山方舟、DeepSeek、ComfyUI、Ollama、Chroma、FastAPI、SQLite、DeepGaze 等环境变量示例 | 统一说明本地和云端服务配置 | 已扩展到新架构；真实服务调用需填入有效配置 |
| `.gitignore` | 忽略依赖、构建产物、日志、虚拟环境、SQLite、Chroma、DeepGaze 缓存和任务产物 | 防止运行时数据进入版本管理 | 已完成 |
| `AGENTS.md` | 项目文件访问与搜索限制 | 约束迁移期间的安全操作边界 | 已生效 |
| `package.json` | 只保留新架构的启动、测试和构建命令 | 统一调度 FastAPI、React、DeepGaze 和完整验证 | 已完成；默认命令不再引用旧版 |
| `package-lock.json` | 根命令包的空依赖锁 | 固定根 npm 元数据 | 已重建 |
| `README.md` | 当前项目定位、核心能力、目录、启动和验证方式 | 新架构使用入口 | 已重写 |
| `before/` | 旧根入口、Node 后端、原生 TypeScript 前端、浏览器模型、测试和旧脚本 | 保存迁移历史，便于面试讲解演进过程 | 已归档，不参与当前运行 |
| `dev*.log`、`dev-server*.log` | 历史开发日志 | 无业务职责 | 生成文件，后续清理 |

## 4. `apps/api`：新 FastAPI 后端

### 4.1 工程配置

| 文件 | 写了什么 | 负责什么 | 完成功能 |
|---|---|---|---|
| `apps/api/pyproject.toml` | FastAPI、Pydantic、SQLAlchemy、LangGraph、LangChain、Chroma、Ollama、Pillow、PyPDF、pytest、Ruff 等依赖与工具配置 | 定义 Python 3.12 后端环境 | 已完成可编辑安装和测试配置 |
| `apps/api/app/__init__.py` | Python 包说明 | 标记 `app` 为应用包 | 已完成 |
| `apps/api/app/main.py` | 创建 FastAPI 应用、载入配置、注册异常处理、定义健康接口并注册任务路由 | 新后端入口 | 已完成并注入真实运行时依赖 |

### 4.2 `apps/api/app/core`

| 文件 | 写了什么 | 负责什么 | 完成功能 |
|---|---|---|---|
| `core/__init__.py` | 包说明 | 标记核心模块 | 已完成 |
| `core/config.py` | `Settings`、`.env` 读取、API、数据目录、SQLite、Chroma、Ollama 和 Embedding 配置 | 集中管理运行参数 | 已完成当前已实现模块的配置 |
| `core/logging.py` | `configure_logging()` | 统一日志级别和格式 | 已完成基础日志 |
| `core/exceptions.py` | `PosterPilotError`、统一 JSON 错误响应、异常注册 | 让业务错误具有稳定错误码和 HTTP 状态 | 已完成基础异常处理 |

### 4.3 `apps/api/app/schemas`

这一目录只定义数据契约，不直接执行海报生成。

| 文件 | 写了什么 | 负责什么 | 完成功能 |
|---|---|---|---|
| `schemas/__init__.py` | 导出主要 Schema | 简化跨模块导入 | 已完成 |
| `schemas/brief.py` | `CanvasSize`、`PosterBrief`、海报类型、非空文本约束 | 校验用户海报需求 | 已完成；强制竖版画布和活动必填信息 |
| `schemas/layout.py` | 十六进制颜色、归一化坐标框、布局元素、元素角色、`PosterLayout` | 定义可程序化修改的海报元素 | 已完成；由布局引擎、渲染器和优化动作执行器使用 |
| `schemas/design_spec.py` | `ColorPalette`、`DesignSpec`、模板 ID、预期注意路径 | 约束 LLM 输出的设计方案 | 已完成；已接入设计规划节点 |
| `schemas/evaluation.py` | 硬规则问题、注视点、注意力预测、视觉评价、评分拆分、综合报告 | 统一三类评测输出 | 已完成；已被评测和报告构建使用 |
| `schemas/optimization.py` | `OptimizationAction`、`OptimizationPlan` 和九种动作白名单 | 限制 Agent 只能执行安全、结构化的优化动作 | 已完成；布局白名单动作已由执行器应用 |
| `schemas/run.py` | 任务状态、任务事件、产物引用、`RunRecord` | 定义任务生命周期和文件索引 | 已完成契约 |

### 4.4 `apps/api/app/persistence`

| 文件 | 写了什么 | 负责什么 | 完成功能 |
|---|---|---|---|
| `persistence/__init__.py` | 导出 `RunRepository` | 简化持久化模块使用 | 已完成 |
| `persistence/database.py` | SQLAlchemy Engine、Session Factory、自动建表 | 建立 SQLite 连接 | 已完成 |
| `persistence/models.py` | `RunRow` 数据表，保存 brief、状态、错误、产物和时间 | 定义 SQLite 表结构 | 已完成 |
| `persistence/run_repository.py` | 创建、查询、列表、更新状态、增加产物；统一 SQLite UTC 时间 | 管理本地任务记录 | 已完成并有测试 |

### 4.5 `apps/api/app/services`

| 文件 | 写了什么 | 负责什么 | 完成功能 |
|---|---|---|---|
| `services/__init__.py` | 导出 `ArtifactService` | 简化服务导入 | 已完成 |
| `services/artifact_service.py` | JSON、二进制文件、`events.jsonl` 的安全写入；文件名白名单；原子替换 | 管理 `data/runs/<run_id>/` 任务产物 | 已完成并有路径穿越测试 |

### 4.6 `apps/api/app/providers`

| 文件 | 写了什么 | 负责什么 | 完成功能 |
|---|---|---|---|
| `providers/__init__.py` | Provider 包说明 | 预留统一外部服务适配层 | 已创建 |
| `providers/embedding/__init__.py` | 导出 Ollama 工厂 | Embedding Provider 入口 | 已完成 |
| `providers/embedding/base.py` | `EmbeddingProvider` Protocol | 规定 `embed_documents` 和 `embed_query` 接口 | 已完成接口 |
| `providers/embedding/ollama.py` | 创建 LangChain `OllamaEmbeddings`，设置模型、地址和超时 | 调用本地 `bge-m3` | 代码完成；真实 Ollama/Chroma 检索调用待端到端验收 |
| `providers/llm/base.py`、`llm/deepseek.py` | JSON Chat 协议、DeepSeek OpenAI-compatible 调用、超时和密钥脱敏 | 为设计与优化节点提供结构化文本输出 | 已完成，假响应契约测试通过 |
| `providers/vision/base.py`、`vision/ark.py` | 海报图像 + Prompt 的 Ark 视觉模型调用与 JSON 解析 | 为视觉评测提供结构化模型评价 | 已完成，假响应契约测试通过 |
| `providers/image/base.py`、`image/ark.py` | 无文字主视觉生成、URL/Base64 响应、参考图失败重试 | Seedream/Ark 生图适配 | 已完成，假响应契约测试通过 |
| `providers/image/comfyui.py` | 工作流加载、Prompt 节点定位、排队与历史轮询 | 本机 ComfyUI 生图适配 | 已完成，未配置工作流时明确失败 |

### 4.7 `apps/api/app/rag`

| 文件 | 写了什么 | 负责什么 | 完成功能 |
|---|---|---|---|
| `rag/__init__.py` | 导出知识卡片、切片、来源清单和检索案例模型 | RAG 包入口 | 已完成 |
| `rag/models.py` | `KnowledgeCard`、`SourceChunk`、`SourceManifest`、`RetrievalRequest`、`RetrievalResult`、引用和向量命中等模型 | 约束知识数据和检索结果 | 已完成并有 Schema 测试 |
| `rag/repository.py` | 从 JSONL/JSON 加载卡片、切片和检索案例 | 文件型知识仓库 | 已完成 |
| `rag/indexer.py` | 将批准卡片转换为 LangChain `Document`，重建 Chroma Collection | 一张卡片对应一个向量文档 | 已完成并有假 Chroma 测试 |
| `rag/langchain_chroma_store.py` | 创建远程 Chroma Client；按候选 ID 执行异步相似度检索 | Chroma 适配层 | 代码和契约测试已完成；本机 Chroma 尚未启动验证 |
| `rag/retriever.py` | 先按审核状态、用途和目标区域过滤，再调用向量库，最后混合重排和截断 | RAG 运行时检索主流程 | 已完成并有 fail-open 测试 |
| `rag/reranker.py` | 中文字符归一化、Bigram Dice、词法相似度和向量/词法混合分数 | 改善中文别名与问题描述排序 | 已完成 |
| `rag/citations.py` | 将检索匹配转换为带来源、页码、定位符和分数的引用 | 支持前端和报告展示理论依据 | 已完成 |

### 4.8 `apps/api/app/rag/ingestion`

| 文件 | 写了什么 | 负责什么 | 完成功能 |
|---|---|---|---|
| `ingestion/__init__.py` | 导出 PDF 页面提取入口 | ingestion 包入口 | 已完成 |
| `ingestion/chunker.py` | 清除独立页码、统一空白、修复 PDF 中文断行、按段落和句子切片、平衡末尾短块 | 生成适合 Embedding 的中文原文切片 | 已完成并有回归测试 |
| `ingestion/pdf_text.py` | 使用 PyPDF 按页提取文本并保留一基页码 | 处理有文本层的 PDF | 已用于 `qinghua.pdf` |
| `ingestion/selected_ocr.py` | 显式页码校验、可注入 OCR Engine、仅处理选中页面 | 防止 `lai.pdf` 被意外全书 OCR | 接口和测试已完成；真实 OCR Engine 尚未接入 |
| `ingestion/knowledge_cards.py` | 把模型生成的候选卡片绑定到不可变原文来源和页码 | 后续半自动整理知识卡片 | 辅助函数已完成；尚未接入 LLM |

### 4.9 `apps/api/app/evaluation` 与 `services/deepgaze`

| 文件 | 写了什么 | 负责什么 | 完成功能 |
|---|---|---|---|
| `evaluation/hard_rules.py` | 缺失区域、文字重叠、安全边距、标题层级、信息密度、颜色数量规则 | 不依赖模型的确定性排版评测 | 已完成，单元测试覆盖 |
| `evaluation/score_aggregator.py` | 硬规则 40、视觉 35、注意力 25 的可用权重聚合 | 避免把不可用评测伪装成通过 | 已完成，已注入 Agent 评测节点 |
| `evaluation/deepgaze_client.py` | 调用独立 DeepGaze HTTP 服务、解析注视点和热力图、服务异常转 `unavailable` | 连接主 FastAPI 与注意力预测服务 | 已完成，2 项契约测试通过 |
| `services/deepgaze/app/main.py`、`api.py` | `GET /health`、`POST /v1/predict` | DeepGaze 独立 FastAPI 服务 | 已完成并以真实 CUDA 服务联调 |
| `services/deepgaze/app/model.py` | 延迟加载 DeepGaze III、CUDA 选择、中心中性起点 | 调用官方 DeepGaze III 模型输出注意力热图 | 已完成；RTX 4060 真实推理通过 |
| `services/deepgaze/app/cache.py`、`fixation_sampler.py`、`heatmap.py` | 图片哈希缓存、注视点采样、PNG 热图叠加 | 保证服务输出可复用、可展示 | 已完成 |
| `services/deepgaze/requirements-model.txt`、`scripts/run_deepgaze.ps1` | 锁定 CUDA/模型提交并提供启动入口 | 复现 DeepGaze 本机环境 | 已完成 |

### 4.10 `apps/api/app/agent`：Workflow + Human-in-the-loop ReAct

| 文件 | 写了什么 | 负责什么 | 完成功能 |
|---|---|---|---|
| `agent/state.py` | 全链路状态，包括 brief、检索、设计、评测、人工要求、轮次、工具轨迹和产物 | 让 Workflow 与 ReAct 子图共享可追踪状态 | 已完成 |
| `schemas/react.py` | 人工决策、等待确认、ReAct 决策、工具轨迹和轮次快照 Schema | 限制人工输入和 Agent 工具输出边界 | 已完成并有非法输入测试 |
| `agent/prompts/design.py`、`vision_review.py`、`react.py` | 设计、视觉评审和单步 ReAct 决策 Prompt | 只输出结构化决策摘要，不暴露隐藏思维链 | 已完成 |
| `agent/nodes/retrieve_knowledge.py`、`plan_design.py` | 生成阶段 RAG 检索与 `DesignSpec` 校验；拒绝模型伪造未检索引用 | “知识 → 设计方案”节点 | 已完成 |
| `agent/nodes/generate_visual.py`、`render_draft.py` | 调用生图 Provider、保存无文字主视觉、Pillow 输出初版海报 | “设计方案 → 初版海报”节点 | 已完成，假 Provider 测试通过 |
| `agent/nodes/evaluate.py` | 对初版和优化版使用相同硬规则、DeepGaze、Ark 视觉、评分和报告构建逻辑；保存热力图产物 | 避免优化前后评价标准漂移 | 已完成；服务不可用时明确标为 `unavailable` |
| `agent/nodes/human_review.py` | 构造 `HumanCheckpoint`、调用 LangGraph `interrupt()`、解析 `Command(resume=...)` 的人工决策并路由 | 同一张图中的原生 Human-in-the-loop 暂停与恢复 | 已完成；等待状态写入 SQLite checkpointer |
| `agent/nodes/react_decide.py`、`execute_react_tool.py` | 每次选择一个语义工具、执行并把 Observation 回流到下一次决策 | 自定义 ReAct 循环 | 已完成；单轮最多 3 个工具 |
| `agent/nodes/complete_round.py`、`finalize.py` | 每轮统一渲染、复评、保存快照，并在用户结束后汇总结果 | 保留轮次级版本和真实评分变化 | 已完成；最多 3 轮 |
| `agent/tools/react_tools.py` | 知识检索、排版、布局和现有主视觉调整的语义工具注册表 | 将 Agent 自主选择限制在确定性白名单内 | 已完成；不支持重新生图 |
| `agent/tools/generation_tools.py` | 下载 URL/Base64 生图结果并保存为任务文件 | 让远程和本地 Provider 统一交给渲染器 | 已完成 |
| `agent/graph.py` | 把初版生成、`human_review` interrupt、ReAct 工具循环、每轮复评和 finalize 合并为同一张持久化图；保留旧独立图供聚焦测试 | 同一个 thread 内完成完整 Agent 生命周期 | 已完成；`run_id` 作为 `thread_id` |
| `agent/executor.py` | 懒加载 `AsyncSqliteSaver`、执行初始输入、通过 `Command(resume=...)` 恢复、提取 interrupt payload、关闭连接 | 连接 LangGraph 原生暂停恢复与任务生命周期 | 已完成；API 重启后可恢复等待中的任务 |
| `poster/action_executor.py` | 校验后应用位置、尺寸、字号、颜色、行距、对齐、透明度动作并重新校验边界 | 优化 Agent 的安全布局修改器 | 已完成；亮度和重新生成主视觉走独立执行路径 |

## 5. `apps/api/tests`：新后端测试

| 文件 | 主要验证内容 |
|---|---|
| `tests/conftest.py` | 测试环境变量隔离和批准知识卡片 Fixture |
| `tests/test_health.py` | FastAPI 健康接口 |
| `tests/schemas/test_brief.py` | 活动字段、海报类型和竖版画布 |
| `tests/schemas/test_design_spec.py` | 合法设计方案、颜色格式、坐标越界 |
| `tests/schemas/test_optimization.py`、`test_react.py` | 优化动作、人工决策、语义工具白名单和轮次快照 |
| `tests/persistence/test_run_repository.py` | SQLite 创建、读取、状态更新、时间和排序 |
| `tests/services/test_artifact_service.py` | JSON/JSONL 写入、产物引用和路径穿越防护 |
| `tests/rag/test_knowledge_models.py` | 批准卡片来源追踪、精选 OCR 页码、来源 ID 唯一性 |
| `tests/rag/ingestion/test_chunker.py` | 中文断词、页码清理、段落切片和孤儿块 |
| `tests/rag/ingestion/test_selected_pages.py` | OCR 空页码、越界、重复和显式页面调用 |
| `tests/rag/test_retriever.py` | 元数据先过滤、低相似度剔除、Chroma 故障降级 |
| `tests/rag/test_citations.py` | 页码、来源定位和相似度引用 |
| `tests/rag/test_chroma_store.py` | Chroma 候选 ID 过滤和批准卡片建库 |
| `tests/agent/test_react_tools.py`、`test_react_graph.py`、`test_hitl_executor.py` | 工具边界、Observation 回流、三工具上限、原生暂停、恢复、结束和跨 Executor SQLite 恢复 |

最近一次完整验证为 API 117 项、DeepGaze 4 项、Web 10 项测试通过，前端构建和 Python 静态检查通过。

## 6. `apps/web`：新 React 前端

| 文件 | 写了什么 | 负责什么 | 完成功能 |
|---|---|---|---|
| `apps/web/package.json` | React、Vite、Vitest 和 Testing Library 依赖与命令 | 新前端独立 npm 包 | 已完成基础工程 |
| `apps/web/package-lock.json` | 新前端依赖锁定 | 可复现安装 | 生成文件 |
| `apps/web/index.html` | 中文页面元信息和 React Root | 新前端 HTML 入口 | 已完成 |
| `apps/web/vite.config.ts` | React 插件、5173 端口、`/api` 到 8787 的代理、Vitest 环境 | 开发、测试和构建配置 | 已完成 |
| `apps/web/tsconfig.json` | React/DOM/严格 TypeScript 设置 | 新前端类型检查 | 已完成 |
| `apps/web/tsconfig.tsbuildinfo` | TypeScript 增量编译缓存 | 无业务职责 | 生成文件 |
| `src/vite-env.d.ts` | Vite 客户端和 CSS 导入类型 | 解决 TypeScript 资源声明 | 已完成 |
| `src/main.tsx` | React Root、StrictMode、全局 CSS 导入 | 新前端启动入口 | 已完成 |
| `src/app/App.tsx` | 首页与工作台切换 | 从项目定位页进入需求工作台 | 已完成 |
| `src/app/App.test.tsx` | 产品名和主按钮可访问性测试 | 防止首屏入口消失 | 已完成 |
| `src/api/client.ts` | 任务、等待确认、人工决策、轮次、工具轨迹和 SSE 类型及客户端 | 连接 FastAPI HITL 接口 | 已完成 |
| `src/features/brief/BriefForm.tsx` | MVP 海报需求表单、演示样例填充和提交 | 创建任务 | 已完成 |
| `src/pages/WorkspacePage.tsx` | 创建前需求页与创建后 60/40 海报/Agent 双栏工作台 | 协调轮询、SSE、人工决策和结果展示 | 已完成 |
| `src/features/agent/AgentConsole.tsx` | 当前问题、知识引用、工具轨迹、批准、自然语言要求和结束操作 | Human-in-the-loop 核心交互 | 已完成并有组件测试 |
| `src/features/agent/AgentTimeline.tsx` | 初版、人工决策和 ReAct 复评三阶段轨迹 | 显示闭环阶段 | 已完成 |
| `src/features/poster/RoundGallery.tsx` | 初版与每轮完成后海报的标签切换 | 只展示轮次级版本，默认最新 | 已完成并有组件测试 |
| `src/features/poster/PosterPreview.tsx` | 示例预览和任务状态 | 为真实初版/优化版产物预留展示位置 | 已完成基础状态展示 |
| `src/styles/tokens.css` | 明暗主题、冷灰色板、钴蓝强调色、字体、圆角和阴影 Token | 新前端设计变量 | 已完成 |
| `src/styles/global.css` | 桌面/窄屏布局、按钮状态、海报图片、流程区和减少动画设置 | 新前端基础视觉 | 已完成并做过 1280px、390px 视觉 QA |
| `src/test/setup.ts` | `jest-dom` 扩展 | React 测试初始化 | 已完成 |
| `apps/web/public/templates/default-poster-red-mansion.jpeg` | 从旧项目复制的真实海报示例 | 首页视觉占位 | 临时复用；后续改为新系统真实产物 |

MVP 工作台组件已完成；真实端到端服务验收仍待执行。

## 7. `data/knowledge`：新知识数据

| 文件 | 写了什么 | 负责什么 | 当前数据状态 |
|---|---|---|---|
| `source_manifest.yaml` | 2 份 PDF、3 组外部权威来源和 1 组内部候选来源；记录处理方式、主题和状态 | 知识来源总清单 | 6 个来源；`lai.pdf` 页码尚未选择 |
| `pdf_inventory.json` | PDF 页数、文本页数量和字符统计 | 判断文本提取或 OCR 策略 | `qinghua.pdf` 44 页都有文本；`lai.pdf` 291 页都无文本层 |
| `source_chunks.jsonl` | 带来源、页码、标题、提取方式和审核状态的原文片段 | RAG 原文层和引用依据 | 44 条 `qinghua.pdf` 待审核切片 |
| `knowledge_cards.jsonl` | 设计规则、问题信号、动作、约束、用途、目标区域和来源 | RAG 可执行知识层 | 11 条卡片，其中 6 条批准、5 条候选 |
| `retrieval_cases.json` | 固定问题、上下文和期望卡片 ID | 计算 Recall@3 和 MRR | 8 个案例；离线基线 Recall@3、MRR 均为 1.000 |

运行时目录 `data/chroma/`、`data/runs/`、`data/deepgaze_cache/` 已加入忽略规则，目前不属于源代码。

## 8. `docs`：资料、架构和计划

| 文件 | 内容与用途 |
|---|---|
| `docs/pdf/qinghua.pdf` | 44 页 AIGC 海报设计资料，具有文本层，已经生成待审核切片 |
| `docs/pdf/lai.pdf` | 291 页海报设计底层资料，无文本层，只允许精选页 OCR |
| `docs/knowledge-preparation.md` | 两份 PDF 的处理边界、知识数据层次和常用命令 |
| `docs/superpowers/specs/2026-07-12-poster-agent-architecture-design.md` | 已确认的新项目定位、目录、Agent 边界、评测和验收标准 |
| `docs/superpowers/plans/2026-07-12-poster-agent-migration.md` | 十阶段实施计划、精确文件、测试命令和当前执行进度 |
| `docs/superpowers/plans/2026-07-10-poster-rule-rag.md` | 旧版 Node RAG 实施计划，作为迁移历史参考 |
| `docs/demo/golden-demo-red-mansion.md` | 红楼梦竖版黄金案例的需求、HITL 输入、ReAct 工具轨迹、RAG 引用、评分边界与面试讲解重点 |
| `docs/demo/assets/*.png` | 黄金案例的初版、轮次海报和两张 DeepGaze 注意力热力图 |
| `docs/framework-and-feature-map.md` | 本文档，按文件和功能双向说明当前代码 |

## 9. `scripts`：当前开发、知识处理和验证命令

### 9.1 新 Python 脚本

| 文件 | 写了什么 | 负责什么 | 当前状态 |
|---|---|---|---|
| `scripts/inventory_pdfs.py` | 逐页统计 PDF 文本字符和文本页 | 选择文本提取或 OCR 策略 | 已执行并生成 `pdf_inventory.json` |
| `scripts/ingest_knowledge.py` | 按来源提取 PDF、切片、覆盖该来源旧切片；支持 `--dry-run` | 生成可追溯原文切片 | 已用于 `qinghua.pdf`；拒绝直接处理 selected OCR 来源 |
| `scripts/validate_knowledge.py` | 校验 YAML、JSONL、来源存在性、ID 唯一性和案例引用 | 防止无来源或损坏知识进入建库 | 已完成并通过 |
| `scripts/build_knowledge_index.py` | 创建 Ollama Embedding、连接远程 Chroma、重建批准卡片 Collection | 真实向量建库 | 已用 6 条批准卡片完成真实建库 |
| `scripts/evaluate_retrieval.py` | 支持离线词法基线和在线 Ollama+Chroma 两种评测 | 输出 Recall@3、MRR 和失败案例 | 离线 Recall@3/MRR 均为 1.000；在线 Recall@3=1.000、MRR=0.875 |
| `scripts/run_api.ps1` | 在 8787 端口启动 FastAPI；可选 `-Reload` | 单独启动新任务 API | 已完成 |
| `scripts/run_deepgaze.ps1` | 在 8001 端口启动 DeepGaze 服务 | 单独启动 GPU 注意力预测服务 | 已完成 |
| `scripts/run_all.ps1` | 启动 Ollama、Chroma、FastAPI、DeepGaze 和 React，并把输出写入 `logs/` | 一键启动本地演示所需服务 | 已完成；尚未用真实云端配置执行 |
| `scripts/verify.ps1` | 顺序执行 API、DeepGaze、Web 测试、静态检查与前端构建 | 一键本地回归验证 | 已完成并通过 |

### 9.2 新基础设施配置

| 文件 | 写了什么 | 负责什么 | 当前状态 |
|---|---|---|---|
| `infra/docker-compose.yml` | Ollama 与 Chroma 容器、端口和项目本地持久化卷 | 新 RAG 运行依赖的一键启动 | Compose 配置已校验；容器真实运行待端到端验收 |

### 9.3 `before/scripts`：旧脚本归档

| 文件 | 负责什么 | 当前状态 |
|---|---|---|
| `before/scripts/dev.mjs` | 同时启动旧 Node API 和旧 Vite 前端 | 已归档 |
| `before/scripts/lib/load-env.mjs` | 旧 Node 代码读取 `.env` | 已归档 |
| `before/scripts/check-rag-services.mjs` | 检查旧 Ollama/Chroma 服务 | 已归档 |
| `before/scripts/run-chroma.mjs` | 启动旧本地 Chroma | 已归档 |
| `before/scripts/pull-ollama-model.mjs` | 拉取旧配置的 Ollama 模型 | 已归档 |
| `before/scripts/build-poster-rule-index.mjs` | 旧 Node 规则建库 | 已由 Python 脚本替代并归档 |
| `before/scripts/evaluate-poster-rule-retrieval.mjs` | 旧 Node 检索评测 | 已由 Python 脚本替代并归档 |
| `before/scripts/validate-poster-rules.mjs` | 旧规则 JSON 校验 | 已由新 Schema 和 Python 校验替代并归档 |
| `before/scripts/migrate_legacy_knowledge.py` | 把旧规则和检索案例映射为新模型 | 迁移已执行，脚本已归档 |

## 10. `before/server`：旧 Node.js 后端归档

该目录完整保存旧 Node.js 后端，只用于历史参考，不参与当前运行。

| 文件 | 写了什么和负责什么 | 当前状态 |
|---|---|---|
| `before/server/index.mjs` | 两千行以上单文件后端；需求摘要、需求提取、DeepSeek/Ark 调用、生图、视觉区域分析、优化提示、旧 API 路由和 fallback | 已归档 |
| `before/server/providers/image/imageProvider.mjs` | Ark、ComfyUI 和本地 fallback 图片 Provider | 对应能力已迁移到 Python Provider |
| `before/server/providers/embedding/embeddingProvider.mjs` | LangChain Ollama Embedding Provider | 已有 Python 替代并归档 |
| `before/server/rag/ruleCore.mjs` | 旧规则文档转换、元数据过滤、查询构造和 Prompt 格式化 | 核心思想已迁移到 Python |
| `before/server/rag/ruleRepository.mjs` | 加载旧规则 JSON | 已由 `KnowledgeRepository` 替代 |
| `before/server/rag/posterRuleRetriever.mjs` | 旧向量检索、词法重排、阈值和 fail-open | 已迁移到 Python `retriever.py` 和 `reranker.py` |
| `before/server/rag/langchainChromaStore.mjs` | 旧 Chroma 适配和索引 | 已迁移到 Python |
| `before/server/rag/posterRuleService.mjs` | 组合仓库、Embedding、Chroma 和检索配置 | 已由 FastAPI 依赖和 Agent Tool 替代 |
| `before/server/rag/knowledge/poster-rules.json` | 11 条旧规则 | 已迁移到 `data/knowledge/knowledge_cards.jsonl` |
| `before/server/rag/knowledge/README.md` | 旧规则格式说明 | 历史参考 |
| `before/server/rag/evaluation/retrieval-cases.json` | 8 个旧检索案例 | 已迁移到新数据目录 |

## 11. `before/src`：旧原生 TypeScript 前端归档

| 文件 | 写了什么和负责什么 | 当前状态 |
|---|---|---|
| `before/src/main.ts` | 旧单页应用主逻辑，包含需求、海报生成、摄像头反馈、诊断和优化界面 | 已归档 |
| `before/src/style.css` | 旧应用全部样式 | 已归档 |
| `before/src/api/posterApi.ts` | 调用旧 Node API 的前端客户端 | 当前由 React API 客户端替代 |
| `before/src/shared/types.ts` | 旧海报、AOI、表情、停留时间、诊断和布局类型 | 仅作历史参考 |
| `before/src/courseware.ts` | 把海报包装为旧 CoursePage/Courseware 阅读页面 | 已归档，不属于当前定位 |
| `before/src/camera/localCamera.ts` | 摄像头启动、视频流和权限处理 | 已从当前项目移除并归档 |
| `before/src/vision/faceTracker.ts` | MediaPipe 人脸、虹膜、眨眼和表情特征 | 已从当前项目移除并归档 |
| `before/src/*.bak`、`*.corrupted`、`*.pre-rewrite`、`*.txt` | 历史备份 | 已归档，无运行职责 |

## 12. `before/public`：旧浏览器资源归档

| 文件或目录 | 负责什么 | 当前状态 |
|---|---|---|
| `before/public/templates/default-poster-red-mansion.jpeg` | 旧版默认海报示例 | 已归档；副本保留在新前端示例资源中 |
| `before/public/mediapipe/models/face_landmarker.task` | MediaPipe 人脸模型 | 已归档，当前项目不使用 |
| `before/public/mediapipe/wasm/*.js`、`*.wasm` | MediaPipe 浏览器推理运行时 | 已归档，当前项目不使用 |

## 13. `before/test/rag`：旧 Node 测试归档

| 文件 | 验证内容 | 当前状态 |
|---|---|---|
| `before/test/rag/ruleCore.test.mjs` | 旧规则文档、上下文、元数据和 Prompt | 已归档 |
| `before/test/rag/posterRuleRetriever.test.mjs` | 候选过滤、阈值、重排和 fail-open | 思想已迁移到 Python 测试 |
| `before/test/rag/langchainChromaStore.test.mjs` | 旧 Chroma 查询和重建 | 已归档 |

## 14. 生成目录和不应手工修改的文件

| 目录或文件 | 来源 | 处理方式 |
|---|---|---|
| `.venv/` | Python 主后端虚拟环境 | 不提交，不手改 |
| `.venv-deepgaze/` | DeepGaze 独立环境，包含 CUDA PyTorch 与模型依赖 | 已建立，不提交，不手改 |
| `node_modules/` | 旧 Node 依赖 | 不提交，不逐文件说明 |
| `apps/web/node_modules/` | 新 React 依赖 | 不提交，不逐文件说明 |
| `dist/` | 旧前端构建产物 | 可重新生成 |
| `apps/web/dist/` | 新前端构建产物 | 可重新生成 |
| `__pycache__/`、`*.pyc` | Python 字节码 | 应由忽略规则排除，可安全清理 |
| `apps/api/posterpilot_api.egg-info/` | `pip install -e` 生成的包元数据 | 不应手工修改，可重新生成 |
| `apps/web/tsconfig.tsbuildinfo` | TypeScript 增量缓存 | 可重新生成 |
| `logs/`、`*.log` | 开发运行日志 | 不属于源代码 |
| `outputs/` | 旧报告、PPT、PDF 和图片产物 | 不属于新运行时核心代码 |

## 15. 从功能出发反查代码

### 15.1 FastAPI 启动与健康检查

```text
apps/api/app/main.py
  -> core/config.py
  -> core/logging.py
  -> core/exceptions.py
  -> tests/test_health.py
```

完成状态：健康检查、任务创建/查询、产物读取和 SSE 事件路由已注册。

### 15.2 用户海报需求校验

```text
schemas/brief.py
  -> CanvasSize
  -> PosterBrief
tests/schemas/test_brief.py
```

完成状态：支持三类竖版活动海报，标题、时间、地点、主办方必填。

### 15.3 设计方案和结构化布局

```text
schemas/layout.py
schemas/design_spec.py
tests/schemas/test_design_spec.py
```

完成状态：模板加载、布局计算、Pillow 渲染和结构化设计节点均已完成；真实 DeepSeek 调用待端到端验收。

### 15.4 Agent 优化动作安全边界

```text
schemas/optimization.py
tests/schemas/test_optimization.py
```

允许动作：位置、尺寸、字号、颜色、行距、对齐、透明度、亮度和重新生成主视觉。

完成状态：Schema 白名单、动作参数执行器和优化版二次渲染均已完成；亮度与重新生成主视觉保留独立执行路径。

### 15.5 任务记录和历史列表

```text
schemas/run.py
persistence/database.py
persistence/models.py
persistence/run_repository.py
tests/persistence/test_run_repository.py
```

完成状态：SQLite 创建、读取、列表和状态更新完成；FastAPI 已提供创建、列表、详情与产物读取的 `/api/v1/runs` 路由。

### 15.6 任务文件和事件轨迹

```text
services/artifact_service.py
schemas/run.py -> ArtifactReference、RunEvent
tests/services/test_artifact_service.py
```

完成状态：安全写入 JSON、PNG 字节和 `events.jsonl`；Agent 节点尚未产生真实事件。

### 15.7 PDF 来源盘点

```text
data/knowledge/source_manifest.yaml
scripts/inventory_pdfs.py
data/knowledge/pdf_inventory.json
```

完成状态：清华资料可直接提取；`lai.pdf` 必须 OCR。

### 15.8 PDF 文本清洗和切片

```text
rag/ingestion/pdf_text.py
rag/ingestion/chunker.py
scripts/ingest_knowledge.py
data/knowledge/source_chunks.jsonl
tests/rag/ingestion/test_chunker.py
```

完成状态：44 条清华待审核切片；尚未人工筛除纯软件操作和低价值内容。

### 15.9 精选 OCR 防护

```text
rag/ingestion/selected_ocr.py
data/knowledge/source_manifest.yaml -> selected_pages
tests/rag/ingestion/test_selected_pages.py
```

完成状态：显式页码和可注入 OCR 接口完成；`lai.pdf` 页码和真实 OCR Engine 未完成。

### 15.10 旧规则迁移和知识数据校验

```text
before/scripts/migrate_legacy_knowledge.py
scripts/validate_knowledge.py
rag/models.py
data/knowledge/knowledge_cards.jsonl
data/knowledge/retrieval_cases.json
```

完成状态：11 条规则、8 个案例迁移完成，6 条批准卡片可进入索引。

### 15.11 RAG 建库

```text
providers/embedding/ollama.py
rag/indexer.py
rag/langchain_chroma_store.py
scripts/build_knowledge_index.py
```

完成状态：代码与假 Chroma 测试完成；真实 Chroma 服务尚未联调。

### 15.12 RAG 检索与重排

```text
rag/repository.py
rag/retriever.py
rag/reranker.py
rag/citations.py
tests/rag/test_retriever.py
tests/rag/test_citations.py
tests/rag/test_chroma_store.py
```

完成状态：元数据过滤、向量检索接口、词法重排、阈值、Top K、引用和故障降级完成。

### 15.13 RAG 质量评测

```text
data/knowledge/retrieval_cases.json
scripts/evaluate_retrieval.py
```

完成状态：离线词法基线 Recall@3=1.000、MRR=1.000；在线向量评测待 Chroma。

### 15.14 新 React 首页

```text
apps/web/src/main.tsx
apps/web/src/app/App.tsx
apps/web/src/styles/tokens.css
apps/web/src/styles/global.css
apps/web/src/app/App.test.tsx
```

完成状态：首页、需求工作台、任务创建、状态轮询、SSE Agent 轨迹、真实产物、评分变化、DeepGaze 热力图、前后对比与本地历史均已接入。

### 15.15 旧版云端模型和生图

```text
before/server/index.mjs
before/server/providers/image/imageProvider.mjs
.env.example
```

完成状态：旧 Node 版已归档；新 Python 的 DeepSeek、Ark、Seedream 与 ComfyUI Provider 已实现并由默认任务运行时注入。

### 15.16 旧摄像头、表情和真实用户反馈

```text
before/src/camera/localCamera.ts
before/src/vision/faceTracker.ts
before/public/mediapipe/
before/src/shared/types.ts
```

完成状态：只存在于 `before/` 归档。当前项目已明确移除这些能力。

## 16. 功能完成情况与剩余边界

| 功能 | 计划代码位置 | 当前状态 |
|---|---|---|
| DeepSeek 文本 Provider | `apps/api/app/providers/llm/` | 已完成假响应契约测试，默认任务运行时已接入；真实调用待验收 |
| 火山方舟视觉 Provider | `apps/api/app/providers/vision/` | 已完成假响应契约测试，视觉评测节点已接入；真实调用待验收 |
| Seedream/ComfyUI 生图 | `apps/api/app/providers/image/` | 已完成假响应契约测试，生成节点已接入；真实调用待验收 |
| 三类竖版模板 | `data/templates/*.json` | 已完成 |
| Pillow 中文排版 | `apps/api/app/poster/typography.py` | 已完成 |
| 布局引擎和渲染 | `apps/api/app/poster/template_loader.py`、`renderer.py` | 已完成；高级自动布局尚未实现 |
| 优化动作执行 | `apps/api/app/poster/action_validator.py`、`action_executor.py`、Agent 节点 | 布局白名单动作已执行；亮度与主视觉重新生成尚未接入 |
| 硬规则评测 | `apps/api/app/evaluation/hard_rules.py` | 已完成 |
| DeepGaze 服务 | `services/deepgaze/` | 已完成；真实 CUDA 推理和 HTTP 服务联调通过 |
| 视觉评价与综合评分 | `apps/api/app/evaluation/` | 评分聚合、报告、Ark 与 DeepGaze 均已注入任务图；服务不可用时结构化降级 |
| LangGraph Agent | `apps/api/app/agent/` | 确定性生成与自定义 ReAct 轮次图已完成；Observation 会进入下一步工具决策 |
| Human-in-the-loop | `schemas/react.py`、`agent/executor.py`、`services/run_service.py` | 初版和每轮后暂停；用户可批准、输入限制或结束；最多 3 轮 |
| 任务 API 和 SSE | `apps/api/app/api/routes/`、`services/run_service.py`、`event_bus.py` | 已完成任务、pending、decisions、产物、事件回放与实时 SSE |
| React 需求表单 | `apps/web/src/features/brief/` | 已完成，可填充演示样例并创建任务 |
| Agent 操作台 | `apps/web/src/features/agent/` | 已完成问题、引用、结构化决策、工具结果与人工输入展示 |
| 轮次版本 | `apps/web/src/features/poster/RoundGallery.tsx` | 已完成初版和每轮海报切换，不保存每工具版本 |
| 评测与热力图 | `apps/web/src/features/evaluation/` | 已完成评分变化、可用权重和 DeepGaze 热力图展示 |
| 前后对比 | `apps/web/src/features/comparison/` | 已完成，展示初版与优化版真实产物 |
| 历史任务页 | `apps/web/src/features/history/` | 已完成，读取本机任务列表 |

## 17. 当前最重要的代码入口

如果要快速理解当前新代码，建议按以下顺序阅读：

1. `docs/superpowers/specs/2026-07-12-poster-agent-architecture-design.md`
2. `apps/api/app/schemas/brief.py`
3. `apps/api/app/schemas/design_spec.py`
4. `apps/api/app/rag/models.py`
5. `apps/api/app/rag/ingestion/chunker.py`
6. `apps/api/app/rag/retriever.py`
7. `apps/api/app/rag/indexer.py`
8. `apps/api/app/persistence/run_repository.py`
9. `apps/api/app/services/artifact_service.py`
10. `apps/web/src/app/App.tsx`

## 18. 当前验证命令

```powershell
# 新 Python 后端测试
.\.venv\Scripts\python.exe -m pytest apps\api\tests -q

# Python 静态检查
.\.venv\Scripts\python.exe -m ruff check apps\api scripts

# DeepGaze 服务测试和静态检查
.\.venv-deepgaze\Scripts\python.exe -m pytest services\deepgaze\tests -q
.\.venv-deepgaze\Scripts\python.exe -m ruff check services\deepgaze

# 知识数据校验
.\.venv\Scripts\python.exe scripts\validate_knowledge.py

# 离线检索评测
.\.venv\Scripts\python.exe scripts\evaluate_retrieval.py --offline

# 新 React 测试和构建
npm run test:web
npm run build:web

# 旧版回归
npm test
npm run build
```

也可直接执行 `npm run verify` 完成本地全量验证，或执行 `npm run run:all` 启动本地演示服务。真实 DeepGaze CUDA 服务已用项目海报联调；仍需在配置真实 Ark、DeepSeek、Ollama 和 Chroma 服务后完成一次云端端到端验收。该验收会触发云端模型或生图调用，因此未在未确认配置与费用前自动执行。
