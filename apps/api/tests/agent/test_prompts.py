from app.agent.prompts.design import build_design_messages
from app.agent.prompts.optimization import build_optimization_messages
from app.agent.prompts.vision_review import build_vision_review_prompt
from app.schemas.brief import PosterBrief


def _brief() -> PosterBrief:
    return PosterBrief.model_validate(
        {
            "poster_type": "cultural_event",
            "topic": "红楼梦研讨分享会",
            "target_audience": "大学生",
            "title": "红楼梦研讨分享会",
            "event_time": "2026年7月20日 19:00",
            "location": "图书馆报告厅",
            "organizer": "文学社",
        }
    )


def test_design_prompt_requires_structured_schema_and_user_facts() -> None:
    messages = build_design_messages(_brief(), knowledge_text="标题要清晰")
    system = str(messages[0]["content"])

    assert "DesignSpec" in system
    assert "不得虚构" in system
    assert "用户事实优先" in system
    assert "3:4" in system
    assert "铺满整张海报" in system
    assert "不要生成文字" in system
    assert "红楼梦研讨分享会" in str(messages[1]["content"])


def test_vision_prompt_describes_deepgaze_as_prediction_not_real_eye_tracking() -> None:
    prompt = build_vision_review_prompt(_brief())

    assert "不是真实用户眼动" in prompt
    assert "JSON" in prompt


def test_optimization_prompt_limits_actions_to_whitelist() -> None:
    messages = build_optimization_messages("标题重叠", knowledge_text="优先修复可读性")

    assert "set_font_size" in str(messages[0]["content"])
    assert "regenerate_visual" in str(messages[0]["content"])
    assert "一轮" in str(messages[0]["content"])
