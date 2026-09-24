"""Paired decision-card ablation using production ReAct, rendering and verification.

Callers supply a real provider for effect measurement. Fixture providers are only
for integration tests and must never be reported as model-quality evidence.
"""

import copy
import hashlib
import json
import shutil
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.agent.nodes.complete_round import complete_round, render_round
from app.agent.nodes.evaluate import evaluate_draft, evaluate_optimized
from app.agent.nodes.execute_react_tool import execute_react_tool
from app.agent.nodes.react_decide import react_decide
from app.agent.nodes.render_draft import render_draft
from app.agent.state import initial_agent_state
from app.agent.tools.catalog import BASE_TOOLS, EXTENSION_SCHEMAS
from app.evaluation.goal_verifier import verify_design_goals
from app.experiments.retrieval import digest
from app.experiments.toolsets import RestrictedToolset, summarize_tool_pairs
from app.poster.renderer import PosterRenderer
from app.schemas.brief import PosterBrief
from app.schemas.datahub import ExperienceQuery
from app.schemas.design_control import BackgroundTreatment, DesignControls
from app.schemas.design_spec import DesignSpec


class DecisionTask(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]+$", max_length=80)
    source_run_id: UUID
    brief: PosterBrief
    design_spec: DesignSpec
    main_visual: Path
    instruction: str = Field(min_length=1, max_length=1000)
    controls: DesignControls
    background_treatment: BackgroundTreatment = Field(default_factory=BackgroundTreatment)
    user_context: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def measurable_request(self):
        if not self.brief.use_case_memory:
            raise ValueError("decision-card experiment requires use_case_memory")
        if not self.controls.element_goals and not any(
            goal.direction != "preserve" for goal in self.controls.adjustments
        ):
            raise ValueError("at least one measurable modification goal is required")
        if self.controls.selected_candidate_id or self.controls.attention_priority:
            raise ValueError(
                "this rule-only experiment cannot evaluate candidate or attention goals"
            )
        return self


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


class FrozenContext:
    """Both arms keep exactly the same ordinary experience and user context."""

    include_demo = False

    def __init__(self, experiences, cards):
        self.experiences = copy.deepcopy(experiences)
        self.cards = copy.deepcopy(cards)
        self.decisions = SimpleNamespace(retrieve=self.retrieve_cards)

    def retrieve(self, query):
        return copy.deepcopy(self.experiences)

    def retrieve_cards(self, state, *, available_tools=None):
        return copy.deepcopy(self.cards)


class RecordedProvider:
    def __init__(self, provider, directory):
        self.provider, self.directory = provider, directory
        self.calls = 0

    async def complete_json(self, messages):
        self.calls += 1
        row = {"messages": copy.deepcopy(messages)}
        start = perf_counter()
        try:
            response = await self.provider.complete_json(messages)
            row["response"] = response
            return response
        except Exception as error:
            row["error_type"] = type(error).__name__
            raise
        finally:
            row["seconds"] = perf_counter() - start
            save(self.directory / f"model_call_{self.calls}.json", row)


def capture_context(task, hub, catalog):
    state = initial_agent_state(task.brief)
    state.update(
        run_id=str(task.source_run_id),
        layout=task.design_spec.layout,
        human_instruction=task.instruction,
    )
    # Do not use production's best-effort wrappers here: errors invalidate a study.
    experiences = hub.retrieve(
        ExperienceQuery(
            query=task.instruction,
            poster_type=task.brief.poster_type,
            exclude_run_id=task.source_run_id,
            include_demo=hub.include_demo,
        )
    )
    cards = hub.decisions.retrieve(state, available_tools={item["name"] for item in catalog})
    return {"experiences": experiences, "cards": cards}


def benchmark_result(state, initial):
    """Score the original request, not a moving goal relative to the previous round."""
    report = state["evaluation_optimized"]
    verification = verify_design_goals(
        before_layout=initial["layout"],
        after_layout=state["layout"],
        before_analysis=initial["analysis_current"],
        after_analysis=state["analysis_current"],
        controls=state["design_controls"],
        before_treatment=initial["background_treatment"],
        after_treatment=state["background_treatment"],
        attention=report.attention,
        rejection_reason=state.get("round_rejection_reason"),
    )
    severe = [
        item.model_dump(mode="json")
        for item in report.rule_issues
        if item.severity in {"high", "critical"}
    ]
    return {
        "accepted": verification.outcome == "met" and not severe,
        "verification": verification.model_dump(mode="json"),
        "severe_rules": severe,
    }


