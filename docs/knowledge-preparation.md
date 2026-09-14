# PosterPilot 知识准备说明

## 数据层次

`docs/pdf/` 保存原始资料，不作为运行时向量库直接读取。

`data/knowledge/source_manifest.yaml` 记录来源、处理方式、选择理由和页码范围。

`data/knowledge/source_chunks.jsonl` 保存可追溯原文切片。所有新切片默认为 `pending_review`，人工检查后才能改为 `approved`。

`data/knowledge/knowledge_cards.jsonl` 保存结构化设计规则。只有 `review_status=approved` 的卡片允许进入生产向量索引。

`data/knowledge/retrieval_cases.json` 保存固定检索案例，用来计算 Recall@3 和 MRR。

## 两份 PDF 的处理边界

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

## 常用命令

```powershell
.\.venv\Scripts\python.exe scripts\inventory_pdfs.py
.\.venv\Scripts\python.exe scripts\ingest_knowledge.py --source-id qinghua-aigc-poster --dry-run
.\.venv\Scripts\python.exe scripts\ingest_knowledge.py --source-id qinghua-aigc-poster
.\.venv\Scripts\python.exe scripts\validate_knowledge.py
```

不要在没有页码清单的情况下为 `lai-poster-design` 执行 OCR。
