# 开源中文标题字体

本轮从 Google Fonts 官方字体仓库取得6款完整、未修改的中文字体。各自的 OFL.txt 与 METADATA.pb 原样保留；manifest.json 记录固定上游提交、下载时间、原始URL、每个文件的SHA256和字体内部名称。

| 字体 | 页面名称/用途 | 上游目录 |
| --- | --- | --- |
| Ma Shan Zheng | 马善政毛笔体：国风、传统文化 | https://github.com/google/fonts/tree/main/ofl/mashanzheng |
| Long Cang | 龙藏体：疏朗文艺手写 | https://github.com/google/fonts/tree/main/ofl/longcang |
| Zhi Mang Xing | 志莽行书：短标题、连笔行草 | https://github.com/google/fonts/tree/main/ofl/zhimangxing |
| ZCOOL KuaiLe | 站酷快乐体：招新、趣味活动 | https://github.com/google/fonts/tree/main/ofl/zcoolkuaile |
| ZCOOL QingKe HuangYou | 站酷庆科黄油体：窄长圆角标题 | https://github.com/google/fonts/tree/main/ofl/zcoolqingkehuangyou |
| ZCOOL XiaoWei | 站酷小薇体：装饰宋体、展览 | https://github.com/google/fonts/tree/main/ofl/zcoolxiaowei |

## 许可

全部采用 SIL Open Font License 1.1。允许按照许可嵌入和随软件分发，也可用于商业设计；分发字体时保留版权声明和许可，不将字体文件单独出售。字体修改、保留名称等限制以各目录完整OFL.txt为准；字体许可不自动限制由字体生成的海报。没有从参考海报裁字或恢复字体文件。

## 生成规则

- 主标题支持手动选择上述字体或“常规粗体”；正文、时间和地点继续使用原有清晰字体。
- 自动匹配为确定性预设：文化活动→小薇体；社团招新→快乐体；校园讲座→庆科黄油体。不宣称LLM做了字体审美推断。
- 手动选择优先于案例字体；自动模式且用户勾选案例字体气质时，沿用原有案例字体近似映射，不声称提取原字体。
- 字体路径只通过预定义ID映射；新增API不接受任意本地路径。
- 字体缺失或不覆盖当前标题时，整个标题回退到常规粗体，规划事件记录说明，渲染分析记录实际字体。不保证常规字体覆盖所有罕见字或emoji。
- 原有字体锁会比较字体别名和最终字体名称/字号，候选布局沿用当前字体。没有新增任意字形生成、图片文字编辑或复杂艺术效果引擎。
- 字体预览由后端本地字体绘制PNG，最多120个字符；不下载整套字体到浏览器，不请求在线字体CDN。预览只展示字形，不代表最终字号和排版。

## 文件入口与维护

- apps/api/app/poster/font_catalog.py：字体目录、字形覆盖检查、自动/显式选择策略。
- apps/api/app/schemas/brief.py：title_font白名单与默认值。
- apps/api/app/agent/nodes/plan_design.py：案例映射后应用最终标题字体。
- apps/api/app/poster/renderer.py：解析本地字体，记录实际字体；小薇体名称从字体内部Unicode名称表读取，避免FreeType显示问号。
- apps/api/app/api/routes/fonts.py：字体清单与有界预览接口。
- apps/web/src/features/brief/TitleFontPicker.tsx：选择、预览、许可链接与错误提示。
- scripts/prepare_title_fonts.py：按manifest固定提交重取/校验素材，不安装到Windows系统字体目录。
- scripts/preview_title_fonts.py：不调用模型，生成6款字形对比图到outputs/title-fonts。

开发验证包括字体哈希/许可、真实Pillow渲染、字形覆盖、手动选择优先级、模型工作流传递、非法ID/超长预览、前端提交和失败提示。模型依赖使用fixture验证流程，不为这次字体接入额外发起付费生图。
