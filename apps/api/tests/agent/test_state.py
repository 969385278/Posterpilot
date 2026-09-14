from app.agent.state import initial_agent_state
from app.schemas.brief import PosterBrief


def test_initial_agent_state_preserves_the_validated_brief() -> None:
    brief = PosterBrief.model_validate(
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

    state = initial_agent_state(brief)

    assert state["brief"] == brief
    assert state["events"] == []
    assert state["errors"] == []
    assert state["iteration"] == 0
