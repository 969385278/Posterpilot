# PosterPilot 知识准备说明

## 当前可运行的公开知识集（2026-09-20）

当前发布副本使用 5 个来源条目、19 张知识卡，其中 14 张 approved、5 张 candidate；没有把版权 PDF 原文或未经审核 OCR 放进索引。新增 8 条知识覆盖字号层级、视觉平衡、次要文字可读性、重点色、留白、局部背景对比、细笔画和字距行距。来源快照见 `data/knowledge/web-source-review-2026-09-20.json`。

旧的对比度、视觉层级与邻近分组卡片改为中文概括，保留 ID 和来源，避免中英文正文不均衡使中文需求漏召回。新增规则仍受当前工具能力限制，例如没有开放的任意字体、图层或遮罩操作，不能因为资料提到就让 Agent 调用。

在项目根目录、已安装依赖的 Python 环境中执行：

```powershell
$env:PYTHONPATH = "$PWD/apps/api"
python scripts/validate_knowledge.py
python scripts/build_knowledge_index.py
python scripts/evaluate_retrieval.py
python scripts/evaluate_retrieval.py --offline
```

实际向量检索使用本地 Ollama `bge-m3:latest` 与 Chroma。固定 16 条检索用例的结果为 Recall@3=1.000、MRR=0.802；离线词法结果为 1.000/1.000。这是小规模、经过开发时检查的回归集，不是独立泛化测评，不代表任意查询准确率。

如本机 Docker 不可用，可单独运行已安装的 `chroma run --path data/.chroma --host 127.0.0.1 --port 8000`。不要在同一端口再启动第二个服务。`build_knowledge_index.py` 会重建配置指定的集合，执行前确认集合名，不指向其他项目的数据。

## 数据层次

`docs/pdf/` 保存原始资料，不作为运行时向量库直接读取。

`data/knowledge/source_manifest.yaml` 记录来源、处理方式、选择理由和页码范围。

`data/knowledge/source_chunks.jsonl` 保存可追溯原文切片。所有新切片默认为 `pending_review`，人工检查后才能改为 `approved`。

`data/knowledge/knowledge_cards.jsonl` 保存结构化设计规则。只有 `review_status=approved` 的卡片允许进入生产向量索引。

`data/knowledge/retrieval_cases.json` 保存固定检索案例，用来计算 Recall@3 和 MRR。

## 两份 PDF 的处理边界

以下是原项目本地资料的历史处理策略；当前公开副本的 source manifest 不包含这两份 PDF，不能直接运行旧 source-id 的导入命令。需要自行提供有权使用的文件，补充来源登记和精选页码后再处理。

### qinghua.pdf

该文件具有可提取文本层。先提取页面文本并生成待审核切片，再筛选与以下主题直接相关的内容：

- AIGC 海报生成。
- 提示词调整。
- 生成问题诊断。
- 迭代优化。

纯软件按钮说明、与海报无关的工具介绍和重复案例步骤不进入批准知识。

### lai.pdf

该文件共 291 页，当前没有可用文本层。禁止默认全书 OCR。

必须先把人工确认的页码写入 `source_manifest.yaml` 的 `selected_pages`，将来源状态改为 `selected`，然后才能调用精选 OCR 管线。计划筛选主题包括视觉层级、构图、网格、对齐、字体、色彩、留白和信息密度。

## 本地补回 PDF 后的命令示例

```powershell
.\.venv\Scripts\python.exe scripts\inventory_pdfs.py
.\.venv\Scripts\python.exe scripts\ingest_knowledge.py --source-id qinghua-aigc-poster --dry-run
.\.venv\Scripts\python.exe scripts\ingest_knowledge.py --source-id qinghua-aigc-poster
.\.venv\Scripts\python.exe scripts\validate_knowledge.py
```

不要在没有页码清单的情况下为 `lai-poster-design` 执行 OCR。
