# PosterPilot 交互式代码执行学习器

> 2026-09-25 核查：此目录保留的是此前采集的执行快照，部分生产源码已更新。
> 当前时间线测试8/9通过，源码哈希一致性检查失败；构建通过。
> 因此可作为历史执行案例阅读，不能称为当前版本的完全同步演示。请勿只修改哈希来掩盖差异；
> 更新时需按下文流程重新采集并核对讲解。

浏览器学习网页，使用 React 19.2.7 + TypeScript 6.0.3 + Remotion Player 4.0.526。独立于原应用和 `apps/learn`，不覆盖任何现有入口。第一章为 9 个业务步骤，没有 MP4。

## 打开

本次实际本地地址：**http://127.0.0.1:8891/**。

重新启动时，在 PowerShell 中执行：

```powershell
Set-Location F:\workspace\posterpilot\apps\execution-learner
npm.cmd ci --workspaces=false
npm.cmd run dev
```

已安装依赖时，只需后两行中的 `npm.cmd run dev`。必须先进入此目录，不从仓库根目录安装工作区依赖。8891 被占用时检查是否已有本学习器运行；`--strictPort` 会拒绝偷偷换端口。

生产构建与本地预览：

```powershell
npm.cmd run build
npm.cmd run preview
```

不需要启动 FastAPI、SQLite 服务、DeepGaze、Ollama 或任何模型。页面只读取自身静态目录里的 JSON 和 PNG。案例采集脚本是独立命令，没有接入网页。

## 如何学

- 初次打开停在案例起点，展示真实测试产物与初始状态。
- **下一步**按业务步骤播放，第一次进入恢复任务；结束后停在完整讲解画面。
- **学习模式**中的播放继续到下一个教学停点；**连续模式**中的播放跨越停点。
- 上一步与目录点击直接停在对应步骤末帧。重播本步从本步起始状态重新展示，结束后暂停。
- 进度条可拖动，拖动后暂停。支持 0.5、1、1.5、2、4 倍速。
- 中间对象可以点击，右侧显示同一步的已采集内容。右侧源码、JSON、快照可以展开、选择、复制、滚动。
- “为什么这样设计”展示原因和代价；“没有这项设计会怎样”进入独立对照，并保存原帧。返回主线仍然暂停。
- 空格播放/暂停，左右方向键前后步骤，R 重播。在表单、源码面板或选择文字时不触发这些快捷键。
- 左侧目录可收起，右上滑条可调整检查面板宽度。

教学时间不代表真实执行耗时。暂停只暂停 Remotion 回放，不控制 Python 进程。

## 本章证据与结论

案例意见：**不要改变主视觉，只增强标题**。这是已有集成测试场景的离线重新执行，明确归类为 **使用测试替身的执行**，并非历史真实用户任务。

真实执行：当前 LangGraph、SQLite 检查点、恢复原任务、受约束工具、Pillow 渲染、可用的本地评价逻辑。替身：已有的文本、图片、检索测试提供者。采集过程中禁止外部网络连接，未付费、未改业务源码。

已观察到：标题布局与实际绘制字号均为 88 → 106；工具为 `modify_typography`；背景字节哈希相同，背景处理参数相同，图片提供者调用次数未增加；最终再次等待人工输入。目标检查仍为 `not_met`，因为活动信息可读性未通过；总分 100 仅基于可用权重 40/100，视觉与注意力信号缺失，不能表述为完整质量满分。

唯一实测对照：相同布局、字号 999，只在隔离函数副本中移除第一处动作校验。原函数由 `ActionValidationError` 拒绝，副本仍由最终 Pydantic `ValidationError` 拒绝。两次均未修改调用方布局，没有产生非法海报。其余“没有会怎样”均明确标为源码推断。

完整映射见 [EVIDENCE.md](./EVIDENCE.md)，验证记录见 [VERIFICATION.md](./VERIFICATION.md)。

## 文件分工

```text
public/case/record.json              脱敏记录、检查点、实际参数、冻结源码、反例结果
public/case/*.png                    实际采集的初始/本轮/主视觉图片
scripts/capture_case.py              独立离线采集命令（网页不调用）
src/content.ts                      9 步中文教学文案、源码映射、伪代码
src/timeline.ts                     稳定步骤边界、停帧、进退语义
src/data.ts                         由案例记录和当前帧派生输入输出、差异、产物
src/animation/ExecutionScene.tsx     仅由 Remotion 帧计算的动画
src/player/usePlayback.ts           播放、单步、暂停点、键盘、对照恢复
src/components/Inspector.tsx        可选择/复制的普通网页源码与数据面板
src/components/Comparison.tsx       独立的实测/推断对照
tests/timeline.test.ts              时间轴、证据映射、哈希、回退测试
tests/browser.mjs                   真实 Chromium 中的完整交互验收
```

`case + branch + frame` 决定展示。只有 Remotion 帧驱动回放；检查面板从同一个帧派生。动画移动和调用箭头是教学示意，不是逐行执行日志。起始阶段展示 before，返回阶段展示 after。任何位置跳转都重新计算当前画面，避免未来结果残留。

自动暂停使用 `frameupdate`，检测 `frame >= targetStop`，先撤销目标并暂停，再定位准确停帧。重新继续只选择严格晚于当前帧的下一个停点。手动 seek 先暂停再定位，避免 Player 在播放中 seek 后恢复播放。

## 再次验证

```powershell
npm.cmd test
npm.cmd run build
# 确认本地 8891 预览已运行后：
npm.cmd run test:browser
```

浏览器测试优先使用 Windows 标准位置的 Chrome，也支持环境变量 `CHROME_PATH`。其他机器可以 `npx.cmd playwright install chromium` 后使用 Playwright 自带 Chromium。

本次 backend 依赖在已有 `F:\workspace\GazePoster\.venv` 中，但采集器将**当前仓库** `apps/api` 放到 Python 导入路径第一位；冻结源码与当前仓库哈希均已验证。仅需要重采数据时才独立执行：

```powershell
& F:\workspace\GazePoster\.venv\Scripts\python.exe scripts\capture_case.py
```

该命令会在本工具 `.runtime` 下创建隔离运行目录，并替换本工具的 `public/case` 记录；它不是日常学习的启动步骤。不同字体环境可能改变图片哈希，重新采集后应重新验收。没有相应 Python 依赖时可直接使用随附的已采集数据。

## API 核对

本次使用已安装的 Remotion SaaS/Player、Markup、Interactivity 和相关文档技能；Player 与 Remotion 固定为同一版本 **4.0.526**。API 依据 [官方 Player 文档](https://www.remotion.dev/docs/player/player) 与已安装包 `dist/cjs/Player.d.ts`、`player-methods.d.ts`、`event-emitter.d.ts` 核对。使用 `useCurrentFrame` 和 `interpolate`，没有用 CSS 动画或独立累积计时器改变记录。
