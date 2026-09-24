"""Export a real initial run into a fixed decision-card experiment input."""

import argparse
import json
from pathlib import Path
from uuid import UUID

from app.experiments.decisions import DecisionTask
from app.schemas.design_control import DesignControls


def export_task(run_directory, *, task_id, instruction, controls):
    run_directory = Path(run_directory).resolve()
    evidence = json.loads(
        (run_directory / "experience_round_0.json").read_text("utf-8")
    )
    if not evidence.get("design_spec"):
        raise ValueError(
            "This old run has no full design_spec; regenerate rather than invent it"
        )
    return DecisionTask(
        id=task_id,
        source_run_id=UUID(run_directory.name),
        brief=evidence["brief"],
        design_spec=evidence["design_spec"],
        main_visual=run_directory / "main_visual.png",
        instruction=instruction,
        controls=controls,
        background_treatment=evidence.get("background_treatment", {}),
        user_context=evidence.get("user_context", {}),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-directory", type=Path, required=True)
    parser.add_argument("--id", required=True)
    parser.add_argument("--instruction", required=True)
    parser.add_argument("--controls", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    controls = DesignControls.model_validate_json(args.controls.read_text("utf-8"))
    task = export_task(
        args.run_directory,
        task_id=args.id,
        instruction=args.instruction,
        controls=controls,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(
            {
                "dataset_kind": "user_export_not_verified_holdout",
                "tasks": [task.model_dump(mode="json")],
            },
            stream,
            ensure_ascii=False,
            indent=2,
        )
    print(args.output)


if __name__ == "__main__":
    main()
