# 本地实验记录导航

这些目录位于项目根目录下的 `work/`，保留在实验机器上，并由 Git 忽略。
从 GitHub 新克隆仓库不会自动取得原始模型响应、数据库、图片及冻结快照；仓库提供实现、
开发样例和可复现实验说明，不声称已经公开全部实验数据。

|方向|本地目录（相对项目根目录）|先读什么|
|---|---|---|
|200条意图分类|`work/interview-evaluation/runs/routing-200-df5183558fff44708160736836f3cdca/`|`summary.json`、`dataset.json`、`rows.jsonl`|
|100题知识召回|`work/interview-evaluation/runs/retrieval-3eb12575bbc840bf9b1db5f10a4dc47e/`|`summary.json`、`cases.json`、`rows.jsonl`|
|定向编辑回归|`work/final-validation/`|`最终评测报告.md`、`任务明细.md`、`results/`|
|偏好记忆对照|`work/memory-rag-ablation-20260925-corrected/`|`实验报告.md`、`逐题对照.md`、`results/`|
|决策卡替换案例的工具选择实验|`work/tool-choice-rag-vs-cards-20260925/`|`实验报告.md`、`verification.json`、`results/`|
|早期决策卡叠加实验及治理检查|`work/decision-card-ablation-20260925/`|`实验报告.md`、`governance-*.json`|
|停止格式根因诊断|`work/decision-card-diagnosis-20260925/`|`summary.json`、`replay-results.json`|
|Jev分流推演|`work/jev-routing-simulation-20260925/`|`模拟对话与路由估算.md`、`messages.json`|

## 证据口径

- 先看协议、题目与标签，再看实际响应与判分，最后复算汇总。版本哈希证明输入/源码一致，不能证明标签无误。
- 实验是自建模拟任务，重复运行不是新增独立用户，功能测试通过不等于真实用户效果。
- 记忆实验使用已确认历史；不覆盖自动提取偏好和完整海报生成。没有 `-corrected` 的首轮因知识上下文为空而无效，保留供审计，不用于效果结论。
- 决策卡替换案例的提速来自诊断条件，生产仍追加案例与卡片；不能宣称正式全流程已提速。
- Jev未接入，分流比例来自人工标注推演；三轮排版修改节省75%生图费用来自4次与1次调用的同价假设，而非账单对照。
- 失败样例、负结果和作废轮次保留，不属于待删除垃圾。不得只保留成功结果。

开发集与运行方法见 [可复现实验](reproducible-evaluations.md) 和 [评测协议](interview-evaluation-protocol.md)。
运行真实模型评测可能产生费用；阅读已有 JSON/Markdown 不会调用模型。部分验证脚本会重写汇总，执行前检查脚本。
