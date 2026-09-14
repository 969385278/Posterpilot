from app.evaluation.vision_evaluator import VisionEvaluator


class FakeVisionProvider:
    async def analyze_json(self, *, image_url: str, prompt: str) -> dict:
        assert image_url == "https://example.test/poster.png"
        assert prompt == "review"
        return {
            "score": 82,
            "summary": "信息层级清晰。",
            "issues": [
                {
                    "problem": "副标题较弱",
                    "reason": "对比度不足",
                    "severity": "medium",
                    "related_principles": ["对比"],
                    "suggested_actions": ["set_color"],
                }
            ],
        }


class FailingVisionProvider:
    async def analyze_json(self, *, image_url: str, prompt: str) -> dict:
        raise RuntimeError("provider unavailable")


class FlakyVisionProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def analyze_json(self, *, image_url: str, prompt: str) -> dict:
        self.calls += 1
        if self.calls == 1:
            return {"summary": "missing score"}
        return {"score": 78, "summary": "第二次响应有效", "issues": []}


class ChineseSeverityVisionProvider:
    async def analyze_json(self, *, image_url: str, prompt: str) -> dict:
        return {
            "score": 90,
            "summary": "整体清晰",
            "issues": [
                {
                    "problem": "主办方信息偏弱",
                    "reason": "视觉权重较低",
                    "severity": "低",
                    "related_principles": "信息层级",
                    "suggested_actions": "适当增大字号",
                }
            ],
        }


async def test_vision_evaluator_maps_provider_json_to_review() -> None:
    review = await VisionEvaluator(FakeVisionProvider()).evaluate(
        image_url="https://example.test/poster.png",
        prompt="review",
    )

    assert review.availability == "available"
    assert review.score == 82
    assert review.issues[0].suggested_actions == ["set_color"]


async def test_vision_evaluator_marks_provider_failures_unavailable() -> None:
    review = await VisionEvaluator(FailingVisionProvider()).evaluate(
        image_url="https://example.test/poster.png",
        prompt="review",
    )

    assert review.availability == "unavailable"
    assert review.error == "Vision evaluation provider is unavailable."


async def test_vision_evaluator_retries_one_invalid_model_response() -> None:
    provider = FlakyVisionProvider()

    review = await VisionEvaluator(provider).evaluate(
        image_url="https://example.test/poster.png",
        prompt="review",
    )

    assert provider.calls == 2
    assert review.availability == "available"
    assert review.score == 78


async def test_vision_evaluator_normalizes_chinese_severity_labels() -> None:
    review = await VisionEvaluator(ChineseSeverityVisionProvider()).evaluate(
        image_url="https://example.test/poster.png",
        prompt="review",
    )

    assert review.availability == "available"
    assert review.issues[0].severity == "low"
    assert review.issues[0].related_principles == ["信息层级"]
    assert review.issues[0].suggested_actions == ["适当增大字号"]
