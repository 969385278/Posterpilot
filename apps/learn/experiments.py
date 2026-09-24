"""Fixed local experiments. No arbitrary code, network, secrets or business writes.

Repository experiments compile allowlisted, unchanged function ASTs from disk.
Import-time application startup is deliberately excluded. SimpleNamespace replaces
data containers only; this is not a full production graph or a Pydantic test.
"""
import __future__
import ast
import hashlib
import math
import re
import sys
from pathlib import Path
from types import SimpleNamespace

from catalog import ROOT
from line_notes import explain


LABS = [
    {"id":"filter", "node":"filter", "title":"筛选知识：实际运行仓库函数", "kind":"repository",
     "description":"调整审核状态、使用意图和区域，观察原函数保留哪些卡片。数据使用教学容器。",
     "defaults":{"intent":"generation", "target_role":"event_info", "include_candidates":False},
     "fields":[{"key":"intent","label":"使用意图","type":"select","options":["generation","optimization","evaluation"]},
               {"key":"target_role","label":"目标区域","type":"select","options":["event_info","title","main_visual"]},
               {"key":"include_candidates","label":"显式允许待审核卡片（对照实验）","type":"checkbox"}]},
    {"id":"similarity", "node":"bigrams", "title":"两个字一组：实际运行相似度函数", "kind":"repository",
     "description":"输入两段短文本，进入 normalize、bigrams、Dice 和混合评分，查看真实局部变量。",
     "defaults":{"left":"摄影展", "right":"摄影活动", "vector_score":0.8},
     "fields":[{"key":"left","label":"知识文本","type":"text"},{"key":"right","label":"检索问题","type":"text"},
               {"key":"vector_score","label":"语义分数（教学输入，不是实际向量召回）","type":"number","min":0,"max":1,"step":0.05}]},
    {"id":"scores", "node":"scores", "title":"可用信号：实际运行评分函数", "kind":"repository",
     "description":"切换视觉和注意力信号，观察分母如何变化。模型评分由你输入，绝不发出模型请求。",
     "defaults":{"vision_available":True,"vision_score":80,"attention_available":False,"attention_match":True,"high_issue":False},
     "fields":[{"key":"vision_available","label":"视觉信号可用","type":"checkbox"},{"key":"vision_score","label":"视觉模型分数（教学输入）","type":"number","min":0,"max":100,"step":1},
               {"key":"attention_available","label":"注意力信号可用","type":"checkbox"},{"key":"attention_match","label":"预测注意顺序匹配目标","type":"checkbox"},
               {"key":"high_issue","label":"存在一个 high 级版式问题","type":"checkbox"}]},
    {"id":"budget", "node":"decide", "title":"拿掉工具上限，会发生什么？", "kind":"teaching",
     "description":"教学代码对照：假定模型持续请求工具。两组只改变次数约束，最多观察六次，避免真的无限循环。",
     "defaults":{"limit":3,"remove_limit":False},
     "fields":[{"key":"limit","label":"正常工具上限","type":"number","min":1,"max":5,"step":1},{"key":"remove_limit","label":"移除业务工具上限","type":"checkbox"}]},
    {"id":"revision", "node":"activities", "title":"活动改期：旧素材还能被返回吗？", "kind":"planned",
     "description":"DesignHub 规划模拟，没有调用未实现的业务服务。对照是否检查活动修订。",
     "defaults":{"current_revision":2,"check_revision":True},
     "fields":[{"key":"current_revision","label":"当前活动修订","type":"number","min":1,"max":3,"step":1},{"key":"check_revision","label":"检查素材绑定的活动修订","type":"checkbox"}]}
]


def safe(value, depth=0):
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return round(value, 6) if math.isfinite(value) else str(value)
    if isinstance(value, str):
        return value[:300]
    if depth > 4:
        return "…"
    if isinstance(value, dict):
        return {str(k):safe(v, depth+1) for k,v in list(value.items())[:25] if not str(k).startswith("__")}
    if isinstance(value, (list, tuple)):
        return [safe(v, depth+1) for v in value[:25]]
    if isinstance(value, (set, frozenset)):
        return sorted(safe(v, depth+1) for v in list(value)[:25])
    if isinstance(value, SimpleNamespace):
        return safe(vars(value), depth+1)
    if callable(value):
        return "<教学数据读取函数>"
    return "<" + type(value).__name__ + ">"


