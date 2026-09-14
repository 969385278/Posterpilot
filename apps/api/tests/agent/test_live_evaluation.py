from pathlib import Path

from app.agent.nodes.evaluate import EvaluationDependencies, evaluate_draft
from app.agent.nodes.generate_visual import generate_visual
from app.agent.nodes.render_draft import render_draft
from app.evaluation.deepgaze_client import DeepGazePrediction
from app.poster.renderer import PosterRenderer
from app.schemas.evaluation import AttentionPrediction, Fixation, VisionReview
from tests.agent.test_rendering_nodes import FakeImageProvider, _state


class FakeDeepGazeClient:
    async def predict(self, *, image_bytes: bytes, filename: str, steps: int) -> DeepGazePrediction:
        assert image_bytes
        assert filename == "poster_initial.png"
        assert steps == 5
        return DeepGazePrediction(
            availability="available",
            attention=AttentionPrediction(
                availability="available",
                model="fake-deepgaze",
                device="cpu",
                fixations=[Fixation(x=0.2, y=0.1, order=1)],
                inference_ms=2,
            ),
            heatmap_png=b"heatmap",
        )


class FakeVisionEvaluator:
    async def evaluate(self, *, image_url: str, prompt: str) -> VisionReview:
        assert image_url.startswith("data:image/png;base64,")
        assert "不是真实用户眼动" in prompt
        return VisionReview(availability="available", score=82, summary="视觉层级清晰")


async def test_evaluation_saves_heatmap_and_combines_available_evaluators(tmp_path: Path) -> None:
    state = _state()
    generated = await generate_visual(
        state,
        image_provider=FakeImageProvider(),
        run_directory=tmp_path,
    )
    rendered = render_draft(
        {**state, **generated},
        renderer=PosterRenderer(),
        run_directory=tmp_path,
    )

    evaluated = await evaluate_draft(
        {**state, **generated, **rendered},
        dependencies=EvaluationDependencies(
            deepgaze=FakeDeepGazeClient(),
            vision=FakeVisionEvaluator(),
        ),
        run_directory=tmp_path,
    )

    report = evaluated["evaluation_initial"]
    assert report.attention.availability == "available"
    assert report.attention.predicted_path == ["title"]
    assert report.attention.heatmap_artifact == "attention_initial.png"
    assert report.vision.score == 82
    assert report.scores.available_weight == 100
    assert (tmp_path / "attention_initial.png").read_bytes() == b"heatmap"
