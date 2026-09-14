from app.providers.llm.base import ChatMessage


def build_optimization_messages(issues_text: str, *, knowledge_text: str) -> list[ChatMessage]:
    system = """
你是海报优化 Agent。只输出 OptimizationPlan JSON，不要 Markdown。
只允许动作：set_position、set_size、set_font_size、set_color、set_line_spacing、
set_alignment、set_opacity、set_brightness、regenerate_visual。
只执行一轮优化：先修复出界、缺失、重叠和可读性，再处理注意力路径、层级、拥挤与色彩。
默认只修改排版；只有视觉问题明确指向主视觉不可修复时才使用 regenerate_visual。
""".strip()
    user = f"待修复问题：\n{issues_text}\n\n可引用知识：\n{knowledge_text}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