async def run_condition(task, initial, directory, *, provider, tools, context, catalog, rounds):
    directory.mkdir(parents=True, exist_ok=False)
    state = copy.deepcopy(initial)
    recorder = RecordedProvider(provider, directory)
    result = {
        "task_id": task.id,
        "first_action": None,
        "rounds": [],
        "accepted_round": None,
        "error_type": None,
    }
    try:
        for number in range(1, rounds + 1):
            state.update(
                round_number=number,
                human_instruction=task.instruction,
                tool_calls_in_round=0,
                tool_traces=[],
                react_decision=None,
                round_base_layout=state["layout"].model_copy(deep=True),
                round_base_treatment=state["background_treatment"].model_copy(deep=True),
                analysis_before_round=state["analysis_current"].model_copy(deep=True),
                goal_verification=None,
                round_rejection_reason=None,
            )
            # Production react_decide forces finish after three executed tool calls.
            for _ in range(4):
                state.update(
                    await react_decide(
                        state,
                        text_provider=recorder,
                        experience_source=context,
                        tool_catalog=catalog,
                    )
                )
                if state["react_decision"].decision == "finish_round":
                    break
                state.update(await execute_react_tool(state, tools=tools))
                if number == 1 and state["tool_calls_in_round"] == 1:
                    # Probe on an isolated copy: do not feed extra evaluation to the Agent.
                    probe = copy.deepcopy(state)
                    probe_dir = directory / "first_action"
                    probe_dir.mkdir()
                    probe.update(
                        render_round(probe, renderer=PosterRenderer(), run_directory=probe_dir)
                    )
                    probe.update(await evaluate_optimized(probe, run_directory=probe_dir))
                    result["first_action"] = benchmark_result(probe, initial)
                    result["first_action"]["trace"] = state["tool_traces"][0].model_dump(
                        mode="json"
                    )
                    result["first_action"]["accepted"] &= state["tool_traces"][0].success
            state.update(render_round(state, renderer=PosterRenderer(), run_directory=directory))
            state.update(await evaluate_optimized(state, run_directory=directory))
            state.update(complete_round(state))
            outcome = benchmark_result(state, initial)
            result["rounds"].append(
                {
                    "number": number,
                    **outcome,
                    "snapshot": state["round_snapshots"][-1].model_dump(mode="json"),
                }
            )
            if outcome["accepted"]:
                result["accepted_round"] = number
                break
    except Exception as error:
        result["error_type"] = type(error).__name__
    result.update(model_calls=recorder.calls, censored=result["accepted_round"] is None)
    save(directory / "result.json", result)
    return result


