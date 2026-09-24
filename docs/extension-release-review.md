# 文字扩展发布审查材料

更新时间：2026-09-24。状态：用户在本对话选择 A，批准两项本地启用；两个工具均已 published、revision=1。批准不代表认可效果指标。

| 工具 | 实际行为 | 参数与限制 |
| --- | --- | --- |
| set_text_opacity | 设置已有文字元素的不透明度，Pillow 实际像素合成会消费该值 | 1–3 个不重复文字 ID；opacity 为 0.3–1；不修改事实、主视觉、位置或字体；typography 锁定可阻止执行 |
| align_text_group | 将已有文字框左边、中心或右边对齐到另一个已有文字框 | 1–3 个不重复目标；参考不能同时是目标；保留纵坐标与宽高；拒绝出界；position 锁定可阻止执行 |

对齐指文字框，不保证实际字形视觉边缘相同。已有 modify_layout 也能表达对齐，不应将这个扩展包装成此前完全不具备的新能力。透明度和位置设置成功后仍须渲染并验收可读性，不能保证总分或审美提升。

实现：apps/api/app/agent/tools/extensions.py。严格参数：apps/api/app/schemas/tool_release.py。生产入口：apps/api/app/agent/tools/react_tools.py，每次执行前检查发布授权。测试覆盖实际透明像素变化、三种对齐、原始布局不变、无效/非文字目标、锁定和出界拒绝。

## 当前门禁证据

| 工具 | 报告 ID | 结果 |
| --- | --- | --- |
| set_text_opacity | 492e62d7-e6da-415f-8c27-eabe6b211200 | 124 passed，0 failures，0 skipped |
| align_text_group | 709f1361-9918-46bd-be9b-3f68929deff1 | 124 passed，0 failures，0 skipped |

共同代码指纹：acdd0ef04add534b21a07b94f79576e23bed06b1692c948e474ae1b760da1184。

原始报告、JUnit 和日志在 data/tool-harness/<报告 ID>/；报告快照在 work/completion-audit/current-extension-gates.json。两份报告均确认 code_unchanged=true。124 项是共享回归集合，不是两个工具各有 124 个独立业务样本。

## 发布前后边界

- 人工审核须明确决定发布哪些工具，并留下真实审核人及备注；不把自动测试通过填成用户批准。
- 发布时运行进程必须加载当前代码。若代码、测试、模板、字体或相关依赖变化，当前报告失效，需重新验证；若 API 加载旧代码，应在无在途任务时重启。
- 发布后新增工具进入 ReAct 目录；调用仍受 Schema、文字目标、画布边界、锁定和三步工具预算约束。
- 发布后应执行真实透明度/对齐请求并记录验收，不能由门禁直接推断真实模型使用效果。撤回后阻止新调用，历史产物与审计保留。
- 用户选择 A 后已执行发布；审核记录见 work/completion-audit/user-approved-extension-releases.json。确认无在途任务后重启 API，加载当前代码。

## 发布后真实验收

- 使用真实 DeepSeek、生产发布授权和固定输入执行两项开发任务配对实验；每组最多一轮、三次工具调用。证据目录：work/completion-audit/published-capabilities/capabilities-0c8c22d1029c47fc9269676e26028861。
- 模型实际调用 set_text_opacity，将标题透明度设为 0.8，执行成功，全部目标检查通过。
- 模型实际调用 align_text_group，将 event_info 文字框右边对齐 title，执行成功；整体目标未通过，因活动信息可读性为 1.339:1，低于 3:1 阈值。保留失败结果。
- 基础工具组通过 0/2，扩展组通过 1/2；无运行错误、无上下文或目录漂移、代码与数据未变化。仅为开发样本的规则验收，effect_claim_supported=false，不支持独立业务收益或简历数字。
- 在正式 Harness 数据库的隔离副本中验证撤回：两工具撤回后均从目录消失，再次调用返回 tool_not_published；正式发布状态未改变。证据：work/completion-audit/withdrawal-check-2b3a0b24523f41ad83b49393d2fc6e47/verification.json。
