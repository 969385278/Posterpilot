# 授权背景素材

本目录用于真实中文排版与工具调整的演示，不替代正式环境的生图 Provider。图像从 Wikimedia Commons 下载，许可依据取得时的 imageinfo 元数据，保留原始来源、作者、下载时间和 SHA256。

| 素材 | 原作者/机构 | 来源 | 使用判断 |
| --- | --- | --- | --- |
| 鸢尾花（10036） | Vincent van Gogh | [原作与许可](https://commons.wikimedia.org/w/index.php?curid=10036) | Public domain；横幅原作转竖版有裁切，油画细节密集，需检查文字背景 |
| 创生之柱去噪版（38165284） | NASA, ESA, and the Hubble Heritage Team (STScI/AURA)；处理说明见来源页 | [原图与许可](https://commons.wikimedia.org/w/index.php?curid=38165284) | Public domain；完整图像，没有旧拼接版的大块黑色缺口 |
| 大提顿与蛇河（118192） | Ansel Adams，美国国家公园署/NARA 来源记录 | [原图与许可](https://commons.wikimedia.org/w/index.php?curid=118192) | Public domain；黑白摄影，竖版裁切仍保留山峰与河流主体 |

旧版创生之柱（129538）有明显未覆盖黑块，不作为背景使用；仅保留文件和来源说明筛选过程。`reviewed_media.json` 是入选与排除清单。来源页标注不是本项目的法律保证，商业使用需复核地区、作者与机构权利边界。

下载的是展示尺寸图片，不是印刷级原始文件。海报渲染包含裁切、背景处理和中文覆盖，活动内容为虚构。中文标题使用项目已有的 SIL OFL 字体，未从外部海报提取字体。

`sources/` 保存来源元数据，`images/` 保存下载字节；`app.showcase.reviewed_media()` 每次载入会校验许可和文件哈希。

重新取得候选（只下载，不代表审核）：

```powershell
python scripts/prepare_case_assets.py --commons --root data/media 10036 38165284 118192 129538
```
