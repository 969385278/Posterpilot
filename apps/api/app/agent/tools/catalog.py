"""Code-owned tools only. Publication never imports user-provided code or paths."""

from app.schemas.design_control import BackgroundAdjustmentArguments
from app.schemas.poster_case import CaseSearchArguments
from app.schemas.tool_release import AlignTextGroupArguments, TextOpacityArguments

EXTENSION_SCHEMAS = {
    "set_text_opacity": TextOpacityArguments,
    "align_text_group": AlignTextGroupArguments,
}
BASE_TOOLS = {
    "search_design_knowledge",
    "search_poster_cases",
    "modify_typography",
    "modify_layout",
    "adjust_background",
}
DESCRIPTIONS = {
    "search_design_knowledge": "检索带出处的设计知识；参数 query、target_roles。",
    "search_poster_cases": "按文字及标签查找有来源的视觉案例。",
    "modify_typography": "调整文字字号、颜色、行距、对齐；参数 actions。",
    "modify_layout": "调整文字等非主视觉元素的位置、尺寸；参数 actions。",
    "adjust_background": "基于原始主视觉设置绝对明暗反差或饱和度，不重绘。",
    "set_text_opacity": "设置一至三个文字元素的透明度（0.3 到 1），不改变内容或背景。",
    "align_text_group": "将一至三个文字框的左边、中心或右边对齐参考文字框；保留纵坐标和尺寸。",
}


def tool_definition(name: str) -> dict:
    if name not in DESCRIPTIONS:
        raise ValueError("Unknown registered tool")
    schemas = {
        **EXTENSION_SCHEMAS,
        "adjust_background": BackgroundAdjustmentArguments,
        "search_poster_cases": CaseSearchArguments,
    }
    if name in schemas:
        schema = schemas[name].model_json_schema()
    elif name == "search_design_knowledge":
        schema = {
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string", "minLength": 1},
                "target_roles": {"type": "array", "items": {"type": "string"}},
            },
        }
    else:
        schema = {
            "type": "object",
            "required": ["actions"],
            "properties": {
                "actions": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 3,
                    "items": {
                        "type": "object",
                        "required": ["action", "target_id", "parameters", "reason"],
                        "properties": {
                            "action": {"type": "string"},
                            "target_id": {"type": "string"},
                            "parameters": {"type": "object"},
                            "reason": {"type": "string"},
                        },
                    },
                },
            },
        }
    return {
        "name": name,
        "description": DESCRIPTIONS[name],
        "parameters": schema,
        "bundled": name in BASE_TOOLS,
        "implementation": (
            "apps/api/app/agent/tools/extensions.py"
            if name in EXTENSION_SCHEMAS
            else "apps/api/app/agent/tools/react_tools.py"
        ),
    }


def bundled_catalog() -> list[dict]:
    return [tool_definition(name) for name in sorted(BASE_TOOLS)]
