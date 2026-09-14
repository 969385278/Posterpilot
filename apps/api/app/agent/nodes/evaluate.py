import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.agent.nodes.common import with_event
from app.agent.prompts.vision_review import build_vision_review_prompt
from app.agent.state import PosterAgentState
from app.evaluation.deepgaze_client import DeepGazePrediction
from app.evaluation.hard_rules import evaluate_hard_rules
from app.evaluation.report_builder import build_report
from app.evaluation.score_aggregator import aggregate_scores
from app.schemas.evaluation import AttentionPrediction, Fixation, VisionReview
from app.schemas.layout import PosterLayout
from app.schemas.design_control import BackgroundTreatment, DesignControls
from app.evaluation.design_analysis import analyze_design
from app.evaluation.goal_verifier import verify_design_goals


class AttentionClient(Protocol):
    async def predict(
        self,
        *,
        image_bytes: bytes,
        filename: str = "poster.png",
        steps: int = 5,
    ) -> DeepGazePrediction: ...


class VisionReviewer(Protocol):
    async def evaluate(self, *, image_url: str, prompt: str) -> VisionReview: ...


@dataclass(frozen=True)
class EvaluationDependencies:
    deepgaze: AttentionClient | None = None
    vision: VisionReviewer | None = None


async def evaluate_draft(
    state: PosterAgentState,
    *,
    dependencies: EvaluationDependencies | None = None,
    run_directory: Path | str | None = None,
) -> dict[str, object]:
    report = await _evaluate_layout(
        state,
        poster_key="poster_initial_path",
        heatmap_name="attention_initial.png",
        dependencies=dependencies,
        run_directory=run_directory,
    )
    return {
        "evaluation_initial": report,
        **_design_analysis_updates(state, report, initial=True),
        "events": with_event(
            state,
            node="evaluate_draft",
            message="已完成初版硬规则、视觉与注意力评测。",
            payload={
                "total": report.scores.total,
                "available_weight": report.scores.available_weight,
            },
        ),
    }


async def evaluate_optimized(
    state: PosterAgentState,
    *,
    dependencies: EvaluationDependencies | None = None,
    run_directory: Path | str | None = None,
) -> dict[str, object]:
    round_number = state.get("round_number", 0)
    heatmap_name = (
        f"attention_round_{round_number}.png" if round_number else "attention_optimized.png"
    )
    report = await _evaluate_layout(
        state,
        poster_key="poster_optimized_path",
        heatmap_name=heatmap_name,
        dependencies=dependencies,
        run_directory=run_directory,
    )
    return {
        "evaluation_optimized": report,
        **_design_analysis_updates(state, report, initial=False),
        "events": with_event(
            state,
            node="evaluate_optimized",
            message="已按相同标准完成优化版复评。",
            payload={
                "total": report.scores.total,
                "available_weight": report.scores.available_weight,
                "round_number": round_number,
            },
        ),
    }


async def _evaluate_layout(
    state: PosterAgentState,
    *,
    poster_key: str,
    heatmap_name: str,
    dependencies: EvaluationDependencies | None,
    run_directory: Path | str | None,
):
    design_spec = state["design_spec"]
    poster_path = state[poster_key]
    if design_spec is None or not poster_path:
        raise ValueError("design spec and rendered poster are required before evaluation")
    layout = state["layout"] or design_spec.layout
    poster_bytes = Path(poster_path).read_bytes()
    dependencies = dependencies or EvaluationDependencies()
    attention = await _evaluate_attention(
        dependencies.deepgaze,
        poster_bytes=poster_bytes,
        poster_path=Path(poster_path),
        layout=layout,
        heatmap_name=heatmap_name,
        run_directory=run_directory,
    )
    vision = await _evaluate_vision(
        dependencies.vision,
        poster_bytes=poster_bytes,
        brief=state["brief"],
        controls=state.get("design_controls"),
    )
    controls = state.get("design_controls") or DesignControls()
    rule_issues = evaluate_hard_rules(layout, controls)
    scores = aggregate_scores(
        rule_issues=rule_issues,
        vision=vision,
        attention=attention,
        expected_attention_path=controls.attention_priority or design_spec.expected_attention_path,
    )
    report = build_report(rule_issues, attention, vision, scores)
    report.design_goal_context = {
        "adjustments": [goal.model_dump(mode="json") for goal in controls.adjustments],
        "attention_priority": controls.attention_priority or design_spec.expected_attention_path,
    }
    return report


