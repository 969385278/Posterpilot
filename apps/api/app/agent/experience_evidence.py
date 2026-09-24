"""Persist per-render evidence, not a mutable summary of the last task state."""

import json
from pathlib import Path


def write_experience_evidence(state, report, updates, *, initial: bool, run_directory) -> None:
    if run_directory is None:
        return
    layout = state.get("layout") or state["design_spec"].layout
    round_number = 0 if initial else state.get("round_number", 0)
    # The legacy one-shot graph has no numbered ReAct round; don't mislabel its output.
    if not initial and not round_number:
        return
    analysis = updates.get("analysis_current")
    goal = updates.get("goal_verification")
    payload = {
        "schema_version": 1,
        "round_number": round_number,
        "brief": state["brief"].model_dump(mode="json"),
        "design_spec": state["design_spec"].model_dump(mode="json"),
        "layout": layout.model_dump(mode="json"),
        "instruction": "" if initial else state.get("human_instruction", ""),
        "controls": state["design_controls"].model_dump(mode="json")
        if state.get("design_controls")
        else {},
        "tool_traces": []
        if initial
        else [t.model_dump(mode="json") for t in state.get("tool_traces", [])],
        "evaluation": report.model_dump(mode="json"),
        "analysis": analysis.model_dump(mode="json") if analysis else None,
        "goal_verification": goal.model_dump(mode="json") if goal else None,
        "background_treatment": state["background_treatment"].model_dump(mode="json")
        if state.get("background_treatment")
        else {},
        "poster_artifact": "poster_initial.png" if initial else f"poster_round_{round_number}.png",
        "experience_references": state.get("experience_references", []),
        "user_context": state.get("user_context", {}),
        "decision_card_references": state.get("decision_card_references", []),
        "tool_catalog": state.get("tool_catalog", []),
        "visual_asset_retrieval": state.get("visual_asset_retrieval", {}),
    }
    path = Path(run_directory) / f"experience_round_{round_number}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
