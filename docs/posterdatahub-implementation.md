# PosterPilot + PosterHub 实施与验收

日期：2026-09-20。状态：本次范围已实现并通过功能验收；真实模型效果提升尚未验证。

## 范围

保留活动海报业务和现有生成、确定性排版、评测、HITL、受约束优化。
增加配套的 PosterHub（原开发名 PosterDataHub，案例、反馈、质量管理），共用仓库和后端，拥有独立管理入口。
不实现电商售后、不重写 Agent 引擎、不自动训练模型、不建设多租户数据中台。
仓库内未跟踪的学习工具、旧团队工作台方案和演示脚本保持不变；本次按当前讨论实施。
验证先使用明确标记的离线依赖，不擅自调用付费模型或伪造真实用户反馈。

## 必须完成的闭环

- [x] 生成初版及每轮优化后保存结构化证据（布局、目标、输入意见、动作、评测、版本及图像校验值）。
- [x] 候选案例可从实际任务产物导入，重复导入幂等；数据保留原始来源，不覆盖既有审核。
- [x] 反馈支持接受/拒绝/未明确评价，保留原话；结束任务不等于用户接受。
- [x] 案例可补充标题、风格、问题、适用条件、限制、复用建议与使用授权说明。
- [x] 审核、驳回、撤回、修改重审有版本与记录；只有已批准且授权明确的内容参与新检索。
- [x] 生成及优化可读取相关已批准案例，展示来源/版本；不匹配时走原流程；不直接复制旧活动事实字段。
- [x] 撤回即时影响新检索；历史引用快照仍可追溯；同一任务不引用自己的历史作为独立经验。
- [x] 工作台有案例库、反馈与质量入口，包含加载、错误、空状态和海报前后对照。
- [x] 检索试验支持相同查询的关闭/开启案例对照；测试集不把被测任务本身放入案例库。
- [x] 自动化测试覆盖审核门禁、并发版本冲突、重复导入、撤回、反馈与分数分离、参考与指令边界、真实业务链路。提示注入相关测试只证明消息结构与现有工具约束，不证明任意攻击下模型不会受影响。
- [x] 有可复现的离线端到端演示、前后图、操作说明与诚实的测试结果；无真实效果提升宣称。

## 数据边界

原始任务证据不可编辑。整理后的案例可修改，但修改后必须重新审核。
评测结果仅按现有 compare_reports 比较同条件数据；用户偏好不是普遍设计规则。
生成内容不自动成为设计知识。经验仅作外部参考，不能覆盖当前事实、锁定项和工具权限。
首版是本机单用户工作台，审核为人工确认，不冒充企业账号权限或双人审批。

## 验证证据

2026-09-20 在本机实际执行。由于新仓库尚无 `.venv`，使用已有 `F:/workspace/GazePoster/.venv/Scripts/python.exe` 并显式设置 `PYTHONPATH=F:/workspace/posterpilot/apps/api`，确认测试加载的是当前仓库。可移植安装与运行方式见 [操作指南](posterdatahub-guide.md)。

| 检查 | 实际结果 | 覆盖范围 |
| --- | --- | --- |
| `python -m pytest apps/api/tests -q` | 240 passed，63.60 秒 | 原有生成优化回归及新增数据平台测试 |
| `npm.cmd --prefix apps/web run test` | 18 个测试文件、44 项通过 | 原有界面及工作台交互、审核冲突、标签输入、历史版本 |
| `npm.cmd --prefix apps/web run build` | TypeScript 与 Vite 构建成功 | 前端类型检查与生产打包 |
| 新增 Python 文件的 Ruff 检查 | 通过 | 经验模块、DataHub API/模型/服务/存储、演示、验证脚本与测试 |
| `git diff --check` | 通过 | 已跟踪改动的空白检查 |
| `start_datahub_demo.ps1 -Mode Seed` | 12 项链路检查通过，4 个查询探针通过，8.01 秒 | 真实 API/图/渲染/SQLite，固定离线模型，不调用付费服务 |
| 浏览器操作 | 案例图片、前后对照、撤回、重新发布、检索及来源任务跳转通过 | 本机 API 8793、Web 5193；离线数据 |
| 响应式检查 | 1280×900、390×844 下没有横向溢出 | 宽屏前后图与编辑双栏，窄屏表单单栏 |

