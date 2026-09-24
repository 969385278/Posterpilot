"""Hand-authored, code-grounded curriculum. Planned work is always labelled."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NODES = []


def lesson(id, parent, title, summary, actor, need, because, without, mechanism,
           code, inputs, outputs, source=None, symbol=None, status="implemented",
           alternative="可以更换实现方式；先保留业务要求，再决定是否需要框架。",
           quiz=None, lab=None, terms=()):
    NODES.append(dict(id=id, parent=parent, title=title, summary=summary,
        actor=actor, status=status, need=need, because=because, without=without,
        mechanism=mechanism, alternative=alternative,
        code=[dict(text=x[0], note=x[1]) for x in code], inputs=inputs,
        outputs=outputs, source=source, symbol=symbol, quiz=quiz, lab=lab, terms=terms))


lesson("system", None, "一张海报，怎样从需求走到结果？",
    "从整个项目开始，再进入模块、步骤与基础逻辑。每一层都能看到输入、输出，以及这一步为什么存在。",
    "程序 + 模型 + 用户", "业务主线", "把制作、检查与修改接起来，才能交付用户需要的结果。",
    "只有一次生图调用时，活动文字、修改过程和用户确认都缺少管理。",
    "程序负责顺序与约束，模型提供方案和工具选择，用户决定修改目标和是否结束。",
    [("brief = receive_request()", "接收标题、时间、地点等需求。"),
     ("poster, report = create_first_poster(brief)", "进入生成模块，返回海报与评测。"),
     ("while user_wants_changes():", "用户决定是否继续；实际项目还有轮数上限。"),
     ("    poster, report = improve_poster(poster)", "Agent 选择工具，程序校验并执行。"),
     ("save_result(poster, report)", "保存最终产物及每轮记录。")],
    [{"name":"brief", "value":{"title":"春日摄影展", "event_time":"周五 18:00"}, "from":"intake"}],
    [{"name":"result", "value":{"poster":"海报文件", "rounds":"修改记录"}, "to":"artifacts"}],
    "apps/api/app/agent/graph.py", "create_hitl_react_graph", terms=("Agent", "state"),
    quiz=("谁决定要不要继续修改？", ["模型永远自己决定", "用户决定，程序限制最大轮数", "向量数据库决定"], 1, "人工反馈决定业务方向，程序保留执行边界。"))

lesson("intake", "system", "接收与校验需求", "把表单变成结构化需求，并创建一个可以追踪的任务。",
    "程序", "核心必需", "后续步骤必须拿到格式明确的活动信息。", "空标题或不合法尺寸可能进入后端，错误会拖到渲染时才暴露。",
    "先校验，再创建任务；每个任务拥有独立编号和状态。",
    [("brief = validate(form)", "校验字段；校验不等于模型理解。"), ("run = create_run(brief)", "保存需求，分配任务编号。"), ("schedule(run.id)", "交给后台执行，让页面先收到编号。"), ("return run.id", "页面用编号查询进度。")],
    [{"name":"form", "value":{"title":"春日摄影展", "canvas":{"width":1080,"height":1440}}, "from":"form"}],
    [{"name":"run", "value":{"id":"教学任务-001", "status":"queued"}, "to":"production"}],
    "apps/api/app/services/run_service.py", "RunService.create", terms=("API", "Schema"))

lesson("brief", "intake", "哪些输入合法？", "检查标题与画布，保留没有填写的可选信息。", "程序", "核心必需",
    "模型和渲染器需要遵守一致的数据约定。", "横版画布可能进入竖版模板；模型可能替用户补写未提供的地点。",
    "字段类型、范围和跨字段条件在进入流程前统一检查；空的可选字段保持为空。",
    [("if not title.strip():", "标题不能只有空格。"), ("    reject('标题不能为空')", "拒绝当前需求。"), ("if height <= width:", "当前模板只支持竖版。"), ("    reject('请使用竖版画布')", "阻止不兼容尺寸。"), ("return brief", "校验通过后继续；可选信息不凭空补全。")],
    [{"name":"title / canvas", "value":{"title":"摄影展", "width":1080,"height":1440}, "from":"form"}],
    [{"name":"PosterBrief", "value":{"title":"摄影展", "location":""}, "to":"planning"}],
    "apps/api/app/schemas/brief.py", "PosterBrief", terms=("Schema",),
    quiz=("没有填写活动地点时，程序应该怎么做？", ["让模型猜一个地点", "保持为空，不虚构活动事实", "一律填待定"], 1, "当前项目允许不提供地点，空值不是让模型编造的许可。"))

lesson("production", "system", "生成初版海报", "按固定顺序检索、规划、生成、排版与评测。", "程序安排，模型参与", "核心必需",
    "活动信息、视觉内容和版式需要共同组成一张海报。", "仅有背景图片时，中文内容和最终可读性还没有处理。",
    "把不确定的模型输出与确定的排版分开；每个阶段使用前一步的结果。",
    [("knowledge = retrieve(brief)", "找到可参考的设计知识。"), ("design = plan(brief, knowledge)", "模型提出受限的设计方案。"), ("visual = generate_image(design)", "调用图片服务生成无文字背景。"), ("poster = render(brief, design, visual)", "程序将准确的中文信息画上去。"), ("report = evaluate(poster)", "检查版式与可用的视觉信号。"), ("return poster, report", "展示给用户，等待反馈。")],
    [{"name":"brief", "value":{"title":"春日摄影展"}, "from":"intake"}],
    [{"name":"初版", "value":{"poster":"poster_initial.png", "report":"评测报告"}, "to":"human"}],
    "apps/api/app/agent/graph.py", "create_hitl_react_graph", terms=("workflow",))

lesson("rag", "production", "找到可用的设计知识", "先限制可用范围，再召回、排序并返回来源。", "程序 + 检索服务", "质量增强",
    "有来源的规则可以帮助模型规划版式，也方便解释设计依据。", "仍可使用基础模板生成，但设计依据和可追溯性会减少。",
    "把和本次任务相关的少量知识交给模型，而不是把所有资料都塞进提示词。",
    [("query = build_query(brief)", "从主题、风格和视觉元素整理问题。"), ("cards = filter_candidates(request)", "只留下适合当前任务的知识。"), ("hits = vector_search(query, cards)", "在候选范围内按语义查找。"), ("matches = rank_and_trim(hits)", "结合词法分数排序，限制数量。"), ("return matches_with_sources(matches)", "连同来源一起返回。")],
    [{"name":"query", "value":"摄影展 时间地点醒目", "from":"query"}],
    [{"name":"matches", "value":[{"card_id":"demo-contrast", "source":"教学来源"}], "to":"planning"}],
    "apps/api/app/rag/retriever.py", "KnowledgeRetriever.retrieve", terms=("RAG", "embedding"),
    alternative="简单演示可以不用 RAG；但宣称有可追溯设计依据时，必须保留真实来源。")

lesson("query", "rag", "把需求变成检索问题", "拼接用户的主题、风格、视觉元素和所选案例特点。", "程序", "检索步骤必需",
    "检索服务需要知道这次要寻找什么。", "只用模糊标题检索，可能找不到时间地点布局等具体规则。",
    "把已知需求组织成查询文本，保留用户选择的设计维度。",
    [("parts = [brief.topic]", "先放入活动主题。"), ("parts += brief.style_preferences", "加入用户希望的风格。"), ("parts += brief.visual_elements", "加入视觉元素。"), ("return join(parts)", "组成一个可检索的问题。")],
    [{"name":"需求字段", "value":{"topic":"摄影展", "style_preferences":["清新"], "visual_elements":["相机"]}, "from":"brief"}],
    [{"name":"query", "value":"摄影展\n清新\n相机", "to":"recall"}],
    "apps/api/app/agent/nodes/retrieve_knowledge.py", "retrieve_generation_knowledge")

lesson("filter", "rag", "先筛选，再检索", "按审核状态、使用意图和适用区域缩小候选范围。", "程序", "可信检索必需",
    "语义相似不代表有权使用，也不代表适用于当前步骤。", "待审核规则或只适合评测的规则可能进入生成依据。",
    "先做业务条件过滤，再把合格卡片的编号交给向量库。",
    [("candidates = []", "准备保存符合条件的知识。"), ("for card in all_cards:", "逐条查看卡片。"), ("    if approved(card) and matches_scope(card):", "同时满足审核、用途和区域要求。"), ("        candidates.append(card)", "符合条件才进入候选。"), ("return candidates", "后面的语义检索只能从这里选择。")],
    [{"name":"all_cards", "value":["已审核的标题规则", "待审核的布局规则"], "from":"knowledge-data"}],
    [{"name":"candidate_ids", "value":["demo-title"], "to":"recall"}],
    "apps/api/app/rag/retriever.py", "KnowledgeRetriever._filter_candidates", lab="filter", terms=("metadata",))

lesson("filter-status", "filter", "审核状态这一关", "默认生成只使用 approved 知识卡。", "程序", "可信知识要求下必需",
    "团队还未确认的内容，不应默认成为设计依据。", "相似度很高的候选卡也可能是不可靠内容。",
    "先检查 review_status。当前实现也支持显式 include_candidates，普通生成不会打开它。",
    [("usable = []", "先准备空列表。"), ("for card in cards:", "每次检查一张卡片。"), ("    if card.review_status == 'approved':", "判断是否通过审核。"), ("        usable.append(card)", "通过后才放入结果。"), ("return usable", "这只是状态筛选，下一步还检查用途。")],
    [{"name":"cards", "value":[{"id":"A","review_status":"approved"},{"id":"B","review_status":"candidate"}], "from":"knowledge-data"}],
    [{"name":"usable", "value":["A"], "to":"filter-scope"}],
    "apps/api/app/rag/retriever.py", "KnowledgeRetriever._filter_candidates", lab="filter",
    quiz=("审核通过可以保证知识永远正确吗？", ["可以", "不可以，还需要更新、停用和复核"], 1, "审核是使用资格，不是永远正确的证明。"))

lesson("filter-scope", "filter", "这条规则适用于哪里？", "检查 generation 等使用意图，以及 title、event_info 等目标区域。", "程序", "检索精度保障",
    "标题规则和背景规则未必能混用，生成和优化也可能需要不同知识。", "系统可能把背景构图建议当成正文排版规则。",
    "检查用途是否匹配，再看规则目标与本次目标是否有交集；处理等价区域名称。",
    [("if card.intents and intent not in card.intents:", "卡片限定用途且当前用途不在其中。"), ("    skip(card)", "跳过这张卡片。"), ("if roles_overlap(card.target_roles, targets):", "判断目标区域是否相交；空范围表示不限制。"), ("    keep(card)", "满足条件，保留候选。")],
    [{"name":"request", "value":{"intent":"generation","target_roles":["event_info"]}, "from":"query"}],
    [{"name":"匹配范围", "value":"time_venue 与 event_info 视为同一类区域", "to":"recall"}],
    "apps/api/app/rag/retriever.py", "KnowledgeRetriever._filter_candidates", lab="filter", terms=("metadata",))

lesson("recall", "rag", "向量召回", "把查询转换为向量，查找语义接近的候选卡。", "检索服务", "当前检索方案的组成",
    "用户表达和知识原文可能用不同的词，但描述同一个意思。", "纯关键词检索可能漏掉意思接近、措辞不同的内容。",
    "embedding 将文本表示为数字向量，Chroma 比较距离；仍受候选 ID 限制。",
    [("vector = embed(query)", "用同一模型表示查询文本。"), ("hits = search(vector, candidate_ids)", "仅在允许的候选范围中查找。"), ("if service_unavailable:", "检索服务也可能失败。"), ("    return empty_result('vector_store_unavailable')", "当前代码明确报告不可用，不伪造检索成功。"), ("return hits", "返回召回分数，稍后再混合排序。")],
    [{"name":"query / candidate_ids", "value":{"query":"时间地点醒目","candidate_ids":["A"]}, "from":"filter"}],
    [{"name":"hits", "value":[{"id":"A","similarity":0.8}], "to":"rank"}],
    "apps/api/app/rag/retriever.py", "KnowledgeRetriever.retrieve", terms=("embedding", "Chroma"),
    alternative="小型资料集也可先用关键词检索。当前线上路径向量服务失败时返回空结果，不会自动执行离线评测脚本。")

lesson("rank", "rag", "混合排序", "把语义分数和词法重合程度组合，再按阈值和数量截断。", "程序", "质量增强",
    "语义相关的卡片未必覆盖查询里的具体字词。", "单一召回排序容易忽略明确的关键词；仍可工作但命中质量可能变化。",
    "当前权重是向量 0.85、词法 0.15，再将结果限制在 0～1。权重本身需要评测验证。",
    [("lexical = bigram_dice(card_text, query)", "先计算两个字一组的重合程度。"), ("score = vector_score * 0.85 + lexical * 0.15", "两种分数按权重相加。"), ("score = clamp(score, 0, 1)", "把异常越界值限制在合法范围。"), ("return top_matches_above_threshold(score)", "实际检索器再按分数筛选、排序和截断。")],
    [{"name":"scores", "value":{"vector":0.8,"lexical":0.4}, "from":"recall"}],
    [{"name":"combined", "value":0.74, "to":"citations"}],
    "apps/api/app/rag/reranker.py", "hybrid_similarity", lab="similarity", terms=("embedding",),
    quiz=("0.85 / 0.15 的权重能证明检索效果好吗？", ["能，向量占比高就准确", "不能，需要独立样例验证"], 1, "公式是一个设计选择，不是效果证据。"))

lesson("bigrams", "rank", "两个字一组，怎么算相似？", "用一个真正执行原函数的实验看清集合、交集和分数。", "程序", "当前词法算法必需",
    "比较中文连续字词，比只看单个字能保留一些相邻关系。", "单字重合容易把不相关短语判断为相近。",
    "先清理文本，再取相邻两个字符形成集合；Dice 分数是交集数量的两倍除以集合大小之和。",
    [("left_pairs = bigrams(normalize(left))", "例如摄影展得到 摄影、影展。"), ("right_pairs = bigrams(normalize(right))", "对另一段文字做同样处理。"), ("if not left_pairs or not right_pairs:", "不足两个字符时可能没有字对。"), ("    return 0", "避免除以零。"), ("overlap = len(left_pairs & right_pairs)", "计算共同的字对。"), ("return 2 * overlap / (len(left_pairs) + len(right_pairs))", "输出 0～1 的相似程度。")],
    [{"name":"left / right", "value":{"left":"摄影展","right":"摄影活动"}, "from":"rank"}],
    [{"name":"Dice", "value":0.4, "to":"rank"}],
    "apps/api/app/rag/reranker.py", "bigram_dice", lab="similarity", terms=("集合",))

lesson("citations", "rag", "把来源带回去", "让设计依据可以追到知识卡和原始资料。", "程序", "可追溯要求下必需",
    "用户需要知道模型引用的规则来自哪里。", "模型说有依据，却无法指出对应卡片与来源。",
    "返回 card_id、source_id 和来源定位；设计规划只允许引用本次实际召回的卡片。",
    [("for match in matches:", "检查实际召回结果。"), ("    citation = source_of(match.card)", "从卡片取出已有来源，不让模型编造。"), ("    citations.append(citation)", "保存每条依据。"), ("return citations", "交给规划和前端展示。")],
    [{"name":"match", "value":{"card_id":"A","source_id":"source-demo"}, "from":"rank"}],
    [{"name":"citations", "value":[{"card_id":"A","source_id":"source-demo"}], "to":"planning"}],
    "apps/api/app/rag/citations.py", terms=("RAG",))

lesson("planning", "production", "生成结构化设计方案", "模型提出颜色、视觉描述和设计目标，程序约束活动事实与模板。", "模型 + 程序校验", "当前生成流程必需",
    "图像生成和排版需要具体且一致的设计参数。", "直接使用一段自由文本，后续程序很难稳定读取和检查。",
    "要求 JSON 输出，再归一化颜色、注意顺序、引用与模板；布局坐标来自受信任模板。",
    [("messages = build_prompt(brief, knowledge)", "把事实与可引用依据分开说明。"), ("raw = model.complete_json(messages)", "模型提出方案，输出仍需检查。"), ("design = normalize_and_validate(raw)", "修正或拒绝不合法字段。"), ("layout = instantiate_template(brief)", "程序负责确定版式坐标。"), ("return design, layout", "传给生图与渲染步骤。")],
    [{"name":"brief + knowledge", "value":{"title":"春日摄影展","knowledge_refs":["A"]}, "from":"rag"}],
    [{"name":"design_spec", "value":{"palette":{"primary":"#234E52"},"visual_prompt":"春日摄影主题，无文字"}, "to":"image"}],
    "apps/api/app/agent/nodes/plan_design.py", "plan_design", terms=("Schema", "prompt"))

lesson("image", "production", "生成无文字主视觉", "把画面描述发给图片服务，保存返回的图片。", "外部模型", "有主视觉的产品需要",
    "活动海报需要与主题相符的画面。", "可以使用已有背景，但无法按新需求生成主视觉。",
    "通过 Provider 隔离供应商协议；返回图片地址或数据后保存为本地任务产物。",
    [("image = provider.generate(design.visual_prompt)", "这是外部服务边界，真实调用可能收费。"), ("path = download_and_save(image)", "统一处理 URL 或图片数据。"), ("return {'main_visual_path': path}", "返回状态更新，不是把所有状态重新创建一遍。")],
    [{"name":"visual_prompt", "value":"春日、摄影、留白，不含文字", "from":"planning"}],
    [{"name":"main_visual_path", "value":"main_visual.png", "to":"render"}],
    "apps/api/app/agent/nodes/generate_visual.py", "generate_visual", terms=("Provider",),
    alternative="可以复用已授权背景或使用本地生成服务；学习演示使用预设响应，不真实调用模型。")

lesson("render", "production", "把准确的文字画上去", "根据模板和活动事实，将中文叠加到背景，保存最终海报。", "程序", "当前产品核心必需",
    "活动时间和地点要准确，不能完全依赖图片模型生成文字。", "可能出现错字、遗漏，修改日期也难以独立完成。",
    "文字内容来自结构化需求，位置和字体来自布局参数，Pillow 负责确定性绘制。",
    [("canvas = load_background(main_visual_path)", "先读取生成的背景。"), ("for element in layout.elements:", "按照图层顺序逐项处理。"), ("    font = choose_font(element)", "选字体并检查缺字回退。"), ("    text = fit_text(element.content, element.box)", "测量与换行，必要时缩小字号。"), ("    draw_text(canvas, text, font)", "把文字画入海报。"), ("return save(canvas)", "输出图片与实际文字边界。")],
    [{"name":"layout + visual", "value":{"title":"春日摄影展","font_size":72}, "from":"planning"}],
    [{"name":"poster / text_facts", "value":{"file":"poster_initial.png","actual_font_size":68}, "to":"evaluate"}],
    "apps/api/app/poster/renderer.py", "PosterRenderer.render", terms=("确定性",))

lesson("fonts", "render", "字体选择与回退", "解释为什么明明有艺术字体，最后仍可能出现常规粗体。", "程序", "文字可显示的保障",
    "字体文件必须存在，并覆盖标题中的字符。", "缺字可能变成方框，或让整个标题无法正常渲染。",
    "显式选择优先；auto 可能沿用案例字体。缺字或缺文件时，当前代码会整标题回退。",
    [("font = explicit_choice_or_case_default()", "先尊重手动选择，再看案例和活动类型。"), ("if not exists(font) or not supports_all_chars(font):", "检查文件和字符覆盖。"), ("    font = standard_bold", "当前版本整标题回退，艺术效果可能损失。"), ("return font, explanation", "保留实际字体与回退说明。")],
    [{"name":"title_font", "value":"mashanzheng", "from":"form"}],
    [{"name":"实际字体", "value":"Ma Shan Zheng；缺字时可能回退", "to":"render"}],
    "apps/api/app/poster/font_catalog.py", "select_title_font",
    alternative="规划中的独立艺术标题层可改变表现方式，但当前源码仍主要依靠字体排版。")

lesson("fit", "render", "字号、换行与边界", "测量文字能否装进区域，而不是只相信请求的字号。", "程序", "可读排版必需",
    "标题长短不一，同样字号不一定能放入同一个框。", "长标题会越界或覆盖其他内容。",
    "测量文字，按宽度换行；超出高度时逐步缩小字号，并记录实际尺寸。",
    [("size = requested_size", "从用户请求的字号开始。"), ("while size >= minimum_size:", "只在允许范围内尝试。"), ("    lines = wrap_text(text, size, width)", "按当前字号计算换行。"), ("    if measured_height(lines) <= height:", "检查高度。"), ("        return lines, size", "找到能放下的结果。"), ("    size -= 1", "放不下就缩小后再试。")],
    [{"name":"text / box", "value":{"text":"春日校园摄影作品展","width":600,"height":180}, "from":"render"}],
    [{"name":"text layout", "value":{"font_size":64,"line_count":2}, "to":"rules"}],
    "apps/api/app/poster/typography.py", "fit_text", terms=("确定性",))

lesson("evaluate", "production", "评测，并说明缺了什么信号", "组合版式规则、视觉评价和可选注意力预测，给用户可解释的反馈。", "程序 + 模型", "产品质量反馈需要",
    "生成成功不等于文字清晰、布局合适或修改目标达成。", "很难知道修改是否修复了问题，也难以展示失败边界。",
    "分别保留每种信号的结果与可用性，再计算分数；总分仅是辅助指标。",
    [("rules = check_layout(poster, layout)", "先检查确定性规则。"), ("vision = review_with_model(poster)", "视觉服务可能不可用。"), ("attention = predict_attention_if_available(poster)", "可选信号，不是真实眼动。"), ("scores = aggregate(rules, vision, attention)", "只按可用信号计算。"), ("return report(scores, issues, availability)", "连同缺失与问题说明一起返回。")],
    [{"name":"poster + layout", "value":"海报及文字区域", "from":"render"}],
    [{"name":"report", "value":{"issues":["活动信息字号较小"],"available_weight":75}, "to":"human"}],
    "apps/api/app/agent/nodes/evaluate.py", "evaluate_draft", terms=("降级",))

lesson("rules", "evaluate", "不用模型的版式检查", "检查文字边界、重叠、间距和信息层级。", "程序", "基础质量保障",
    "越界和重叠属于可以用明确条件检查的问题。", "即使模型说好看，文字也可能实际超出画布。",
    "比较真实文字区域与画布、其他区域，产生带严重程度的问题列表。",
    [("issues = []", "收集问题，不急着得出审美结论。"), ("for box in text_boxes:", "逐个检查文字区域。"), ("    if outside_canvas(box):", "判断是否越界。"), ("        issues.append('文字越界')", "保留明确问题及定位。"), ("return issues", "交给评分与修改建议。")],
    [{"name":"text_boxes", "value":[{"x":30,"y":20,"width":600}], "from":"fit"}],
    [{"name":"issues", "value":[], "to":"scores"}],
    "apps/api/app/evaluation/hard_rules.py", terms=("确定性",))

lesson("scores", "evaluate", "缺失信号不等于零分", "看清加权评分的分子、分母和可用性。", "程序", "诚实评测必需",
    "服务不可用时，不能假装它完成了评测。", "把不可用视为零分会混淆服务故障与真实效果差；只看总分又可能误判提升。",
    "当前规则占 40，视觉占 35，注意力占 25；可用信号才进入分母，并保留 available_weight。",
    [("earned = hard_rules", "先保留规则得分。"), ("weight = 40", "规则检查的权重为 40。"), ("if vision_is_available:", "有真实视觉结果才参与。"), ("    earned += vision_score * 0.35", "加入视觉加权得分。"), ("    weight += 35", "同时增加分母。"), ("return earned / weight * 100", "这是简化示例；真实函数还处理注意力信号。")],
    [{"name":"signals", "value":{"hard_rules":40,"vision":80,"attention":"不可用"}, "from":"rules"}],
    [{"name":"scores", "value":{"total":90.67,"available_weight":75}, "to":"comparison"}],
    "apps/api/app/evaluation/score_aggregator.py", "aggregate_scores", lab="scores", terms=("降级",),
    quiz=("初版只有规则分，修改后有视觉分，能直接比较总分吗？", ["可以，数字大就是更好", "不可以，先检查信号与评测条件是否一致"], 1, "分母和评价依据变化，不能当作同条件提升。"))

lesson("comparison", "evaluate", "前后分数能比较吗？", "先检查条件是否一致，再讨论分数变化和目标是否达成。", "程序 + 用户", "效果结论必需",
    "两个数字可能来自不同的可用信号或设计目标。", "可能把评测服务恢复造成的变化宣传为版式优化。",
    "比较评测条件；不一致时标记不可比较，仍可逐项看活动事实、版式问题及用户反馈。",
    [("if not same_conditions(before, after):", "先检查可用信号等条件。"), ("    return 'not_comparable'", "明确拒绝直接比较综合分。"), ("return after.total - before.total", "同条件下才计算差值，仍不等于用户更喜欢。")],
    [{"name":"before / after", "value":{"before_weight":40,"after_weight":75}, "from":"scores"}],
    [{"name":"comparison", "value":"not_comparable", "to":"human"}],
    "apps/api/app/agent/nodes/complete_round.py", terms=("not_comparable",))

lesson("iteration", "system", "收到反馈后，怎样修改？", "用户设目标，模型选工具，程序执行并把结果返回模型。", "用户 + 模型 + 程序", "交互修改核心",
    "第一张结果往往不满足用户的全部要求。", "用户只能重新生成，难以保留满意部分并进行定向调整。",
    "用 ReAct 循环让模型读取上一步 Observation；工具范围和次数由程序限制。",
    [("feedback = wait_for_user()", "先获得用户目标。"), ("while tool_count < 3:", "单轮有明确次数上限。"), ("    decision = choose_tool(feedback, observations)", "模型结合已有结果选择下一步。"), ("    observations.append(execute_checked(decision))", "程序校验、执行并返回观察结果。"), ("return render_and_evaluate_once()", "轮末统一渲染，避免每个动作生成一个版本。")],
    [{"name":"feedback", "value":"时间地点更醒目，保持背景不变", "from":"human"}],
    [{"name":"new_round", "value":{"font_size":48,"poster":"round-1.png"}, "to":"human"}],
    "apps/api/app/agent/graph.py", "create_hitl_react_graph", terms=("ReAct", "Observation"))

lesson("human", "iteration", "暂停，等待你的决定", "保存当前状态，将海报和评测交给用户，再从同一任务继续。", "用户决定，程序恢复", "人机协作必需",
    "主观设计目标需要用户参与，不能让模型无限自动修改。", "模型可能继续改动已经满意的部分，或在反馈时丢失前文。",
    "LangGraph interrupt 暂停；恢复时校验输入，读取保存的状态并进入下一轮或结束。",
    [("checkpoint = build_preview(state)", "整理当前海报、分数和引用。"), ("decision = interrupt(checkpoint)", "先暂停；得到恢复输入后才向下执行。"), ("if decision.action == 'finish':", "用户选择结束。"), ("    return finish_update", "走最终保存路径。"), ("return prepare_next_round(decision)", "保留上下文，设置本轮目标。")],
    [{"name":"checkpoint", "value":{"round_number":0,"poster":"initial.png"}, "from":"evaluate"}],
    [{"name":"decision", "value":{"action":"instruct","instruction":"时间地点更醒目"}, "to":"decide"}],
    "apps/api/app/agent/nodes/human_review.py", "human_review", terms=("HITL", "checkpoint"))

lesson("decide", "iteration", "Agent 选择下一步", "先检查程序约束，再向模型询问工具与参数。", "模型选择，程序约束", "ReAct 核心",
    "自由文本反馈需要转成允许执行的具体动作。", "模型回答了一段建议，但没有可以执行的结构化动作。",
    "让模型返回工具名与参数；达到调用上限时程序直接结束本轮，不再让模型决定。",
    [("if tool_calls >= 3:", "安全上限由代码决定。"), ("    return finish_round()", "达到上限就进入渲染评测。"), ("payload = model.choose_tool(context)", "未达上限，才询问模型。"), ("return validate_decision(payload)", "必须符合约定字段和允许工具。")],
    [{"name":"context", "value":{"instruction":"放大活动信息","tool_calls":0}, "from":"human"}],
    [{"name":"decision", "value":{"tool_name":"modify_typography","arguments":{"font_size":48}}, "to":"execute"}],
    "apps/api/app/agent/nodes/react_decide.py", "react_decide", terms=("ReAct", "Schema"), lab="budget",
    quiz=("工具次数达到上限时谁决定停止？", ["程序直接停止本轮工具循环", "继续询问模型是否想停止"], 0, "预算是程序边界，不能交给模型自行遵守。"))

lesson("execute", "iteration", "校验并执行工具", "检查工具、参数和锁定条件，执行后记录结果。", "程序", "工具执行必需",
    "模型输出有可能错误，用户锁定的内容也必须保留。", "工具可能越权修改活动事实或无法渲染的参数。",
    "只分发注册工具，执行时校验参数与业务约束；失败也返回 Observation 给下一次决策。",
    [("tool = registry.get(decision.tool_name)", "只能使用已注册的工具。"), ("args = validate(decision.arguments)", "检查参数字段和范围。"), ("result = tool.execute(args, controls)", "执行时检查内容与锁定条件。"), ("observation = describe(result)", "把结果转成可理解的观察信息。"), ("return update_state_and_trace(result, observation)", "记录参数、结果和成功状态。")],
    [{"name":"decision", "value":{"tool":"modify_typography","font_size":48}, "from":"decide"}],
    [{"name":"observation", "value":"活动信息字号已调整；背景未改变", "to":"decide"}],
    "apps/api/app/agent/nodes/execute_react_tool.py", "execute_react_tool", terms=("Observation",))

lesson("locks", "execute", "保护用户明确要求不变的内容", "校验活动事实、主视觉构图和用户锁定的属性。", "程序", "可控修改必需",
    "修改字号不应该顺带改日期，也不应该移动锁定元素。", "单个动作看似合理，整体却违背用户要求。",
    "执行后比较修改前后的布局，发现事实或锁定属性变化就拒绝结果。",
    [("for element in before.elements:", "逐个检查原来存在的元素。"), ("    new = after.find(element.id)", "找到修改后的对应元素。"), ("    if element.content != new.content:", "活动文字应保持。"), ("        reject('不能改变活动事实')", "拒绝这次非法修改。"), ("check_locked_properties(before, after)", "继续检查位置、字号、字体等锁定条件。")],
    [{"name":"before / after", "value":{"before":"周五18:00","after":"周六18:00"}, "from":"execute"}],
    [{"name":"结果", "value":"拒绝：此工具不能改变活动事实", "to":"execute"}],
    "apps/api/app/poster/design_guards.py", "assert_design_constraints", terms=("Schema",))

lesson("round", "iteration", "一轮结束后统一渲染", "工具先修改结构参数，轮末保存一个可比较的正式版本。", "程序", "版本与效率要求下需要",
    "用户需要看整轮反馈的结果，而不是每个微小动作都产生一张图。", "中间产物过多，前后比较与引用关系难以管理。",
    "先累积布局变化，再统一绘制与评测，保存轮次快照和工具轨迹。",
    [("poster = render(updated_layout)", "把这一轮的修改真正画出来。"), ("report = evaluate(poster)", "使用相同评测流程复评。"), ("snapshot = save_round(poster, report, traces)", "保存本轮结果与依据。"), ("return wait_for_user_or_finish(snapshot)", "最多三轮，未达上限时再询问用户。")],
    [{"name":"updated_layout", "value":{"event_info_font_size":48}, "from":"execute"}],
    [{"name":"round_snapshot", "value":{"round":1,"poster":"round-1.png"}, "to":"human"}],
    "apps/api/app/agent/nodes/complete_round.py", terms=("state",))

lesson("persistence", "system", "保存状态、产物和过程", "分别保存任务信息、恢复检查点、文件产物和事件。", "程序", "可恢复与追溯需要",
    "任务会暂停，服务会重启，用户还要回看历史。", "刷新或重启后可能无法恢复，也不知道哪张图来自哪次执行。",
    "不同存储对象承担不同责任：任务状态用于查询，检查点用于恢复，文件用于展示，事件用于回看。",
    [("save_run_status(run_id, status)", "任务列表要知道当前状态。"), ("save_checkpoint(run_id, state)", "恢复执行要知道完整上下文。"), ("save_artifacts(run_id, files)", "把图片和报告放在任务目录。"), ("append_events(run_id, events)", "保存关键执行事件。")],
    [{"name":"state / files", "value":"任务数据和图片", "from":"production"}],
    [{"name":"history", "value":"可查询的任务与产物", "to":"interface"}],
    "apps/api/app/agent/executor.py", terms=("checkpoint", "state"))

lesson("checkpoint", "persistence", "检查点怎样继续执行？", "用任务编号找到暂停位置和状态，在同一任务里恢复。", "程序", "跨请求恢复必需",
    "人工反馈可能在几分钟后到达，不能只依赖当前函数的局部变量。", "系统会重新开始生成，或丢失之前的修改和引用。",
    "SQLite Checkpointer 保存 LangGraph 状态，thread_id 对应任务编号；Command(resume=...) 传入反馈。",
    [("config = {'thread_id': run_id}", "指定要恢复哪一个任务。"), ("state = load_checkpoint(config)", "找到上次暂停的上下文。"), ("resume_graph(decision, config)", "从中断处恢复，而不是创建新任务。"), ("return next_checkpoint_or_result", "可能再次等待人工，也可能结束。")],
    [{"name":"run_id + decision", "value":{"run_id":"教学任务-001","action":"instruct"}, "from":"human"}],
    [{"name":"outcome", "value":"waiting_for_human 或 completed", "to":"interface"}],
    "apps/api/app/agent/executor.py", "LangGraphAgentExecutor.resume", terms=("checkpoint", "HITL"))

lesson("artifacts", "persistence", "生成文件放在哪里？", "以任务编号分隔图片、报告和事件文件。", "程序", "交付产物必需",
    "同一用户也可能同时创建多个任务，文件不能互相覆盖。", "不同任务都保存 poster.png 时会冲突，也无法追踪来源。",
    "使用 run_id 子目录和安全文件名，写入完成后原子替换；当前仍是任务文件管理，不是素材审核平台。",
    [("folder = root / run_id", "每个任务一个目录。"), ("validate_plain_filename(name)", "拒绝路径穿越和任意子目录。"), ("write_temporary(folder, name, data)", "先写临时文件。"), ("replace_final_file()", "写完后替换正式文件。"), ("return artifact_reference", "返回可查询的相对路径与类型。")],
    [{"name":"file", "value":{"run_id":"教学任务-001","name":"poster_initial.png"}, "from":"render"}],
    [{"name":"artifact", "value":"教学任务-001/poster_initial.png", "to":"interface"}],
    "apps/api/app/services/artifact_service.py", "ArtifactService.write_bytes", terms=("原子操作",))

lesson("events", "persistence", "事件能告诉我们什么？", "记录节点结果、工具参数、观察结果和轮次。", "程序", "观察与排查需要",
    "流程失败时，需要定位在哪个步骤、用了什么参数。", "页面只显示失败，难以解释模型和工具做过什么。",
    "保留结构化事件；当前部分 Agent 事件在阶段结束后汇总发出，不能理解为每行代码的实时日志。",
    [("event = {'node': node, 'message': message}", "记录发生在哪个节点。"), ("event['payload'] = result_summary", "保存有用的参数与结果摘要。"), ("append_event(event)", "加入当前任务记录。"), ("notify_frontend(event)", "由服务层向页面展示。")],
    [{"name":"tool result", "value":{"step":1,"success":True,"font_size":48}, "from":"execute"}],
    [{"name":"event", "value":{"node":"modify_typography","message":"修改成功"}, "to":"interface"}],
    "apps/api/app/services/run_service.py", "RunService._emit_agent_events", terms=("SSE",))

lesson("interface", "system", "浏览器怎样和后端配合？", "表单提交任务，页面通过事件和查询展示进度与结果。", "用户 + 程序", "交互产品必需",
    "用户需要输入、看到过程、提出修改并取回海报。", "只能通过脚本调用后端，不方便非开发者使用。",
    "HTTP 接口处理业务请求，SSE 展示事件，轮询同步任务状态。页面不是模型执行器。",
    [("run_id = submit_form(brief)", "表单变成 HTTP 请求。"), ("listen_for_events(run_id)", "展示服务器发来的事件。"), ("status = poll_status(run_id)", "同步当前任务状态。"), ("if status == 'waiting_for_human':", "后端暂停时才显示人工决策。"), ("    show_review_panel()", "用户输入下一步目标。")],
    [{"name":"用户输入", "value":"活动需求与修改意见", "from":"form"}],
    [{"name":"页面", "value":"海报、事件、评测与反馈入口", "to":"human"}],
    "apps/web/src/pages/WorkspacePage.tsx", terms=("API", "SSE"))

lesson("form", "interface", "表单与重复提交", "收集需求、显示校验错误，提交期间避免重复操作。", "程序", "交互可靠性需要",
    "网络请求需要时间，用户可能连续点击或提交空字段。", "可能重复创建任务，或无法理解输入为什么不被接受。",
    "页面负责即时提示与提交状态；真正的字段和状态校验仍要由后端执行。",
    [("if submitting:", "请求还没结束时，不重复发送。"), ("    return", "避免普通的重复点击。"), ("result = await submit(brief)", "把需求传给后端校验。"), ("show_result_or_error(result)", "让用户知道下一步该做什么。")],
    [{"name":"form fields", "value":{"title":"春日摄影展"}, "from":"system"}],
    [{"name":"HTTP request", "value":"POST /api/v1/runs", "to":"intake"}],
    "apps/web/src/features/brief/BriefForm.tsx", terms=("API",))

lesson("designhub", "system", "DesignHub：未来如何接上团队业务？", "规划中的配套模块，管理活动修订、知识发布、正式素材和审核。", "团队 + 程序", "团队协作目标需要",
    "任务文件需要进一步变成有版本、审核与有效性的业务素材。", "生成结果虽然保存了，却无法明确哪个版本可以正式使用。",
    "围绕业务对象建立状态与版本关系，让生成输入和正式输出可维护。",
    [("event = manage_activity_revision()", "活动是独立对象，不只存在于任务里。"), ("knowledge = get_published_knowledge()", "获取已发布知识批次。"), ("draft = register_generated_asset(event)", "生成结果先登记为草稿。"), ("return review_and_publish(draft)", "另一位成员确认版本后才正式发布。")],
    [{"name":"资料与生成产物", "value":"活动事实、规则卡、海报", "from":"artifacts"}],
    [{"name":"正式素材", "value":"经审核且仍有效的海报", "to":"system"}],
    "docs/team-workbench-upgrade-plan.md", status="planned", terms=("版本",),
    alternative="目前是设计方案，不存在可逐行执行的 DesignHub 业务源码；此处只播放规划模拟。")

lesson("activities", "designhub", "活动修订与旧图失效", "改期后，旧图仍可追溯，但不能再当成当前正式图。", "程序", "正式交付需要",
    "活动时间改变后，已经审核的图片可能不再正确。", "团队可能继续转发已过期海报。",
    "素材绑定活动修订；查询正式素材时同时检查批准状态和当前修订。",
    [("event.revision += 1", "时间地点等事实变化时生成新修订。"), ("for asset in event.assets:", "找到关联素材。"), ("    if asset.event_revision != event.revision:", "判断制作时使用的事实是否过期。"), ("        exclude_from_official_results(asset)", "从正式查询排除；历史依然保留。")],
    [{"name":"event", "value":{"old_time":"周五","new_time":"周六","revision":2}, "from":"designhub"}],
    [{"name":"old_asset", "value":{"event_revision":1,"current":False}, "to":"assets"}],
    "docs/team-workbench-upgrade-plan.md", status="planned", lab="revision", terms=("版本",),
    quiz=("平台能撤回已经发到群里的旧图片吗？", ["可以自动撤回所有副本", "不能，只能阻止平台继续提供旧正式版并提示跟进"], 1, "平台内有效性管理不能替代外部消息撤回。"))

lesson("approval", "designhub", "审核绑定哪一版？", "审核要针对具体文件和活动修订，不能只针对一个海报名称。", "审核者 + 程序", "团队发布需要",
    "审核通过后更换图片，原来的确认就不再适用。", "可能用旧审批发布新内容，或在活动改期同时批准旧图。",
    "服务端检查身份、版本与文件摘要，在事务中完成当前性检查和发布。",
    [("require_reviewer(user, draft)", "制作人与审核职责区分。"), ("with transaction():", "把检查与写入作为一组操作。"), ("    verify_revision_and_file(draft)", "确保审核对象仍是当前那一版。"), ("    publish(draft)", "通过后才成为正式素材。")],
    [{"name":"approval request", "value":{"asset":"A","version":2}, "from":"assets"}],
    [{"name":"approved asset", "value":{"asset":"A","approved_version":2}, "to":"assets"}],
    "docs/team-workbench-upgrade-plan.md", status="planned", terms=("事务", "版本"))

lesson("knowledge-data", "designhub", "知识审核与可靠发布", "已有知识卡基础，完整的审核发布和版本切换仍在规划中。", "维护者 + 程序", "持续维护需要",
    "知识会更新，向量索引构建也可能失败。", "清空旧集合再构建失败，可能让检索暂时失去可用数据。",
    "先构建新批次并验证，再切换当前指针；明确停用的内容立即排除。",
    [("draft = edit_card_with_source()", "保留出处并人工核对。"), ("new_index = build_new_release(draft)", "独立构建，不先破坏旧版本。"), ("if validate(new_index):", "验证完整性和检索结果。"), ("    activate(new_index)", "成功后才切换。"), ("else: keep_current_release()", "失败时继续使用上一可用批次。")],
    [{"name":"approved revision", "value":"设计规范 v2", "from":"designhub"}],
    [{"name":"active_release", "value":"成功切换 v2；失败保留 v1", "to":"filter"}],
    "docs/team-workbench-upgrade-plan.md", status="planned", terms=("原子操作", "版本"))

lesson("assets", "designhub", "让文件成为可以复用的素材", "记录素材身份、来源、版本与使用资格。", "程序", "跨任务复用需要",
    "只知道图片在哪个任务目录，无法回答哪个版本已获确认。", "用户可能复用草稿或找不到制作依据。",
    "给资产关联活动修订、生成轮次、标题版本和知识批次，正式查询只返回有效批准版本。",
    [("asset = register(file, run_id, round_id)", "登记来源，不必重复复制图片。"), ("asset.event_revision = event.revision", "绑定活动事实版本。"), ("asset.status = 'draft'", "生成完不等于批准。"), ("return query_approved_current_assets(event)", "使用时同时校验审核与有效性。")],
    [{"name":"artifact", "value":"某次任务的海报文件", "from":"artifacts"}],
    [{"name":"asset", "value":{"id":"asset-A","status":"draft","event_revision":1}, "to":"approval"}],
    "docs/team-workbench-upgrade-plan.md", status="planned", terms=("版本",))


GLOSSARY = {
    "Agent":"能根据目标和已有结果选择下一步动作的程序。这里是一个受工具范围和次数限制的 Agent。",
    "state":"共享状态：流程一路携带的数据包。节点通常返回需要更新的字段，不是重建所有数据。",
    "API":"程序之间约定的调用入口。浏览器发请求，后端返回数据。",
    "Schema":"数据格式约定：需要哪些字段、类型是什么、哪些值合法。",
    "workflow":"工作流：程序安排好的步骤顺序以及条件分支。",
    "RAG":"先检索相关资料，再把找到的资料作为模型输入的一部分。检索到不代表资料必然正确。",
    "embedding":"把文本转换成一组数字，使语义接近的文本可以通过距离比较找到。",
    "metadata":"描述内容的附加字段，例如审核状态、用途和适用区域。",
    "Chroma":"保存和查询向量数据的工具；活动审批状态仍应由业务数据负责。",
    "集合":"没有重复元素的一组值。交集就是两个集合共同拥有的值。",
    "prompt":"给模型的任务说明和上下文。模型收到说明不等于必然遵守，程序仍要校验。",
    "Provider":"对外部模型服务的适配层，把不同供应商的调用差异集中在一处。",
    "确定性":"相同输入和相同环境下，程序遵循明确规则得到可预期的结果。",
    "降级":"某个能力不可用时，保留能够继续提供的功能，并明确说明缺少什么。",
    "not_comparable":"不可直接比较：前后评测条件不同，不能用总分差宣称效果提升。",
    "ReAct":"模型选择动作 → 工具执行 → 返回观察结果 → 模型再决定下一步的循环。",
    "Observation":"工具执行后返回给模型的结果或错误，不是模型私有的推理过程。",
    "HITL":"人在流程中参与决策。例如初版生成后先让用户确认，再继续修改。",
    "checkpoint":"检查点：保存暂停位置和必要状态，之后可以从这里继续。",
    "原子操作":"外部看到的是完整的一次变更，不会看到写到一半的中间结果。具体保证范围取决于实现。",
    "SSE":"服务器向浏览器持续发送事件的连接。它不自动意味着模型每个 token 或代码每行都实时显示。",
    "版本":"某个对象在一个时点的明确内容。审核和引用应指向具体版本。",
    "事务":"把相关数据库检查与修改放在一个一致性边界里，防止并发操作破坏业务规则。"
}

PATHS = [
    {"id":"start", "title":"第一次来：看懂一张海报", "nodes":["system","intake","production","rag","planning","image","render","evaluate","human"]},
    {"id":"agent", "title":"理解 Agent 到底做了什么", "nodes":["iteration","human","decide","execute","locks","round","checkpoint"]},
    {"id":"rag", "title":"从一条查询拆开 RAG", "nodes":["rag","query","filter","filter-status","filter-scope","recall","rank","bigrams","citations"]},
    {"id":"team", "title":"规划课：团队怎样交付素材", "nodes":["designhub","activities","approval","knowledge-data","assets"]}
]


def catalog():
    return {"nodes": NODES, "glossary": GLOSSARY, "paths": PATHS,
        "title":"PosterPilot 学习台", "version":"1.0", "root":"system"}
