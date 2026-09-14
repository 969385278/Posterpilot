# 《梦红楼》淡彩人物画版：AI 视觉迭代

## 设计方向

根据用户提供的古画风格参考，采用米色旧绢纸质感、细线人物、赭红淡彩、少量枝石与留白。主角为一位修长的古装人物，画面不再采用厚重油画或大面积园林景色。标题沿用毛笔行书。

| 初版（淡彩人物画） | 迭代版（信息排版） |
|---|---|
| ![梦红楼淡彩人物画初版](assets/menghonglou-ink-initial.png) | ![梦红楼淡彩人物画排版迭代版](assets/menghonglou-ink-optimized.png) |

## 来源与边界

本组图片由 Codex 内置 imagegen 制作。第一次以用户提供的图片仅作风格参考，生成新的海报构图；第二次仅以本组初版作为编辑输入，调整左下角活动信息。输入链为“用户风格参考 → 淡彩初版 → 排版迭代版”，不是从油画版本继续编辑。

参考图的作者、出处及许可尚未核实。仓库不收录、不嵌入参考图原文件，也不据此认定其属于公有领域；本说明不作版权无风险保证。公开的是本次生成的海报和实际提示词。

两图均非 PosterPilot 工作流产物，未调用项目的 Agent、RAG、渲染器或评测服务，不作为自动优化或分数提升证据。活动信息为虚构示例；书法文字属于图像像素，不是字体文件。

## 迭代内容

保留人物、淡彩配色及书法标题，将日期与时间分行，适度放大活动信息并调整间距。生成式编辑不保证细节或像素完全一致；这里记录的是人工指定的设计目标及目视观察，没有进行量化评测。

## 初版提示词

输入图片角色：用户提供的风格参考图，仅作风格参照，不是需要直接复刻的编辑目标。

```text
Use case: ads-marketing.
Input image 1: STYLE REFERENCE ONLY supplied by the user. Do not reproduce this image or its exact composition. Create a NEW original finished portrait 3:4 Chinese theatre poster titled "梦红楼", matching the reference's antique Chinese painted-silk aesthetic.
STYLE TO FOLLOW VERY CLOSELY: warm pale parchment/aged silk ground, fine dark flowing ink outlines, slender elegant classical Chinese figures, flat and translucent pale mineral pigments, muted cinnabar/ochre/rose, grey-violet rock washes, dry ink on a few twisting bare branches, ethereal pale ground mist. The feel of a delicate old Chinese figure-painting album leaf, NOT Western oil painting and NOT realistic cinematic fantasy. Flat pictorial depth, graceful linework, quiet restrained color, lightly worn silk texture; no raised impasto, glossy skin, photographic lighting, modern fashion illustration, anime or 3D.
SUBJECT: ONE prominent fictional Chinese literary heroine evoking the poetic mood of Dream of the Red Chamber, in an ivory robe with fine dusty-red borders and spare floral pattern, long flowing slender silhouette, black hair in a restrained updo. She stands slightly turned, face visible in delicate three-quarter view, eyes gently lowered, hands composed in front within her sleeves. She occupies the center-right and roughly two-thirds of the image height so she is the unmistakable focal subject. The figure must be noticeably larger and more prominent than either small figure in the reference. Do not copy either reference figure's exact face, costume or pose. No second person, no portrait of a real actor.
COMPOSITION: lots of breathable warm rice-paper empty space, no filled-in garden scene. A small expressive ochre/ink rock mass near the bottom and ONE slender bare branch entering from the outer edge may frame the figure lightly. Branches and rocks occupy only a small portion of the image and never dominate the person. No giant tree trunk, no pavilion, architecture, moon, pond, mountain vista, dense trees or flower borders. The subtle paper ground continues edge to edge behind text; no boxed footer or header.
LETTERING: dark warm ink custom Chinese brush calligraphy. Three large beautiful 行书 characters 梦 红 楼 stacked vertically at upper-left, balanced against the standing figure, with varied brush pressure and subtle dry-brush edges. Not rigid font shapes. Event type and poetic line in restrained handwritten 行楷 under the title; initial event information in a modest compact handwritten block at lower-left. All Chinese must be accurate. No Songti, Heiti, generic sans-serif, decorative seals or fake artist signatures.
EXACT VISIBLE COPY, each phrase once:
"梦红楼"
"红楼主题戏剧夜"
"一入红楼，万般皆梦"
"2026年10月16日 19:00"
"大学生活动中心剧场"
"主办：校园戏剧社"
No extra text, logos, watermark, QR, frame, ratings, before/after labels or UI. Produce the poster artwork itself, not a photo of an old painting or a scroll mockup. Make a sincere polished first design, not an intentionally poor before example.
```

## 迭代提示词

输入：`assets/menghonglou-ink-initial.png`，未再次传入用户原始参考图。

```text
Use case: text-localization.
Input image 1 is the EDIT TARGET: the initial 梦红楼 antique Chinese figure-painting poster. Produce one refined second version of the SAME poster, same portrait proportions.
Keep unchanged: the one slender full-length heroine, her face, pose, hair, robe shape and patterns, fine ink contour lines, the pale parchment background, restrained branches and small rocks, all pigment colors, and the large vertical calligraphy 梦红楼 with its cinnabar middle character. Keep the event subtitle and poetic line as they are. Absolutely no oil-painting texture, new scenery, extra people, realistic camera effects or new decorations.
Make ONLY a measured change to the lower-left event information layout. Remove the old small three-line date/location/organizer block. Replace it with a comfortably larger four-line block slightly higher in the same left-side paper space, remaining wholly to the left of the robe and rocks. Use dark warm ink handwritten 行楷. Increase date and venue roughly 25-30 percent, split date and time into separate lines to fit without colliding with the subject; keep organizer smaller. Add a little more vertical breathing room between lines. Do not move the information to another corner, do not enlarge it so much that it competes with the character or title, and do not add boxes, rules, badges, seals or any colored panel. Preserve the pale paper exactly behind it; this is a quiet antique art poster.
The complete exact visible copy is:
"梦红楼"
"红楼主题戏剧夜"
"一入红楼，万般皆梦"
"2026年10月16日"
"19:00"
"大学生活动中心剧场"
"主办：校园戏剧社"
Each phrase once, no extra copy. No Songti, Heiti, sans-serif fonts. No watermark, logo, QR, score, before/after label, UI or surrounding frame. The output must clearly be an information-hierarchy refinement of the supplied image, not a different artwork.
```