def load_functions(relative, names, globals_=None, methods=()):
    path = ROOT / relative
    text = path.read_text(encoding="utf-8-sig")
    module = ast.parse(text, filename=str(path))
    selected = [n for n in module.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names]
    for cls_name, method_name in methods:
        cls = next(n for n in module.body if isinstance(n, ast.ClassDef) and n.name == cls_name)
        selected.append(next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == method_name))
    namespace = {"re":re, **(globals_ or {})}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), "exec",
                 flags=__future__.annotations.compiler_flag), namespace)
    return namespace, str(path), text


def capture(filename, text, action):
    trace, stack = [], []
    source_lines = text.splitlines()
    def tracer(frame, event, arg):
        if frame.f_code.co_filename != filename:
            return None
        if len(trace) >= 1600:
            raise ValueError("教学轨迹过长，请缩短输入")
        name = frame.f_code.co_name
        if event == "call":
            stack.append(name)
        if event in {"call", "line", "return", "exception"}:
            line = frame.f_lineno
            trace.append(dict(event=event, function=name, line=line,
                code=source_lines[line-1] if 0 < line <= len(source_lines) else "",
                locals=safe(frame.f_locals), stack=list(stack),
                returned=safe(arg) if event == "return" else None,
                explanation={"call":"进入函数：参数已经传入。", "line":"高亮行即将执行；这里显示进入该行时的变量。点击下一步观察变化。", "return":"函数返回：查看返回值，并回到调用它的位置。", "exception":"函数触发异常；查看输入与当前语句。"}[event]))
        if event == "return" and stack:
            stack.pop()
        return tracer
    previous = sys.gettrace()
    try:
        sys.settrace(tracer)
        result = action()
    finally:
        sys.settrace(previous)
    return result, trace


def number(values, key, low, high, integer=False):
    v = values.get(key)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not low <= v <= high:
        raise ValueError(f"{key} 必须在 {low}～{high} 之间")
    if integer and int(v) != v:
        raise ValueError(key + " 必须为整数")
    return int(v) if integer else float(v)


def boolean(values, key):
    if not isinstance(values.get(key), bool):
        raise ValueError(key + " 必须为 true 或 false")
    return values[key]


def budget_experiment(limit, remove_limit):
    calls = []
    for attempt in range(6):
        if not remove_limit and len(calls) >= limit:
            return {"calls": calls, "stopped_by": "业务工具上限"}
        calls.append({"attempt": attempt + 1, "tool": "modify_typography"})
    return {"calls": calls, "stopped_by": "教学观察上限；真实无约束循环仍可能继续"}


def revision_experiment(current_revision, check_revision):
    assets = [
        {"id": "旧正式图", "approved": True, "revision": 1},
        {"id": "新正式图", "approved": True, "revision": 2},
        {"id": "未审核草稿", "approved": False, "revision": 2},
    ]
    visible = []
    for asset in assets:
        if not asset["approved"]:
            continue
        if check_revision and asset["revision"] != current_revision:
            continue
        visible.append(asset["id"])
    return visible


