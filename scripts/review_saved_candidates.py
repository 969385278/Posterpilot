"""Re-evaluate layout proposals on a saved real-model initial poster.

No image generation or LLM calls. Reuses the saved vision subject boxes and
calls real DeepGaze for new rendered candidates; writes a separate evidence folder.
"""
import argparse
import asyncio
import hashlib
import json
import shutil
from pathlib import Path

from run_design_experiments import ROOT, attention_ablation, save
from app.agent.nodes.propose_layouts import propose_layout_candidates
from app.agent.nodes.evaluate import EvaluationDependencies
from app.agent.state import initial_agent_state
from app.core.config import Settings
from app.evaluation.deepgaze_client import DeepGazeClient
from app.poster.renderer import PosterRenderer
from app.schemas.brief import PosterBrief
from app.schemas.design_spec import DesignSpec
from app.schemas.evaluation import EvaluationReport
from app.schemas.react import HumanCheckpoint


async def main(directory: Path, revision: str):
    directory = directory.resolve()
    if not directory.is_relative_to(ROOT / "data/experiments"):
        raise ValueError("Select an experiment condition within data/experiments")
    if revision not in {"v2", "v3"}:
        raise ValueError("Unknown review revision")
    target = directory / f"candidate-review-{revision}"
    if target.exists():
        raise ValueError("Evidence folder already exists; preserve the previous review")
    load = lambda name: json.loads((directory / name).read_text(encoding="utf-8"))
    checkpoint = HumanCheckpoint.model_validate(load("initial_checkpoint.json"))
    spec = DesignSpec.model_validate(load("design_spec.json"))
    initial_report = EvaluationReport.model_validate(load("result.json")["evaluation_initial"])
    # Brief is loaded from the recorded experiment, not inferred from poster OCR.
    brief = PosterBrief.model_validate(json.loads((directory.parent / "summary.json").read_text(encoding="utf-8"))["brief"])
    state = initial_agent_state(brief)
    target.mkdir()
    shutil.copyfile(directory / "poster_initial.png", target / "poster_initial.png")
    state.update(design_spec=spec, layout=spec.layout, main_visual_path=str(directory / "main_visual.png"),
                 poster_initial_path=str(target / "poster_initial.png"), analysis_current=checkpoint.analysis,
                 evaluation_initial=initial_report, rendered_text_facts=checkpoint.analysis.text_facts)
    settings = Settings()
    output = await propose_layout_candidates(state, renderer=PosterRenderer(), run_directory=target,
        evaluation=EvaluationDependencies(deepgaze=DeepGazeClient(base_url=settings.deepgaze_base_url, timeout_seconds=180)))
    updated = checkpoint.model_copy(update={"layout_candidates": output["layout_candidates"]})
    report = attention_ablation(updated)
    report.update(source_poster_sha256=hashlib.sha256((directory / "poster_initial.png").read_bytes()).hexdigest(),
                  source_subject_regions=[box.model_dump() for box in initial_report.vision.subject_regions],
                  note="Reused saved real VLM boxes; newly rendered candidates evaluated by real DeepGaze. Original experiment preserved.")
    save(target / "candidates.json", [candidate.model_dump(mode="json") for candidate in output["layout_candidates"]])
    save(target / "attention_ablation.json", report)
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--revision", choices=["v2", "v3"], default="v3")
    args = parser.parse_args()
    asyncio.run(main(args.directory, args.revision))
