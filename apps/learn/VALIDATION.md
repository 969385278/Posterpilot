# 学习台验收记录

日期：2026-09-19。检查范围为新增的独立学习应用，没有修改或重新验收 PosterPilot 生产业务。

## 自动检查

- 13 项 Python 检查：课程树和引用、源码符号、所有回放行号及状态连续性、异常场景差异、真实函数结果、缺失信号与零分、移除保护的对照、行号与源码一致性、输入边界、禁用网络下的实验、HTTP 页面与接口、跨站/越界拒绝。
- 画布改版后通过 12 组浏览器验收：单画布与相邻段落、从画布逐层进入、伪代码键盘选择和源码、折叠小题及进度保存、搜索和规划标记、39 节课程逐个检查、路径和词典、播放/单步/人工暂停、场景输入和来源追溯、真实调用/返回和两次结果对比、五项实验及不同屏幕布局、无浏览器运行错误。桌面检查 1440×900 和 1920×1080，窄屏检查 390×844。
- 截图和浏览器检查结果写入 `.runtime/qa/`；该目录不提交。

## 完整流程图独立验收

使用 Archify skill 生成。结构验证、浏览器检查与图片目视复核是独立结论。

```text
diagram_type: workflow
output: F:/workspace/posterpilot/apps/learn/web/flow-overview.html
specification_sha256: 093a60725f8f786600b5d7b6866999a01c98fbd8b733f756c88f822aabd19422
artifact_sha256: ae21c4c90661aa113f31a5844a7b95dcbefff58cc20f07bb2ea8e5d1e21d8469
validation: 9/9 showcase, 0 errors, 0 warnings
browser_evidence: passed
visual_review: passed
correction_rounds: 0
```

自动浏览器检查覆盖 1440×900、1600×1000、1920×1080、2048×1320；检查了页面容纳情况，捕获小/大两端的浅色和深色图。已目视复核 2048×1320 浅色和 1440×900 深色图片的布局、节点文字与连线。收据为 `.runtime/archify-visual-check/flow-overview.visual-check.json`（本地验收产物，不随Git发布），收据中的 `visualReview: pending` 是工具默认值，目视复核结果单独记录在这里。

## 明确的限制

本验收不证明生成海报质量提升，不证明 DesignHub 已实现，不证明完整生产流程已进行真实逐行调试。课程是人工整理的第一版；后续业务代码改变时仍需维护课程。无需外部模型调用，本次学习台开发未产生模型服务调用费用。