def _design_analysis_updates(state, report, *, initial: bool):
    if not state.get("main_visual_path") or not state.get("rendered_text_facts"):
        return {}
    treatment = state.get("background_treatment") or BackgroundTreatment()
    layout = state["layout"] or state["design_spec"].layout
    analysis = analyze_design(
        layout, main_visual_path=state["main_visual_path"], treatment=treatment,
        text_facts=state["rendered_text_facts"], visual_summary=report.vision.summary,
    )
    update = {"analysis_current": analysis}
    if initial:
        update["analysis_initial"] = analysis
    elif state.get("analysis_before_round") and state.get("round_base_layout"):
        update["goal_verification"] = verify_design_goals(
            before_layout=state["round_base_layout"], after_layout=layout,
            before_analysis=state["analysis_before_round"], after_analysis=analysis,
            controls=state.get("design_controls") or DesignControls(),
            before_treatment=state.get("round_base_treatment") or BackgroundTreatment(),
            after_treatment=treatment,
            attention=report.attention,
            rejection_reason=state.get("round_rejection_reason"),
        )
    return update


async def _evaluate_attention(
    client: AttentionClient | None,
    *,
    poster_bytes: bytes,
    poster_path: Path,
    layout: PosterLayout,
    heatmap_name: str,
    run_directory: Path | str | None,
) -> AttentionPrediction:
    if client is None:
        return AttentionPrediction(
            availability="unavailable",
            error="DeepGaze evaluation is not configured for this run.",
        )
    prediction = await client.predict(
        image_bytes=poster_bytes,
        filename=poster_path.name,
        steps=5,
    )
    attention = prediction.attention.model_copy(deep=True)
    attention.fixations = [_annotate_fixation(fixation, layout) for fixation in attention.fixations]
    attention.predicted_path = _predicted_path(attention.fixations)
    if prediction.heatmap_png is not None and run_directory is not None:
        (Path(run_directory) / heatmap_name).write_bytes(prediction.heatmap_png)
        attention.heatmap_artifact = heatmap_name
    return attention


async def _evaluate_vision(
    reviewer: VisionReviewer | None,
    *,
    poster_bytes: bytes,
    brief,
    controls: DesignControls | None = None,
) -> VisionReview:
    if reviewer is None:
        return VisionReview(
            availability="unavailable",
            error="Vision evaluation is not configured for this run.",
        )
    image_url = f"data:image/png;base64,{base64.b64encode(poster_bytes).decode('ascii')}"
    return await reviewer.evaluate(image_url=image_url, prompt=build_vision_review_prompt(
        brief, controls=controls.model_dump(mode="json") if controls else None,
    ))


def _annotate_fixation(fixation: Fixation, layout: PosterLayout) -> Fixation:
    # Renderer paints the full-bleed visual first, then content in list order.
    # Resolve overlapping AOIs from the last painted content back to the visual.
    # These remain layout-box AOIs, not glyph masks or measured human fixations.
    role = next(
        (
            element.role
            for element in reversed(layout.elements)
            if element.role != "main_visual"
            and element.content
            and element.box.x <= fixation.x <= element.box.x + element.box.width
            and element.box.y <= fixation.y <= element.box.y + element.box.height
        ),
        "main_visual" if any(e.role == "main_visual" for e in layout.elements) else None,
    )
    return fixation.model_copy(update={"aoi_role": role})


def _predicted_path(fixations: list[Fixation]) -> list[str]:
    path: list[str] = []
    for fixation in fixations:
        if fixation.aoi_role and fixation.aoi_role not in path:
            path.append(fixation.aoi_role)
    return path
