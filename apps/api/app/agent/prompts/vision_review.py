from app.schemas.brief import PosterBrief


def build_vision_review_prompt(brief: PosterBrief, *, controls: dict | None = None) -> str:
    return (
        "你是海报视觉评审。只输出 JSON，字段为 score、summary、issues、subject_regions。"
        "issues 每项包含 problem、reason、severity、related_principles、suggested_actions。"
        "subject_regions 标出不应被文字遮挡的主要人物/物体的粗略包围框（不包括文字），最多6个，"
        "每项为 x,y,width,height，均为0到1归一化坐标且不得越界；无法判断返回空数组，不编造主体。"
        "以用户提供的活动事实核对海报内容，不得补充不存在的信息。"
        f"活动事实：{brief.model_dump_json()}。"
        f"本轮用户设计目标与保留条件：{controls or {}}。"
        "根据用户选择判断，不把强对比、高饱和或标题优先一律当作优点；用户要求减弱时应尊重该方向。"
        "DeepGaze 输出仅是模型预测的视觉注意力，不是真实用户眼动；不得把它表述为观众行为。"
    )
