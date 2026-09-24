# 可复现实验与证据边界

## 检索排序对照

```powershell
.\.venv\Scripts\python.exe scripts/compare_retrieval.py --top-k 5
```

默认读取 `data/knowledge/knowledge_cards.jsonl` 和 `retrieval_cases.json`，调用本机 Ollama
`bge-m3`，在独立目录创建真实 Chroma 索引。不会重建或覆盖正式 Chroma 集合。

每条查询先执行生产环境的审核状态、意图和目标区域过滤，只调用一次向量检索。
纯向量条件使用向量顺序，混合条件通过生产 `KnowledgeRetriever` 对同一批向量结果重排。
两组 top-k、候选范围、相似度下限和嵌入一致；本实验只测重排贡献，不测场景过滤的贡献。

输出目录为 `data/experiments/retrieval-<id>/`：

- `manifest.json`：数据摘要、代码摘要、模型实际权重摘要、依赖版本、控制条件、状态和局限。
- `corpus.json`、`cases.json`：本次实际使用的输入快照。
- `source/`：运行脚本及关键生产模块的代码快照。
- `rows.jsonl`：逐条查询、候选、原始向量分数、词法分数、两种排名、未召回标签和错误。
- `summary.json`：Recall、Hit Rate、MRR 与两组差值；模型或代码变化、查询失败使对照无效。
- `chroma/`：本次独立索引，不共享生产数据。

指标定义：Recall 为召回相关卡片数 / 全部相关卡片数，报告按问题宏平均；Hit Rate 是是否命中
至少一张相关卡片；MRR 是第一张相关卡片名次倒数的平均值。失败查询保留在分母内，不挑选
成功子集。`evaluate_retrieval.py` 同步明确区分这三项指标。

当前 16 条数据是已有开发回归集，不是独立人工标注集。已有查询可能与知识卡检索别名重合，
因此不能用于证明简历中的 100 条独立问题和 76%→88% 提升。未来应另行冻结独立评测输入，
而不是在这些数据上不断调参后称为泛化测试。

## 意图与约束解析

```powershell
.\.venv\Scripts\python.exe scripts/evaluate_intents.py
# 配置真实文本模型后，才运行下面的三种路由条件：
.\.venv\Scripts\python.exe scripts/evaluate_intents.py --live
```

默认使用明确标为开发样例的 `data/evaluation/intent_development.json`（24 条），比较规则分类
与没有模型连接时的完整路由行为。另有 7 条精确约束标注，单独统计，不混入意图准确率。
没有连接真实模型时 `live_comparison_available=false`、调用节省为 null，不伪造回退改善。

`--live` 使用同一个配置模型分别运行低置信度回退和强制全量模型路由；缺少密钥时直接失败。
原始请求、模型输入输出、失败类别、模型调用次数及耗时逐条落盘。预期标签不进入模型输入。
全模型条件使用 direct_llm，直接调用同一文本模型完成分类与解析，不经过规则置信度门槛；
混合条件保留规则分类和低置信度回退。两者共用解析 Schema、事实校验和本地控制约束规则。

输出目录为 `data/experiments/intents-<id>/`，包含数据、路由器和脚本快照、manifest、逐条结果
及 summary。重复运行使用新目录，不能覆盖旧结果。保存的模型交互可能含用户输入，只存本机，
实验目录已由 Git 忽略。

## 画像更新规则对照

```powershell
.\.venv\Scripts\python.exe scripts/evaluate_memory.py
# 配置真实文本模型后，以同一份真实提取结果驱动两种更新条件：
.\.venv\Scripts\python.exe scripts/evaluate_memory.py --live
```

开发数据在 `data/evaluation/memory_development.json`，含 8 组、18 步模拟对话。每步分别记录
原话、会话、候选、模拟用户确认动作、撤销对象和预期画像。预期画像只用于结果比较，不能写入
运行画像，也不会发送给模型。

两组共用经过真实 `UserMemoryService.extract` Schema 和原话校验的候选，模型仅调用一次。
`direct_overwrite` 将每条候选写入画像；保留用户隔离、场景优先级和显式撤销支持，因此不会通过
故意移除这些能力夸大差异。`governed` 使用真实 SQLite 记忆服务，只让确认后的明确偏好进入画像，
同时执行事件修订、撤销和来源追踪。

默认模式 `frozen_candidate_replay` 使用数据里的固定候选回复，测更新规则，不测模型提取质量。
`--live` 则调用实际配置的提取模型，固定候选不参与模型响应生成；缺少密钥直接失败。二者都保留
模型交互、逐步画像、原话来源及 SQLite 审计。一个消息返回同一偏好键/场景的多项冲突候选会使
该次对照无效，不静默选一项。
模拟确认必须精确匹配实际候选的值、原话、场景和 explicit 类型；匹配失败会记录
`unmatched_confirmations` 并使治理对照无效。不能把提取差异造成的未确认，归因于治理效果，
也不能按预期标签自动确认语义相近的候选。

输出在 `data/experiments/memory-<id>/`，包括数据/代码快照、manifest、summary 以及
`execution/rows.jsonl` 和分组数据库。指标分别统计错误步骤和至少一次错误的会话组；运行错误
保留在分母并使对照无效。此开发集不支持简历所述 60 组真实对话、12→3 的主张。

## 决策卡固定输入对照

```powershell
.\.venv\Scripts\python.exe scripts/evaluate_decisions.py --dataset data/evaluation/decision_development.json --live
```

