from typing import Any

from pydantic import ValidationError

from app.providers.vision.base import VisionJsonProvider
from app.schemas.evaluation import VisionIssue, VisionReview


class VisionEvaluator:
    def __init__(self, provider: VisionJsonProvider) -> None:
        self.provider = provider

    async def evaluate(self, *, image_url: str, prompt: str) -> VisionReview:
        for _ in range(2):
            try:
                payload = await self.provider.analyze_json(image_url=image_url, prompt=prompt)
                return self._parse(payload)
            except (KeyError, OSError, RuntimeError, TypeError, ValueError, ValidationError):
                continue
        return VisionReview(
            availability="unavailable",
            error="Vision evaluation provider is unavailable.",
        )

    @staticmethod
    def _parse(payload: dict[str, Any]) -> VisionReview:
        severity_aliases = {
            "低": "low",
            "中": "medium",
            "中等": "medium",
            "高": "high",
            "严重": "critical",
        }
        issues = []
        for raw_issue in payload.get("issues", []):
            issue = dict(raw_issue)
            severity = str(issue.get("severity", "medium")).strip()
            issue["severity"] = severity_aliases.get(severity, severity.lower())
            for field in ("related_principles", "suggested_actions"):
                value = issue.get(field, [])
                if isinstance(value, str):
                    issue[field] = [value]
                elif value is None:
                    issue[field] = []
            issues.append(VisionIssue.model_validate(issue))
        return VisionReview(
            availability="available",
            score=float(payload["score"]),
            summary=str(payload.get("summary", "")),
            issues=issues,
            subject_regions=payload.get("subject_regions", []),
        )