async def compare_decisions(
    tasks,
    root,
    *,
    provider,
    tools,
    hub,
    live=False,
    rounds=3,
    intervention="cards",
    added_tools=(),
):
    if not tasks or len({item.id for item in tasks}) != len(tasks):
        raise ValueError("nonempty tasks with unique IDs required")
    if not 1 <= rounds <= 3:
        raise ValueError("round budget must be between one and three")
    if intervention not in {"cards", "tools"}:
        raise ValueError("unknown intervention")
    if intervention == "cards" and added_tools:
        raise ValueError("card ablation must not also change tool availability")
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False)
    catalog = copy.deepcopy(tools.public_catalog())
    save(root / "tool_catalog.json", catalog)
    condition_names = ["without_cards", "with_cards"]
    toolsets = {name: tools for name in condition_names}
    if intervention == "tools":
        if not added_tools or len(set(added_tools)) != len(added_tools):
            raise ValueError("unique, nonempty added_tools required")
        if not set(added_tools) <= EXTENSION_SCHEMAS.keys():
            raise ValueError("added_tools must be registered extensions")
        release_source = getattr(tools, "release_source", None)
        if release_source is None:
            raise ValueError("tool capability comparison requires the real publication gate")
        for name in added_tools:
            release_source.authorization(name)
        if not set(added_tools) <= {item["name"] for item in catalog}:
            raise ValueError("requested extensions missing from current catalog")
        releases = [item for item in release_source.catalog() if item["name"] in added_tools]
        save(root / "release_evidence.json", releases)
        for item in releases:
            report_id = item["release"]["report_id"]
            save(root / f"gate_report_{report_id}.json", release_source.report(report_id))
        condition_names = ["base_tools", "extended_tools"]
        toolsets = {
            "base_tools": RestrictedToolset(tools, BASE_TOOLS),
            "extended_tools": RestrictedToolset(tools, BASE_TOOLS | set(added_tools)),
        }
    catalogs = {name: copy.deepcopy(toolsets[name].public_catalog()) for name in condition_names}
    save(root / "condition_catalogs.json", catalogs)
    rows, frozen = [], []
    for index, task in enumerate(tasks):
        directory = root / task.id
        directory.mkdir()
        save(directory / "input.json", task.model_dump(mode="json"))
        row = {"task_id": task.id, "conditions": {}, "error_type": None}
        try:
            image = directory / ("main_visual" + task.main_visual.suffix)
            shutil.copyfile(task.main_visual, image)
            row["image_sha256"] = hashlib.sha256(image.read_bytes()).hexdigest()
            initial = initial_agent_state(task.brief.model_copy(deep=True))
            initial.update(
                run_id=str(task.source_run_id),
                design_spec=task.design_spec.model_copy(deep=True),
                layout=task.design_spec.layout.model_copy(deep=True),
                main_visual_path=str(image),
                design_controls=task.controls.model_copy(deep=True),
                background_treatment=task.background_treatment.model_copy(deep=True),
                user_context=copy.deepcopy(task.user_context),
            )
            initial.update(
                render_draft(initial, renderer=PosterRenderer(), run_directory=directory)
            )
            initial.update(await evaluate_draft(initial, run_directory=directory))
            context = capture_context(task, hub, catalog)
            frozen.append((task, context))
            save(directory / "context.json", context)
            row["retrieved_card_count"] = len(context["cards"])
            # Alternate arm order to reduce simple service-time/order confounding.
            order = list(condition_names)
            if index % 2:
                order.reverse()
            row["execution_order"] = order
            for condition in order:
                row["conditions"][condition] = await run_condition(
                    task,
                    initial,
                    directory / condition,
                    provider=provider,
                    tools=toolsets[condition],
                    context=FrozenContext(
                        context["experiences"],
                        context["cards"]
                        if intervention == "cards" and condition == "with_cards"
                        else [],
                    ),
                    catalog=catalogs[condition],
                    rounds=rounds,
                )
        except Exception as error:
            row["error_type"] = type(error).__name__
        rows.append(row)
        save(directory / "paired_result.json", row)
    drift = False
    try:
        drift = digest(catalog) != digest(tools.public_catalog()) or any(
            digest(context) != digest(capture_context(task, hub, catalog))
            for task, context in frozen
        )
    except Exception:
        drift = True
    errors = sum(
        bool(row["error_type"]) or any(item["error_type"] for item in row["conditions"].values())
        for row in rows
    )
    summary = {
        "task_count": len(tasks),
        "runtime_error_tasks": errors,
        "context_or_catalog_drift": drift,
        "round_budget": rounds,
        "tool_budget_per_round": 3,
        "evaluation": "rule_only",
        "intervention": intervention,
        "added_tools": list(added_tools),
        "live_provider": live,
        "valid_execution": not errors and not drift,
        "effect_claim_supported": False,
        "conditions": {},
    }
    summary["tasks_with_cards"] = sum(bool(row.get("retrieved_card_count")) for row in rows)
    summary["valid_live_comparison"] = (
        live
        and summary["valid_execution"]
        and (intervention == "tools" or summary["tasks_with_cards"] > 0)
    )
    for condition in condition_names:
        outcomes = [row["conditions"].get(condition, {}) for row in rows]
        successes = [item["accepted_round"] for item in outcomes if item.get("accepted_round")]
        summary["conditions"][condition] = {
            "first_action_accepted": sum(
                bool((item.get("first_action") or {}).get("accepted")) for item in outcomes
            ),
            "task_accepted": len(successes),
            "unresolved_or_error": len(tasks) - len(successes),
            "mean_rounds_successes_only": sum(successes) / len(successes) if successes else None,
            "success_round_denominator": len(successes),
        }
    if intervention == "tools":
        summary["paired_outcomes"] = summarize_tool_pairs(rows, added_tools)
    save(root / "summary.json", summary)
    return summary, rows