def run_lab(lab_id, values):
    lab = next((l for l in LABS if l["id"] == lab_id), None)
    if not lab or not isinstance(values, dict):
        raise ValueError("未知实验或输入格式不正确")
    if set(values) - set(lab["defaults"]):
        raise ValueError("包含未支持的输入字段")
    v = {**lab["defaults"], **values}
    source_path = ""
    if lab_id == "similarity":
        for key in ("left", "right"):
            if not isinstance(v[key], str) or len(v[key]) > 80:
                raise ValueError("文本最多 80 个字符")
        vector = number(v, "vector_score", 0, 1)
        source_path = "apps/api/app/rag/reranker.py"
        ns, filename, text = load_functions(source_path, {"bigram_dice", "_normalize", "_bigrams", "hybrid_similarity"})
        def action():
            lexical = ns["bigram_dice"](v["left"], v["right"])
            return {"lexical_score":lexical,"combined_score":ns["hybrid_similarity"](vector, lexical)}
        caveat = "执行仓库原函数；vector_score 是教学输入，没有执行 embedding 或向量库查询。"
    elif lab_id == "filter":
        if v["intent"] not in {"generation","optimization","evaluation"} or v["target_role"] not in {"event_info","title","main_visual"}:
            raise ValueError("用途或区域不在教学选项中")
        include = boolean(v, "include_candidates")
        cards = [
            SimpleNamespace(id="A-活动信息规则", review_status="approved", intents=["generation"],target_roles=["time_venue"]),
            SimpleNamespace(id="B-待审核信息规则", review_status="candidate", intents=["generation"],target_roles=["event_info"]),
            SimpleNamespace(id="C-标题优化规则", review_status="approved", intents=["optimization"],target_roles=["title"]),
            SimpleNamespace(id="D-通用规则", review_status="approved", intents=[],target_roles=["any"]),
            SimpleNamespace(id="E-已拒绝规则", review_status="rejected", intents=[],target_roles=[]),
        ]
        source_path = "apps/api/app/rag/retriever.py"
        source_text = (ROOT/source_path).read_text(encoding="utf-8-sig")
        tree = ast.parse(source_text)
        alias_node = next(n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t,ast.Name) and t.id == "_ROLE_ALIASES" for t in n.targets))
        aliases = ast.literal_eval(alias_node.value)
        ns, filename, text = load_functions(source_path, {"_expand_roles"}, {"_ROLE_ALIASES":aliases}, methods=[("KnowledgeRetriever","_filter_candidates")])
        request = SimpleNamespace(intent=v["intent"],target_roles=[v["target_role"]],include_candidates=include)
        holder = SimpleNamespace(repository=SimpleNamespace(list_cards=lambda:cards))
        action = lambda: [c.id for c in ns["_filter_candidates"](holder, request)]
        v = {**v, "cards":safe(cards)}
        caveat = "执行仓库原筛选函数；request 与卡片使用教学数据容器，未经过完整 Schema，也未调用向量库。"
    elif lab_id == "scores":
        score = number(v, "vision_score", 0, 100)
        va = boolean(v, "vision_available")
        aa = boolean(v, "attention_available")
        match = boolean(v, "attention_match")
        issue = boolean(v, "high_issue")
        source_path = "apps/api/app/evaluation/score_aggregator.py"
        text_ = (ROOT/source_path).read_text(encoding="utf-8-sig")
        penalties = ast.literal_eval(next(n.value for n in ast.parse(text_).body if isinstance(n, ast.Assign) and any(isinstance(t,ast.Name) and t.id=="_SEVERITY_PENALTIES" for t in n.targets)))
        ns, filename, text = load_functions(source_path, {"aggregate_scores","_vision_score","_attention_score"},
            {"_SEVERITY_PENALTIES":penalties,"ScoreBreakdown":lambda **kw:kw})
        action = lambda: ns["aggregate_scores"](rule_issues=[SimpleNamespace(severity="high")] if issue else [],
            vision=SimpleNamespace(availability="available" if va else "unavailable",score=score),
            attention=SimpleNamespace(availability="available" if aa else "unavailable",predicted_path=["title","event_info"] if match else ["main_visual"]),
            expected_attention_path=["title","event_info"])
        caveat = "执行仓库原评分函数；模型评分和注意顺序为教学输入，数据容器与返回模型使用轻量替身，不是真实视觉推理。"
    else:
        filename = str(__file__)
        text = Path(filename).read_text(encoding="utf-8")
        source_path = "apps/learn/experiments.py"
        if lab_id == "budget":
            limit = number(v,"limit",1,5,True)
            removed = boolean(v,"remove_limit")
            action = lambda: budget_experiment(limit, removed)
            caveat = "这是真实执行的教学函数，不是仓库 Agent。最多观察六次，不会调用模型或真实工具。"
        else:
            revision = number(v,"current_revision",1,3,True)
            checked = boolean(v,"check_revision")
            action = lambda: revision_experiment(revision, checked)
            caveat = "真实执行规划示例；DesignHub 业务尚未实现，本实验不能证明它已经具备版本失效能力。"
    result, trace = capture(filename, text, action)
    # Only show traced functions, keeping original file line numbers.
    lines = sorted(set(t["line"] for t in trace))
    start, end = max(1,min(lines)-1), max(lines)+1
    if lab_id in {"budget","revision"}:
        fn = budget_experiment if lab_id == "budget" else revision_experiment
        func = next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name==fn.__name__)
        start, end = func.lineno, func.end_lineno
        trace = [t for t in trace if t["function"]==fn.__name__]
        for event in trace:
            event["stack"] = [fn.__name__]
    for event in trace:
        event["explanation"] = explain(event)
    return dict(lab=lab_id, node=lab["node"], kind=lab["kind"], input=safe(v), output=safe(result),
        steps=trace, source=dict(path=source_path, start=start, end=end,
            code="\n".join(text.splitlines()[start-1:end]),sha256=hashlib.sha256((ROOT/source_path).read_bytes()).hexdigest()),
        caveat=caveat)
