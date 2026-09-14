"""Recompute ablation with an order-independent tie break; no model calls."""
import json
from pathlib import Path
from types import SimpleNamespace
from run_design_experiments import ROOT, attention_ablation, save
from app.schemas.layout_candidate import LayoutCandidate


def audit(root: Path):
    outputs = []
    for condition in ("no_case", "selected_case"):
        directory = root / "club" / condition
        initial = json.loads((directory / "initial_checkpoint.json").read_text(encoding="utf-8"))
        report = attention_ablation(SimpleNamespace(layout_candidates=[LayoutCandidate.model_validate(item) for item in initial["layout_candidates"]]))
        outputs.append({"condition": condition, "source": "initial_checkpoint.json", "ablation": report})
        revised = directory / "candidate-review-v3/candidates.json"
        if revised.exists():
            candidates = [LayoutCandidate.model_validate(item) for item in json.loads(revised.read_text(encoding="utf-8"))]
            outputs.append({"condition": condition, "source": "candidate-review-v3/candidates.json", "ablation": attention_ablation(SimpleNamespace(layout_candidates=candidates))})
    save(root / "audited_attention_ablation.json", outputs)
    return outputs


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("experiment", type=Path)
    args = parser.parse_args()
    path = args.experiment.resolve()
    if not path.is_relative_to(ROOT / "data/experiments"):
        raise ValueError("Experiment must be under data/experiments")
    print(json.dumps(audit(path), ensure_ascii=False))
