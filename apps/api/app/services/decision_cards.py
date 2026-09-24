from uuid import UUID

from app.core.exceptions import PosterPilotError
from app.persistence.decision_repository import DecisionRepository
from app.schemas.datahub import HubAudit, ReviewCaseRequest
from app.schemas.decision import CreateDecisionCard, DecisionCard, EditDecisionCard


class DecisionCardService:
    def __init__(self, hub):
        self.hub = hub
        self.repository = DecisionRepository(hub.repository.database)

    def create(self, request: CreateDecisionCard) -> DecisionCard:
        source = self.hub.repository.get(request.source_case_id)
        card = DecisionCard(
            source_case_id=source.id,
            source_revision=source.revision,
            evidence_hash=source.evidence_hash,
            source_run_id=source.run_id,
            origin=source.origin,
            policy=request.policy,
            audit=[
                HubAudit(
                    revision=1,
                    action="create",
                    note="从来源案例整理，等待人工审核",
                    snapshot={
                        "policy": request.policy.model_dump(mode="json"),
                        "source_revision": source.revision,
                        "evidence_hash": source.evidence_hash,
                    },
                )
            ],
        )
        self._require_quality(card)
        return self.repository.insert(card)

    def quality_issues(self, card: DecisionCard) -> list[str]:
        issues = []
        try:
            source = self.hub.repository.get(card.source_case_id)
        except PosterPilotError:
            return ["来源案例已不存在"]
        if (
            source.status != "approved"
            or source.revision != card.source_revision
            or source.evidence_hash != card.evidence_hash
        ):
            issues.append("来源案例未发布、已撤回或版本发生变化，需要重新整理")
        issues.extend(self.hub.quality_issues(source))
        after = source.evidence["after"]
        successful = {
            trace["tool_name"] for trace in after.get("tool_traces", []) if trace.get("success")
        }
        if not set(card.policy.candidate_tools).issubset(successful):
            issues.append("候选工具必须有来源轮次中的成功执行记录")
        if (after.get("goal_verification") or {}).get("outcome") != "met":
            issues.append("来源轮次没有通过修改目标验收，不能作为正向决策经验")
        if any(not term.strip() for term in card.policy.trigger_terms + card.policy.excluded_terms):
            issues.append("触发词和排除词不能为空")
        if after["brief"]["poster_type"] not in card.policy.poster_types:
            issues.append("适用场景必须包含来源场景")
        if set(card.policy.verification_rules) != {
            "goals_met",
            "locks_preserved",
            "no_critical_rules",
        }:
            issues.append("决策卡不能省略目标、锁定条件或严重规则验收")
        return issues

    def _require_quality(self, card):
        issues = self.quality_issues(card)
        if issues:
            raise PosterPilotError("；".join(issues), code="decision_quality_gate", status_code=422)

    def edit(self, card_id: UUID, request: EditDecisionCard):
        card = self.repository.get(card_id)
        source = self.hub.repository.get(card.source_case_id)
        card.policy = request.policy
        card.source_revision = source.revision
        card.evidence_hash = source.evidence_hash
        card.status = "candidate"
        self._require_quality(card)
        return self._save(card, request.expected_revision, "edit", "修改后需要重新审核")

    def review(self, card_id: UUID, request: ReviewCaseRequest):
        card = self.repository.get(card_id)
        if request.action == "approve":
            self._require_quality(card)
        card.status = {"approve": "approved", "reject": "rejected", "withdraw": "withdrawn"}[
            request.action
        ]
        return self._save(card, request.expected_revision, request.action, request.note)

    def _save(self, card, revision, action, note):
        card.revision = revision + 1
        card.audit.append(
            HubAudit(
                revision=card.revision,
                action=action,
                note=note,
                snapshot={
                    "policy": card.policy.model_dump(mode="json"),
                    "source_revision": card.source_revision,
                    "status": card.status,
                },
            )
        )
        return self.repository.replace(card, expected_revision=revision)

    def retrieve(self, state: dict, *, available_tools: set[str] | None = None) -> list[dict]:
        if not state["brief"].use_case_memory:
            return []
        brief = state["brief"]
        query = state.get("human_instruction", "").lower()
        layout = state.get("layout")
        roles = {item.role for item in layout.elements} if layout else set()
        ranked = []
        for card in self.repository.list(approved_only=True):
            policy = card.policy
            if str(card.source_run_id) == str(state.get("run_id")):
                continue
            if card.origin == "offline_demo" and not self.hub.include_demo:
                continue
            if (
                brief.poster_type not in policy.poster_types
                or not set(policy.required_roles) <= roles
            ):
                continue
            if any(term.lower() in query for term in policy.excluded_terms):
                continue
            matched = [term for term in policy.trigger_terms if term.lower() in query]
            if not matched or self.quality_issues(card):
                continue
            tools = [
                name
                for name in policy.candidate_tools
                if available_tools is None or name in available_tools
            ]
            if not tools:
                continue
            context = {
                "card_id": str(card.id),
                "revision": card.revision,
                "source_case_id": str(card.source_case_id),
                "source_revision": card.source_revision,
                "source": f"/api/v1/datahub/decisions/{card.id}",
                "problem": policy.problem,
                "applicable_when": policy.applicable_when,
                "avoid_when": policy.avoid_when,
                "candidate_tools": tools,
                "verification_rules": policy.verification_rules,
                "matched_terms": matched,
                "note": "仅调整候选工具优先级；当前约束、预算和执行后的验收仍必须满足",
            }
            ranked.append((len(matched), str(card.id), context))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        return [item[2] for item in ranked[:3]]
