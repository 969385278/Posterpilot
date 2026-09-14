"""A shared source for the visual Wiki and bounded, text-based case retrieval.

This is intentionally not image-embedding search. Explicit selections bypass
retrieval ranking entirely, and only selected dimensions enter the generation.
"""

import json
import re
from pathlib import Path

from app.core.paths import PROJECT_ROOT
from app.schemas.design_control import ReferenceSelection
from app.schemas.poster_case import PosterCase


class CaseRepository:
    def __init__(self, directory: Path | str | None = None):
        self.directory = Path(directory) if directory is not None else PROJECT_ROOT / "data" / "knowledge" / "cases"

    def list_cases(self, *, query: str = "", style: str = "", limit: int = 30) -> list[PosterCase]:
        path = self.directory / "catalog.json"
        if not path.is_file():
            return []
        cases = [PosterCase.model_validate(item) for item in json.loads(path.read_text(encoding="utf-8"))]
        ids = [case.id for case in cases]
        if len(ids) != len(set(ids)):
            raise ValueError("case catalog contains duplicate ids")
        eligible = [case for case in cases if case.status == "curated" and case.user_acceptance != "rejected" and (not style or style in case.styles)]
        if query.strip():
            scored = [(self._score(query, case), case) for case in eligible]
            eligible = [case for score, case in sorted(scored, key=lambda item: (-item[0], item[1].id)) if score > 0]
        return eligible[:max(1, min(limit, 100))]

    def get(self, case_id: str) -> PosterCase:
        match = next((case for case in self.list_cases(limit=100) if case.id == case_id), None)
        if match is None:
            raise ValueError(f"海报案例不存在或尚未整理：{case_id}")
        return match

    def image_path(self, case_id: str) -> Path:
        case = self.get(case_id)
        root = (self.directory / "images").resolve()
        path = (root / case.image_asset).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise FileNotFoundError("case image is unavailable")
        return path

    def resolve_selections(self, selections: list[ReferenceSelection]) -> list[dict]:
        result = []
        used = set()
        for selection in selections:
            conflict = used.intersection(selection.aspects)
            if conflict:
                raise ValueError("每个参考维度只能选择一个案例：" + ", ".join(sorted(conflict)))
            used.update(selection.aspects)
            case = self.get(selection.case_id)
            self.image_path(case.id)
            result.append({
                "case_id": case.id,
                "title": case.title,
                "selected_features": {aspect: case.features[aspect] for aspect in selection.aspects},
                "palette": case.palette if "palette" in selection.aspects else [],
                "suggested_priority": case.suggested_priority if "hierarchy" in selection.aspects else [],
                "render_hints": {
                    **({"title_font_style": case.title_font_style} if "typography" in selection.aspects else {}),
                    **({"composition_preset": case.composition_preset} if "composition" in selection.aspects else {}),
                },
                "source_url": str(case.source.source_url),
                "analysis_basis": case.analysis_basis,
                "cautions": case.cautions,
            })
        return result

    @staticmethod
    def _score(query: str, case: PosterCase) -> float:
        clean = re.sub(r"\s+", "", query.lower())
        text = " ".join([case.title, *case.styles, *case.scenarios, *case.features.values()]).lower()
        pairs = {clean[i:i + 2] for i in range(max(0, len(clean) - 1))} or {clean}
        overlap = sum(pair in text for pair in pairs) / max(1, len(pairs))
        exact_tags = sum(tag.lower() in clean for tag in [*case.styles, *case.scenarios])
        return overlap + exact_tags
