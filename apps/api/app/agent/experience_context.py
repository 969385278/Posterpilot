import logging
from uuid import UUID

from app.schemas.datahub import ExperienceQuery

logger = logging.getLogger(__name__)


def retrieve_experience(state, source, *, optimization: bool) -> list[dict]:
    if source is None or not state["brief"].use_case_memory:
        return []
    brief = state["brief"]
    query = state.get("human_instruction", "") if optimization else ""
    query = query or " ".join([brief.topic, *brief.style_preferences, brief.notes]) or brief.title
    try:
        return source.retrieve(
            ExperienceQuery(
                query=query[:1000],
                poster_type=brief.poster_type,
                exclude_run_id=UUID(state["run_id"]) if state.get("run_id") else None,
                include_demo=source.include_demo,
            )
        )
    except Exception:
        logger.warning("Experience retrieval unavailable; using original workflow", exc_info=True)
        return []
