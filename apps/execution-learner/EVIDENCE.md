# 第一章：步骤、源码和证据

业务版本：`6e7e8d3645d46126b5a466d7a486ba2b1f7d38b0`。

采集时间：`2026-09-19T15:49:03.081823+00:00`（北京时间 2026-09-19 23:49）。业务源码无本地修改。新文件仅在 `apps/execution-learner/` 内；旧学习器与其他已有未跟踪文件保留。

所有下文的 `record` 指向 `public/case/record.json`。每个源码引用有相对仓库的真实路径、符号、起止行、完整函数文本、整个文件 SHA-256。采集器自身 SHA-256 在 `record.collector`。完整依赖版本在锁文件和 `record.versions`。

## 证据选择

检查过现有演示文档、产物与检查点：`docs/demo/golden-demo-red-mansion.md` 保留图片和总结，但不足以复原每一步输入输出；`data/runs/readme-photography-20260914` 只有初版相关资料，当前 SQLite 也没有该案例的完整修改链路。因此没有把历史摘要补造成逐步运行记录。

选择当前 `apps/api/tests/agent/test_hitl_executor.py:72–104` 的受约束修改流程，使用已有 `DesignAndReactProvider`、`BothStageRetriever` 和 `FakeImageProvider`。案例输入复用 `tests/agent/test_generation_nodes.py:_brief`。测试替身的字面返回不是模型真实输出。

采集器创建第一次执行器，执行初版并停在人审；关闭后以同一 SQLite 创建第二次执行器，核对全部状态相等，再调用真实 `resume`。恢复后的节点记录来自 `aget_state_history`，渲染参数与文字元数据来自真实 renderer 的透明记录包装。

## 逐步对应

30 FPS；0–29 帧为起点。每步 120 帧，第 78 帧开始展示返回值，末帧为讲解停帧。时间分配仅为教学设计。

| ID / 步骤 | 起止帧 / 停帧 | 当前业务源码 | 输入 → 输出证据 |
|---|---|---|---|
| `restore` 恢复原任务 | 30–149 / 149 | `apps/api/app/agent/executor.py:64–87` `LangGraphAgentExecutor.resume`；`:121–122` `_config` | `record.initial → record.restored` 全状态相等；`record.decision` 为恢复参数；采集器实际新建第二个执行器 |
| `feedback` 接收意见 | 150–269 / 269 | `apps/api/app/agent/nodes/human_review.py:13–55` `human_review` | `record.restored → record.history[0]`；意见、轮次与起始布局写入 |
| `choose-tool` 选择工具 | 270–389 / 389 | `apps/api/app/agent/nodes/react_decide.py:8–56` `react_decide` | `history[0] → history[1]`；`providerCalls[1]` 保存完整请求消息与替身响应 |
| `execute-tool` 校验和修改 | 390–509 / 509 | `apps/api/app/agent/nodes/execute_react_tool.py:8–66`；`tools/react_tools.py:43–129`；`poster/action_executor.py:18–61` | `history[1] → history[2]`；`tool_traces[0]` 的参数、success、Observation；layout 与工具计数变化 |
| `finish-loop` 结束循环 | 510–629 / 629 | `apps/api/app/agent/nodes/react_decide.py:8–56` | `history[2] → history[3]`；`providerCalls[2]` 中包含成功 Observation，返回 finish_round |
| `render` 渲染结果 | 630–749 / 749 | `apps/api/app/agent/nodes/complete_round.py:14–59` `render_round` | `history[3] → history[4]`；`renderCalls` 中输出路径以 `poster_round_1.png` 结束的调用；实际 PNG 和文字元数据 |
| `evaluate` 复评 | 750–869 / 869 | `apps/api/app/agent/nodes/evaluate.py:68–98` `evaluate_optimized` | `history[4] → history[5]`；新报告、analysis_current、goal_verification |
| `save-round` 保存轮次 | 870–989 / 989 | `apps/api/app/agent/nodes/complete_round.py:62–101` `complete_round` | `history[5] → history[6]`；round_snapshots 从 0 到 1 |
| `review` 候选与再次中断 | 990–1109 / 1109 | `apps/api/app/agent/nodes/propose_layouts.py:43–115`；`nodes/human_review.py:69–136` `build_human_checkpoint` 与 `:15–17` | `history[6] → history[7]`；`record.final.interrupts` 和 `record.outcome.status=waiting_for_human` |