此命令需要真实文本模型配置，不会用 demo provider 顶替。缺少密钥时保留失败 manifest 并退出。
随附单条输入是 Agent 编写的模板/仓库图片开发样例，source_run_id 是明确标注的模拟标识，
没有预设正确动作或效果标签。它不是独立预留任务，也不支持简历的 40 个任务、24→32 或 2.8→2.1。

两组共用同一初始 design_spec、图片、用户画像、普通历史案例、工具目录和模型；只切换决策卡。
使用生产 react_decide / execute_react_tool / render_round / evaluate_optimized，最多 3 轮，
每轮最多 3 次工具调用。按任务交替执行组别顺序；同一知识检索请求在两组共用首次真实响应，
响应保留原始证据。评测固定为规则与像素/排版测量，不接视觉和注意力服务，不据此声称多模态效果。

首个实际工具调用后复制状态进行渲染验收，不把额外测量反馈给 Agent。后续每轮仍依生产逻辑
统一渲染；实验结果额外以最初海报为基准检查原始目标，并要求没有 high/critical 版式问题。
模型提前结束且没有调用工具时，首动作结果为 null，计为未通过而非从分母剔除。
未解决或报错任务全部保留；平均轮次明确只针对成功任务，同时报告成功分母与未解决数量。

输出 `data/experiments/decisions-<id>/` 包含输入/图片、源代码/字体/知识文件快照、模型标识、
工具目录、来源案例和决策卡快照、每次模型输入输出、首动作渲染、逐轮证据及 summary。
完成后检查代码、数据、工具目录和检索上下文是否漂移。没有检索到任何卡时不算有效卡对照。
拒绝将评测输入来源任务同时用作已审核普通经验或决策卡来源。单次对照仍不控制模型采样方差、
模型后端版本变化或证明数据独立性，`effect_claim_supported` 保持 false。

真实新任务的 `experience_round_0.json` 现保存完整 design_spec。可先准备 controls JSON，例如：

```json
{"adjustments":[{"trait":"title_emphasis","direction":"strengthen","strength":0.1}],"locks":[]}
```

然后导出固定任务，路径替换为实际任务和文件：

```powershell
.\.venv\Scripts\python.exe scripts/export_decision_task.py --run-directory data/runs/<run-id> --id title-case --instruction "增强标题" --controls work/controls.json --output work/decision-task.json
.\.venv\Scripts\python.exe scripts/evaluate_decisions.py --dataset work/decision-task.json --live
```

导出不覆盖已有文件；缺少完整设计规格的旧任务明确报错，不从渲染图猜测参数。
多任务集可以汇总导出文件的 tasks 数组，每个 id 必须唯一。原始任务不要先作为训练经验发布。

精确的工具能力需求也可写在 controls 的 element_goals 中，例如：

```json
{"element_goals":[{"kind":"opacity","element_id":"title","opacity":0.8},{"kind":"alignment","element_id":"event_info","reference_id":"title","edge":"right"}]}
```

不透明度 1 为完全不透明，文字框对齐不代表字形边缘对齐。上述目标仍须通过文字可读性、区域
及锁定检查；不是参数写入成功就算验收通过。opacity 工具仍需真实回归和审核发布，对齐也可以
由已有的 modify_layout 完成，不能把工具名称变多等同于可表达能力增长。

## 已发布工具的能力对照

```powershell
.\.venv\Scripts\python.exe scripts/evaluate_capabilities.py --dataset data/evaluation/capability_development.json --added-tools set_text_opacity align_text_group --live
```

此命令不会发布工具。先在工具治理页面对当前代码运行回归、完成实现审查并发布指定工具；
命令会再次检查实际发布授权，保存发布记录和对应的真实门禁报告。没有密钥、工具未发布、
已撤回或代码已变化时明确失败，不以本地替代执行伪造上线结果。

两组固定初始图片、布局、精确目标、普通历史经验、模型和调用预算。决策卡在两组均关闭，
只切换工具目录：base_tools 只允许内置工具，extended_tools 增加命令中指定且已发布的工具。
限制同时作用于提示词和实际执行：模型猜出新增工具名称也不能在基线组调用；实验组仍通过
真实注册表检查当前发布状态。未经指定的其他已发布扩展也不进入本次对照。

输出为 `data/experiments/capabilities-<id>/`，沿用决策卡实验的完整输入/模型/渲染证据。
额外保留每组工具目录、发布版本、实现指纹和服务器回归报告。统计两组各自的成功、失败及
未解决数量，同时报告新增解决、退化、可比较任务对、错误任务对，以及新增解决中确实调用了
新增工具且具有发布证据的数量。报错对不会被标成能力提升，仍保留在总任务分母及错误对统计中。

随附两条是人工构造的开发输入，没有预设输出，不是简历所称 12 个预留缺口任务。
尤其 align_text_group 的结果可由 modify_layout 表达；模型在一次对照中的成功差异不能证明
新增可表达能力，也不能证明因果改善。测试使用同一个固定 provider 验证两组隔离，不发布
“新工具组获胜”的模拟业务数据；`effect_claim_supported` 保持 false。

## 当前仍未完成的实验

记忆真实提取与独立会话评测、决策卡真实模型对照运行、能力缺口独立任务和真实模型对照仍需继续。
不能用开发回归替代这些指标。实时生图、视觉评价和真实文本模型联调仍需有效配置。
Jev 名称对应的分类器尚未确认，当前规则实现没有更名冒充 Jev。