端到端报告：`data/datahub-demo/verification.json`。本次报告对应来源任务 `f0b88090-3d05-461d-9782-a6b44273f170`，关闭经验的新任务 `2a1abc3b-5f32-489e-a939-d4fe95125042`，开启经验的新任务 `690f1b27-c234-454e-a486-9f4d65b22325`。
报告中的运行 ID 随重新执行改变，以最新报告为准。浏览器验证将案例 `6ece6018-9f7a-402c-8c45-f2101a0544d4` 从 v5 撤回为 v6，再重新批准为 v7；报告保留脚本执行时的结果，不是对后续编辑状态的实时报告。

### 逐项证据定位

| 验收项 | 权威证据 |
| --- | --- |
| 每轮证据与前后图 | `experience_evidence.py`；集成脚本 `round_evidence_auto_captured`、`actions_and_before_after_preserved`；浏览器图片实际加载 |
| 来源导入与幂等 | `test_capture_is_idempotent_and_never_infers_acceptance`、`test_changed_source_is_not_silently_overwritten`、脚本 `recapture_keeps_review` |
| 明确反馈，不推断接受 | `test_rejected_feedback_is_kept_but_cannot_publish`、脚本 `finish_does_not_infer_acceptance` |
| 案例整理与历史版本 | `test_audit_preserves_old_curated_content_after_edit`；前端标签保存及历史内容展示测试 |
| 审核与并发 | `test_approval_requires_metadata_and_rights`、`test_same_revision_only_one_reviewer_wins`、`test_edit_invalidates_approval_and_stale_review_conflicts` |
| 生成/优化引用与字段隔离 | 脚本 `generation_reference_on_off`、`optimization_receives_references_without_copying_source_title`；`test_published_experience_excludes_old_facts_and_own_run` |
| 撤回与旧快照 | `test_withdrawal_immediate_but_previous_reference_survives`；浏览器撤回后检索只返回另一已发布案例，来源 ID 不再包含被撤回条目 |
| 界面与错误状态 | `DataHubPage.test.tsx`；浏览器确认来源任务可跳转，Agent 控制台显示参考来源、版本及“非采纳证明”提示 |
| 开关对照与隔离 | 脚本三个独立任务、开启 1 条/关闭 0 条、同任务排除及演示来源过滤；前端检索对照测试 |
| 降级与重试 | `test_capture_failure_does_not_fail_poster_and_manual_retry_recovers` 注入存储异常，海报仍等待人工决定，重试后恢复候选记录 |
| 可复现交付 | `start_datahub_demo.ps1` 已实际执行 Seed 模式；API/Web 已运行并经浏览器访问；`posterdatahub-guide.md` 含启动与逐文件职责 |

### 保留的边界与后续验证

- 没有调用付费生图/文本模型，没有采集真实用户反馈。固定决策仅验证流程，不能得出模型采纳经验、改善审美或减少生成费用的结论。
- 第一份离线样例因标题可读性不达标未获发布，失败记录保留。后续调整测试样例的文字颜色，没有放宽审核门禁。
- 四个固定检索探针不是有代表性的行业评测集；首版文本匹配适合小案例库，尚未做大规模检索基准。
- 原始字段不复制不代表人工填写的建议天然无隐私或无恶意内容；仍需审核。当前安全控制不是完整提示注入防御证明。
- 单用户、共享部署边界与未实现能力已在操作指南说明，不将其描述为独立生产微服务或自学习平台。
- 测试有一条现有 Starlette/httpx 弃用警告；离线运行还提示未来 LangGraph 将要求显式注册 checkpoint 类型。当前恢复验证通过，升级依赖时应处理这些兼容性提示。
- 未上传 GitHub，也未修改未跟踪的学习工具、旧工作台方案或其他无关文件。
