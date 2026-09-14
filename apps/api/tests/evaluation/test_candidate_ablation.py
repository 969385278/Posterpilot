from types import SimpleNamespace
from scripts.run_design_experiments import attention_ablation


def test_no_attention_tie_break_does_not_leak_original_attention_order():
    def candidate(id, score):
        return SimpleNamespace(id=id, label=id, rank_score=score, is_current=False, attention_used_for_ranking=True,
                               attention=SimpleNamespace(predicted_path=[]), checks=[], subject_overlap=None)
    a, b = candidate("r0-layout-5", 60), candidate("r0-layout-6", 70)
    first = attention_ablation(SimpleNamespace(layout_candidates=[b, a]))
    second = attention_ablation(SimpleNamespace(layout_candidates=[a, b]))
    for report in (first, second):
        assert report["with_attention_top"] == b.id
        assert report["without_attention_top"] == a.id
        assert set(report["without_attention_tied_top"]) == {a.id, b.id}
    assert not attention_ablation(SimpleNamespace(layout_candidates=[a]))["valid_comparison"]