第 1 步组合展示采集到的恢复操作与 resume 源码。没有逐行跟踪 `resume` 内部局部变量，不能将动画箭头当成每一行被探针记录。第 9 步包含确实运行的候选节点，没有省略它或假称自动选中了某个候选。

工具执行内部引用：`apps/api/app/poster/action_validator.py:24–56` `_validate_action`，`:59–72` `_require_number`；`apps/api/app/schemas/layout.py:35–52` `LayoutElement`。输入 106 在成功轨迹中。每一层校验的独立返回值未采集；调用关系根据冻结源码。

## 初始与结果

初始状态：`record.initial.values`，等待 `human_review`，布局中 title.font_size=88，实际文字元数据 actual_font_size=88。初版生成细节不在本章。

工具后：`record.history[2].values.layout.elements[0].font_size=106`，但实际文字记录还是 88，此时尚未重新渲染。这一差别是页面刻意保留的学习重点。

渲染后：`record.history[4].values.rendered_text_facts` 标题 actual_font_size=106。

主视觉复用证据：

- `record.backgroundEvidence` 前后 SHA-256 相同，图片提供者调用数为 1 → 1。
- `main_visual_path` 和 `background_treatment` 在本轮保持相同。
- 实际渲染参数使用相同主视觉路径；图片路径是文件引用，不是对象里包含整张图片。
- 本次结构化 controls 为空。因此不能声称自然语言“不要改”自动产生了一个强制锁；本次实际工具只改字，固定主视觉规则和渲染复用提供了可验证结果。

打包的实际产物：

| 文件 | SHA-256 |
|---|---|
| `poster_initial.png` | `2aaeb22b52efefc1fc7d8c780e9add310b4daaf8d0ccf1f441961060dc6c8454` |
| `poster_round_1.png` | `72e6ee70fc20e29c91004c17859c15098266bb5f67800136ba1917b4d1fffc47` |
| `main_visual.png` | `c3ed3abbc0ada43286c09b13e04014e83261d6e91832ce821a8adee88e76c000` |

候选图片在隔离运行中确实被渲染；调用记录和候选元数据已保存，但候选 PNG 未打包，页面标记“未采集”。不展示伪造的候选图。当前视图始终展示该位置已经产出的正式海报。

本地规则总分前后都是 100，可用权重只有 40；vision 与 attention 均为 null/unavailable。goal_verification 是 not_met，活动信息可读性失败。没有真实用户阅读效果、审美结论或模型能力比较。

## 隔离对照

语义对应步骤：`execute-tool`，不是按视频秒数对齐。

保存位置：`record.counterfactual`。两边使用同一份初始布局与 `set_font_size(title, 999)`，没有模型响应参与这个实验。原函数原样调用；另一个函数是在独立命名空间编译的 AST 副本，只移除 `action_executor.py:23` 的 `validate_actions(actions, layout)`。没有改业务文件、没有替换实际生产函数。

原分支抛出 `ActionValidationError: font_size must be between 10 and 240`。副本执行到 `PosterLayout.model_validate` 后抛出 `ValidationError`，由 `LayoutElement.font_size` 的 `le=240` 约束拒绝。两次 caller_layout_before/after 都相等。这里证明了特定输入仍有后续防线，不证明所有输入的多层校验都可互相替代。

## 证据边界与脱敏

- **真实运行记录**：本次没有完整的历史真实用户案例可用，不使用这个标签伪装测试。
- **使用测试替身的执行**：检查点、工具轨迹、渲染文件、实测反例均来自这次隔离执行。
- **基于源码的推断**：函数内部未探测的调用关系、没有实测反例的设计后果。
- **纯教学示意**：动画箭头、模块卡片、帧节奏、初级伪代码。

任务 UUID 替换成 `chapter-task-001`；运行目录替换成 `{CAPTURE_DIR}`；仓库绝对目录替换成 `{REPOSITORY}`。保留合成活动内容，未读取凭证。相对源码路径、哈希和原始行号可用于复核。

未采集：真实模型响应、真实生成背景、逐行 Python 中间变量、真实执行耗时、前端/SSE 通知、真实用户验收。没有 DesignHub 或其他规划功能被放入调用链。
