"""Only curriculum-listed source files are readable through the learning API."""
import ast
import hashlib
from pathlib import Path

from catalog import NODES, ROOT


def source_for(node_id):
    node = next((n for n in NODES if n["id"] == node_id), None)
    if not node or not node["source"]:
        raise ValueError("这个模块没有对应源码")
    relative = node["source"]
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT) or path.suffix not in {".py", ".tsx", ".ts", ".md"}:
        raise ValueError("不允许读取这个文件")
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    start, end = 1, len(lines)
    if path.suffix == ".py" and node["symbol"]:
        current = ast.parse(text).body
        found = None
        for part in node["symbol"].split("."):
            found = next((x for x in current if isinstance(x, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and x.name == part), None)
            if found is None:
                raise ValueError("源码符号已变化，请更新学习内容：" + node["symbol"])
            current = found.body
        start, end = found.lineno, found.end_lineno
    return dict(path=relative, symbol=node["symbol"], start=start, end=end,
                code="\n".join(lines[start-1:end]), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                status=node["status"], full_code=text if path.suffix == ".py" else None)


def validate_sources():
    return [source_for(n["id"]) for n in NODES if n["source"]]
