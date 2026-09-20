"""A local, single-user curation boundary; not an automatic learning system."""

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from app.core.exceptions import PosterPilotError
from app.evaluation.comparison import compare_reports
from app.persistence.datahub_repository import DataHubRepository
from app.schemas.datahub import (
    CaseNotes,
    EditCaseRequest,
    ExperienceQuery,
    HubAudit,
    HubCase,
    ReviewCaseRequest,
)
from app.schemas.evaluation import EvaluationReport
from app.schemas.layout import PosterLayout


class DataHubService:
    def __init__(self, repository: DataHubRepository, assets: Path, *, include_demo: bool = False):
        self.repository = repository
        self.assets = Path(assets)
        self.assets.mkdir(parents=True, exist_ok=True)
        self.include_demo = include_demo

    def capture(self, run_service, run_id: UUID, *, origin="runtime") -> list[HubCase]:
        run = run_service.require(run_id)
        if run.status not in {"waiting_for_human", "completed", "failed"}:
            raise PosterPilotError("请等待本轮执行结束后再收集。", code="run_busy", status_code=409)
        snapshots = {}
        for number in range(4):
            name = f"experience_round_{number}.json"
            try:
                path = run_service.artifact_path(run_id, name)
            except FileNotFoundError:
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("schema_version") != 1 or payload.get("round_number") != number:
                raise PosterPilotError(
                    "不支持的运行证据格式。", code="invalid_evidence", status_code=422
                )
            PosterLayout.model_validate(payload["layout"])
            EvaluationReport.model_validate(payload["evaluation"])
            snapshots[number] = payload
        if not snapshots:
            raise PosterPilotError(
                "该历史任务没有结构化经验快照；请使用新版完成一次生成。",
                code="evidence_unavailable",
                status_code=409,
            )
        result = []
        for number, after in snapshots.items():
            before = snapshots.get(number - 1)
            image_hash = self._copy_image(run_service, run_id, after["poster_artifact"])
            before_hash = (
                self._copy_image(run_service, run_id, before["poster_artifact"]) if before else None
            )
            comparison = {"outcome": "not_comparable", "delta": None, "reason": "没有前一轮证据。"}
            if before:
                compared = compare_reports(
                    EvaluationReport.model_validate(before["evaluation"]),
                    EvaluationReport.model_validate(after["evaluation"]),
                )
                comparison = {
                    "outcome": compared.outcome,
                    "delta": compared.delta,
                    "reason": compared.reason,
                }
            evidence = {
                "before": before,
                "after": after,
                "comparison": comparison,
                "image_hash": image_hash,
                "before_image_hash": before_hash,
            }
            digest = hashlib.sha256(
                json.dumps(evidence, sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest()
            entry = HubCase(
                run_id=run_id,
                round_number=number,
                origin=origin,
                evidence=evidence,
                evidence_hash=digest,
                image_hash=image_hash,
                before_image_hash=before_hash,
                notes=CaseNotes(
                    title=f"{run.brief.title} · {'初版' if number == 0 else f'第 {number} 轮'}",
                    styles=run.brief.style_preferences,
                    problem=after.get("instruction", "")[:1000],
                ),
                audit=[
                    HubAudit(
                        revision=1,
                        action="capture",
                        note="从运行证据导入，未推断用户接受，未自动发布。",
                    )
                ],
            )
            result.append(self.repository.insert(entry))
        return result

    def _copy_image(self, run_service, run_id, name) -> str:
        path = run_service.artifact_path(run_id, name)
        data = path.read_bytes()
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise PosterPilotError(
                "经验快照需要 PNG 海报。", code="invalid_case_image", status_code=422
            )
        digest = hashlib.sha256(data).hexdigest()
        target = self.assets / f"{digest}.png"
        if not target.exists():
            # Content-addressed immutable copies survive later task cleanup.
            temporary = self.assets / f".{digest}.{uuid4().hex}.tmp"
            try:
                temporary.write_bytes(data)
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
        return digest

    def image_path(self, case_id: UUID, *, before: bool = False) -> Path:
        case = self.repository.get(case_id)
        digest = case.before_image_hash if before else case.image_hash
        if not digest or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise PosterPilotError("图片不存在。", code="case_image_missing", status_code=404)
        path = self.assets / f"{digest}.png"
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise PosterPilotError(
                "案例图片丢失或校验失败。", code="case_image_missing", status_code=409
            )
        return path

    def edit(self, case_id: UUID, request: EditCaseRequest) -> HubCase:
        case = self.repository.get(case_id)
        if request.feedback.verdict != "unknown" and request.feedback.source == "not_collected":
            raise PosterPilotError(
                "明确评价需要注明反馈来源。", code="feedback_source_required", status_code=422
            )
        if case.origin == "offline_demo" and request.feedback.source == "explicit_user":
            # A reviewed demo is still not evidence of live product feedback.
            raise PosterPilotError(
                "离线样例请使用演示反馈标记。", code="demo_feedback_required", status_code=422
            )
        case.notes = request.notes
        case.feedback = request.feedback
        case.status = "candidate"
        return self._save(
            case, request.expected_revision, "edit", "整理内容或反馈后，原审核失效，等待重新审核。"
        )

    def quality_issues(self, case: HubCase) -> list[str]:
        notes = case.notes
        issues = []
        for label, value in (
            ("问题描述", notes.problem),
            ("复用建议", notes.lesson),
            ("适用条件", notes.applicable_when),
            ("限制条件", notes.avoid_when),
        ):
            if not value:
                issues.append(f"缺少{label}")
        if notes.rights != "own_or_authorized" or not notes.rights_note:
            issues.append("尚未确认图片与反馈的使用授权")
        if case.feedback.verdict == "rejected":
            issues.append("用户明确拒绝的结果只保留分析，不作为正向经验发布")
        if case.round_number > 0 and not case.evidence.get("before"):
            issues.append("缺少修改前证据，不能发布优化经验")
        after = case.evidence["after"]
        if any(
            issue.get("severity") in {"high", "critical"}
            for issue in after["evaluation"].get("rule_issues", [])
        ):
            issues.append("存在未解决的严重版式规则问题")
        if any(
            check.get("status") == "failed"
            for check in (after.get("goal_verification") or {}).get("checks", [])
        ):
            issues.append("当前修改目标仍有未通过项")
        try:
            self.image_path(case.id)
            if case.before_image_hash:
                self.image_path(case.id, before=True)
        except PosterPilotError:
            issues.append("来源图片缺失或校验失败")
        return issues

    def review(self, case_id: UUID, request: ReviewCaseRequest) -> HubCase:
        case = self.repository.get(case_id)
        if request.action == "approve":
            issues = self.quality_issues(case)
            if issues:
                raise PosterPilotError("；".join(issues), code="case_quality_gate", status_code=422)
            case.status = "approved"
        elif request.action == "reject":
            case.status = "rejected"
        else:
            case.status = "withdrawn"
        return self._save(case, request.expected_revision, request.action, request.note)

    def _save(self, case, expected_revision, action, note):
        case.revision = expected_revision + 1
        case.updated_at = datetime.now(UTC)
        case.audit.append(
            HubAudit(
                revision=case.revision,
                action=action,
                note=note,
                snapshot={
                    "notes": case.notes.model_dump(mode="json"),
                    "feedback": case.feedback.model_dump(mode="json"),
                    "status": case.status,
                },
            )
        )
        return self.repository.replace(case, expected_revision=expected_revision)

    def retrieve(self, request: ExperienceQuery) -> list[dict]:
        """Small-corpus lexical retrieval; no invented semantic/visual embedding claims."""
        clean = re.sub(r"\s+", "", request.query.lower())
        grams = {clean[i : i + 2] for i in range(len(clean) - 1)} or {clean}
        ranked = []
        for case in self.repository.list(status="approved"):
            if case.run_id == request.exclude_run_id:
                continue
            if case.origin == "offline_demo" and not request.include_demo:
                continue
            after = case.evidence["after"]
            if after["brief"]["poster_type"] != request.poster_type or self.quality_issues(case):
                continue
            text = " ".join(
                [
                    case.notes.problem,
                    case.notes.lesson,
                    case.notes.applicable_when,
                    *case.notes.styles,
                ]
            ).lower()
            relevance = sum(gram in text for gram in grams) / max(len(grams), 1)
            if relevance < 0.08:
                continue
            # Facts and raw old tool arguments intentionally do not cross the task boundary.
            context = {
                "case_id": str(case.id),
                "revision": case.revision,
                "source": f"/api/v1/datahub/cases/{case.id}",
                "origin": case.origin,
                "problem": case.notes.problem,
                "lesson": case.notes.lesson,
                "applicable_when": case.notes.applicable_when,
                "avoid_when": case.notes.avoid_when,
                "styles": case.notes.styles,
                "canvas": after["brief"]["canvas"],
                "title_length": len(after["brief"]["title"]),
                "feedback": case.feedback.verdict,
                "comparison": case.evidence["comparison"],
                "warning": (
                    "单次案例，不是普遍规则；需要适配当前文字、画布和锁定条件，"
                    "不得直接复制旧参数。"
                ),
            }
            ranked.append((relevance, case.created_at, str(case.id), context, case.image_hash))
        ranked.sort(key=lambda item: (-item[0], item[1], item[2]))
        result, seen_images = [], set()
        for item in ranked:
            if item[4] not in seen_images:
                result.append(item[3])
                seen_images.add(item[4])
            if len(result) >= request.limit:
                break
        return result

    def stats(self) -> dict:
        cases = self.repository.list()
        counts = {
            state: sum(case.status == state for case in cases)
            for state in ("candidate", "approved", "rejected", "withdrawn")
        }
        return {
            "total": len(cases),
            "statuses": counts,
            "feedback": {
                verdict: sum(case.feedback.verdict == verdict for case in cases)
                for verdict in ("unknown", "accepted", "rejected")
            },
            "offline_demo": sum(case.origin == "offline_demo" for case in cases),
            "note": "统计是记录数量，不代表实际用户数、因果提升或泛化效果。",
        }
