from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.agent.state import initial_agent_state
from app.core.exceptions import PosterPilotError
from app.datahub_demo import create_app
from app.poster.template_loader import TemplateLoader
from app.schemas.brief import PosterBrief
from app.schemas.datahub import ReviewCaseRequest
from app.schemas.decision import CreateDecisionCard, DecisionPolicy
from tests.services.test_datahub import approve, curate
from tests.services.test_user_memory import add


def test_real_graph_memory_and_reviewed_decision_reuse(tmp_path):
    app = create_app(tmp_path / "demo")
    with TestClient(app) as client:
        runs = app.state.run_service
        memory = add(runs.memory, key="title_font", value="standard")

        def generate(title, use_memory=False):
            response = client.post(
                "/api/v1/runs",
                json={
                    "title": title,
                    "event_time": "周六下午",
                    "location": "图书馆",
                    "attention_layout": False,
                    "use_user_memory": use_memory,
                },
            )
            assert response.status_code == 202, response.text
            run_id = response.json()["id"]
            pending = client.get(f"/api/v1/runs/{run_id}/pending")
            assert pending.status_code == 200, client.get(f"/api/v1/runs/{run_id}").text
            return run_id, pending.json()

        source_id, pending = generate("春日诗会", True)
        title = next(item for item in pending["layout"]["elements"] if item["role"] == "title")
        assert title["font_family"] == "reference-sans-bold"
        snapshot = client.get(f"/api/v1/runs/{source_id}/artifacts/experience_round_0.json").json()
        assert snapshot["design_spec"]["layout"] == snapshot["layout"]
        assert snapshot["user_context"]["preferences"]["title_font"]["id"] == memory["id"]
        # Use a separate source with the original fixture typography for the goal benchmark.
        source_id, _ = generate("春日诗会")
        response = client.post(
            f"/api/v1/runs/{source_id}/decisions",
            json={
                "action": "instruct",
                "expected_round_number": 0,
                "instruction": "标题不醒目，增强标题",
                "controls": {
                    "adjustments": [
                        {"trait": "title_emphasis", "direction": "strengthen", "strength": 0.1}
                    ]
                },
            },
        )
        assert response.status_code == 202, response.text
        source = next(
            case
            for case in runs.datahub.repository.list(run_id=UUID(source_id))
            if case.round_number == 1
        )
        assert source.evidence["after"]["goal_verification"]["outcome"] == "met"
        source = approve(runs.datahub, curate(runs.datahub, source))
        policy = DecisionPolicy(
            title="短标题层级",
            problem="标题不醒目",
            applicable_when="短标题未锁定",
            avoid_when="长标题或文字锁定",
            poster_types=["cultural_event"],
            required_roles=["title"],
            trigger_terms=["标题不醒目"],
            excluded_terms=["不要放大"],
            candidate_tools=["modify_typography"],
        )
        cards = runs.datahub.decisions
        card = cards.create(CreateDecisionCard(source_case_id=source.id, policy=policy))
        state = initial_agent_state(PosterBrief(title="另一个活动"))
        state["layout"] = TemplateLoader().instantiate("cultural_event", state["brief"])
        state["human_instruction"] = "标题不醒目"
        assert cards.retrieve(state) == []
        card = cards.review(
            card.id, ReviewCaseRequest(expected_revision=1, action="approve", note="测试审核")
        )
        with pytest.raises(PosterPilotError) as stale:
            cards.review(
                card.id,
                ReviewCaseRequest(
                    expected_revision=1,
                    action="withdraw",
                    note="过期提交",
                ),
            )
        assert stale.value.code == "stale_decision_revision"
        assert cards.retrieve(state)[0]["card_id"] == str(card.id)
        assert cards.retrieve(state, available_tools={"adjust_background"}) == []
        state["run_id"] = source_id
        assert cards.retrieve(state) == []
        state["run_id"] = None
        state["human_instruction"] = "标题不醒目，但不要放大"
        assert cards.retrieve(state) == []
        new_id, _ = generate("秋日读诗")
        response = client.post(
            f"/api/v1/runs/{new_id}/decisions",
            json={
                "action": "instruct",
                "expected_round_number": 0,
                "instruction": "标题不醒目",
            },
        )
        assert response.status_code == 202
        evidence = client.get(f"/api/v1/runs/{new_id}/artifacts/experience_round_1.json").json()
        assert evidence["decision_card_references"][0]["card_id"] == str(card.id)
        # A source change disables a published card immediately, without deleting history.
        runs.datahub.review(
            source.id,
            ReviewCaseRequest(
                expected_revision=source.revision,
                action="withdraw",
                note="来源撤回测试",
            ),
        )
        state["human_instruction"] = "标题不醒目"
        assert cards.retrieve(state) == []
        assert cards.repository.get(card.id).audit[-1].action == "approve"
