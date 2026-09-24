"""Generated teaching replay, explicitly NOT a production execution trace."""
from copy import deepcopy

SCENARIOS = [
    {"id":"normal", "title":"生成初版，再修改一次", "description":"主线：检索 → 规划 → 生图替身 → 排版 → 评测 → 人工反馈 → 工具 → 复评。"},
    {"id":"empty_retrieval", "title":"如果没有找到知识", "description":"检索返回空结果和原因，规划使用基础版式，不伪造引用。"},
    {"id":"tool_failure", "title":"如果工具执行失败", "description":"失败被记录为 Observation，模型根据结果换一个合法动作。"},
    {"id":"missing_signal", "title":"如果视觉服务不可用", "description":"标记缺失信号；前后条件不同，不比较综合分。"},
    {"id":"budget_limit", "title":"如果工具次数到上限", "description":"模型还想继续，程序在第三次后直接结束工具循环。"}
]


def make_trace(scenario="normal", title="春日摄影展"):
    if scenario not in {s["id"] for s in SCENARIOS}:
        raise ValueError("未知教学场景")
    if not isinstance(title,str) or not title.strip() or len(title)>30:
        raise ValueError("教学标题需要 1～30 个字符")
    title=title.strip()
    state={"status":"未开始","round_number":0,"tool_calls_in_round":0}
    steps=[]
    def add(node,line,heading,explanation,inputs,output,updates=None,actor="程序",wait=False):
        before=deepcopy(state)
        state.update(updates or {})
        steps.append(dict(node=node,line=line,title=heading,explanation=explanation,
            input=deepcopy(inputs),output=deepcopy(output),state_before=before,state_after=deepcopy(state),
            changes={k:{"before":before.get(k,"尚未产生"),"after":deepcopy(v)} for k,v in (updates or {}).items() if before.get(k)!=v},
            actor=actor,wait=wait))
    brief={"title":title,"event_time":"周五 18:00","location":"图书馆大厅","style_preferences":["清新"]}
    add("form",3,"用户提交活动需求","表单把需求发给后端；这里用教学输入代替真实网络提交。",brief,{"request":"POST /api/v1/runs"},actor="用户")
    add("brief",5,"需求通过校验","标题非空，画布是竖版；没有提供的信息不由模型补写。",brief,brief,{"brief":brief})
    add("intake",2,"创建独立任务","任务 ID 用于关联状态与产物。教学记录不写入业务数据库。",brief,{"run_id":"learn-demo-001"},{"run_id":"learn-demo-001","status":"queued"})
    add("intake",3,"开始生成流程","固定流程由程序安排，不是模型临时发明步骤。",{"run_id":"learn-demo-001"},{"next":"检索生成知识"},{"status":"running"})
    query=title+" 清新 活动信息"
    add("query",4,"组织检索问题","组合主题与已知风格，为后面的筛选和召回提供输入。",brief,{"query":query},{"query":query})
    candidates=["demo-contrast","demo-hierarchy"]
    add("filter-status",5,"排除待审核卡片","教学样例中有一条 candidate；默认生成只保留 approved。",{"cards":["对比度：approved","层级：approved","未核实：candidate"]},{"candidate_ids":candidates},{"candidate_ids":candidates})
    add("filter-scope",4,"限制用途和区域","检查 generation 意图，以及 title / event_info 等适用区域。",{"intent":"generation","target_roles":["title","event_info"]},candidates)
    empty=scenario=="empty_retrieval"
    matches=[] if empty else [{"id":"demo-contrast","vector_score":0.8,"lexical_score":0.4}]
    add("recall",5,"取得召回结果" if not empty else "没有达到召回阈值","向量分数是预设教学值，本次没有调用 embedding 或 Chroma。",{"query":query,"candidate_ids":candidates},{"matches":matches,"fallback_reason":"below_similarity_threshold" if empty else None},{"retrieval_available":not empty},actor="检索响应替身")
    add("rank",2,"组合两种分数" if not empty else "保留空结果","0.8 × 0.85 + 0.4 × 0.15 = 0.74。无结果时不能编造卡片。",matches,[] if empty else [{"id":"demo-contrast","score":0.74}])
    refs=[] if empty else ["demo-contrast"]
    add("citations",4,"携带实际引用","引用只来自实际保留的卡片；这里的 demo 来源是教学样例。",refs,{"knowledge_refs":refs},{"knowledge_refs":refs})
    design={"template_id":"cultural_event","palette":{"primary":"#234E52"},"visual_prompt":"春日摄影主题，留白，无文字","knowledge_refs":refs}
    add("planning",2,"模型提出结构化方案","这里使用明确标注的固定模型响应；空检索场景采用基础版式。",{"brief":brief,"knowledge_refs":refs},design,{"design_spec":design},actor="模型响应替身")
    layout={"title":{"text":title,"font_size":72},"event_info":{"text":"周五 18:00 · 图书馆大厅","font_size":32}}
    add("planning",4,"程序填入模板","模型不任意设计坐标；活动文字来自输入，程序创建可渲染布局。",design,layout,{"layout":layout})
    add("image",3,"图片响应返回","学习台使用示意背景，不调用付费图片模型，也不把它当真实生成结果。",{"prompt":design["visual_prompt"]},{"main_visual_path":"教学背景示意"},{"main_visual_path":"教学背景示意"},actor="图片响应替身")
    add("fonts",4,"选择并说明字体","当前工程仍是字体排版。独立艺术标题层属于后续升级。",{"title":title,"title_font":"auto"},{"font":"装饰宋体预设"},{"font_choice":"装饰宋体预设"})
    add("fit",5,"测量文字区域","这里是教学排版数据；实际 fit_text 使用字体测量和边界计算。",layout,{"title_size":72,"event_info_size":32})
    add("render",6,"保存初版海报","合成文字和背景后才是一张完整海报。本回放仅展示示例产物名称，未运行真实渲染器。",layout,{"poster":"教学初版示意"},{"poster":"教学初版示意"})
    add("rules",5,"检查确定性规则","规则检查与模型审美意见分开；教学设定没有越界。",layout,{"hard_rules":40,"issues":[]},{"hard_rules":40})
    unavailable=scenario=="missing_signal"
    initial_score=100.0 if unavailable else 90.67
    add("scores",6,"汇总可用信号","视觉不可用时分母只有 40，规则满分会归一为 100；这不意味着设计完美。" if unavailable else "规则40 + 视觉80×0.35，除以可用权重75，再乘100。注意力在本例缺失。",{"rules":40,"vision":None if unavailable else 80,"attention":None},{"total":initial_score,"available_weight":40 if unavailable else 75},{"evaluation":{"total":initial_score,"available_weight":40 if unavailable else 75}})
    add("human",2,"暂停：等待用户反馈","这是业务中的暂停位置。教学回放在这里也会暂停，点击下一步代表查看示例用户决定。",{"poster":state["poster"],"evaluation":state["evaluation"]},{"status":"waiting_for_human"},{"status":"waiting_for_human"},wait=True)
    instruction="时间地点更醒目，保持背景和活动事实不变"
    add("human",5,"用户提出修改目标","用户给出目标；模型随后在允许范围内选择具体工具。",{"action":"instruct","instruction":instruction},{"next":"react_decide"},{"human_instruction":instruction,"round_number":1,"status":"running"},actor="用户")
    add("checkpoint",3,"在原任务里恢复","保留 brief、布局、引用和任务 ID；不会重新创建背景生成任务。",{"run_id":state["run_id"],"instruction":instruction},{"round_number":1,"tool_calls_in_round":0})
    max_calls=3 if scenario=="budget_limit" else 2 if scenario=="tool_failure" else 1
    for i in range(max_calls):
        fail=scenario=="tool_failure" and i==0
        size=999 if fail else 48+i*2
        decision={"tool_name":"modify_typography","arguments":{"target":"event_info","font_size":size}}
        add("decide",3,f"第 {i+1} 次选择工具","模型响应为预设样例；失败场景故意先给出越界字号。",{"instruction":instruction,"previous_observation":state.get("observation"),"tool_calls":i},decision,{"react_decision":decision},actor="模型响应替身")
        add("execute",2,"校验参数与允许范围","999 超出字号范围，因此不应用修改。" if fail else "参数处于允许范围，仍需保护活动文字与背景。",decision,{"valid":not fail})
        add("locks",5,"保护活动事实和背景","校验并不只看数值；还检查用户要求保留的部分。",{"before":layout,"requested_size":size},{"facts_unchanged":True,"background_unchanged":True})
        if fail:
            observation="工具失败：字号超出允许范围，布局未改变"
        else:
            layout=deepcopy(layout)
            layout["event_info"]["font_size"]=size
            observation=f"活动信息字号改为 {size}；事实与背景不变"
        add("execute",5,"把成功或失败交回模型","工具失败也会消耗尝试次数，并以 Observation 返回。",decision,{"success":not fail,"observation":observation},{"layout":deepcopy(layout),"observation":observation,"tool_calls_in_round":i+1})
    add("decide",2 if max_calls==3 else 4,"达到上限，程序结束本轮" if max_calls==3 else "模型选择结束本轮","达到三个工具时不再请求模型。" if max_calls==3 else "在本教学样例中，模型认为已经完成修改。",{"tool_calls_in_round":max_calls},{"decision":"finish_round"},{"react_decision":{"decision":"finish_round"}},actor="程序" if max_calls==3 else "模型响应替身")
    add("round",1,"轮末统一渲染","前面的工具修改布局参数；这里才生成本轮正式结果。背景引用保持原值。",layout,{"poster":"教学优化版示意"},{"poster":"教学优化版示意"})
    add("round",2,"重新评测","新视觉分数是教学输入，不代表真实设计效果。",{"hard_rules":40,"vision":86,"attention":None},{"total":93.47,"available_weight":75},{"evaluation":{"total":93.47,"available_weight":75}})
    comparable=not unavailable
    add("comparison",3 if comparable else 2,"比较前后条件","本次信号一致，可计算分差，但仍需用户判断。" if comparable else "初版缺视觉信号，当前视觉恢复，综合分不可直接比较。",{"before_weight":40 if unavailable else 75,"after_weight":75},{"comparison":2.8 if comparable else "not_comparable"},{"comparison":2.8 if comparable else "not_comparable"})
    add("human",2,"再次等待用户确认","教学用户接下来选择结束；真实项目最多允许三轮修改。",{"round_number":1,"poster":state["poster"]},{"status":"waiting_for_human"},{"status":"waiting_for_human"},wait=True)
    add("human",4,"用户结束任务","结束权归用户；程序也会在达到轮次上限时收尾。",{"action":"finish"},{"next":"finalize"},actor="用户")
    add("artifacts",5,"保存结果与过程","本教学回放只保存在浏览器状态，不写入 PosterPilot 业务数据。",{"poster":state["poster"],"round_number":1},{"result":"海报、评测、工具轨迹"},{"status":"completed"})
    return {"kind":"teaching", "scenario":scenario,"title":title,"steps":steps,
            "notice":"教学执行回放：依据当前代码控制流编排，模型、检索和图片使用预设响应；不是生产运行记录，不产生模型费用。"}
