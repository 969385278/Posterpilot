from pathlib import Path
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agent.nodes.apply_optimization import apply_optimization
from app.agent.nodes.complete_round import complete_round, render_round
from app.agent.nodes.evaluate import EvaluationDependencies, evaluate_draft, evaluate_optimized
from app.agent.nodes.execute_react_tool import execute_react_tool
from app.agent.nodes.finalize import finalize
from app.agent.nodes.generate_visual import generate_visual
from app.agent.nodes.human_review import (
    human_review,
    route_after_round,
    route_human_decision,
)
from app.agent.nodes.plan_design import plan_design
from app.agent.nodes.propose_layouts import propose_layout_candidates
from app.agent.nodes.plan_optimization import plan_optimization
from app.agent.nodes.react_decide import react_decide, route_react_decision
from app.agent.nodes.render_draft import render_draft
from app.agent.nodes.retrieve_knowledge import Retriever, retrieve_generation_knowledge
from app.agent.nodes.retrieve_optimization_knowledge import retrieve_optimization_knowledge
from app.agent.state import PosterAgentState
from app.agent.tools.react_tools import ReactToolRegistry
from app.poster.renderer import PosterRenderer
from app.providers.image.base import ImageProvider
from app.providers.llm.base import JsonChatProvider


def create_hitl_react_graph(
    *,
    retriever: Retriever,
    text_provider: JsonChatProvider,
    image_provider: ImageProvider,
    renderer: PosterRenderer,
    tools: ReactToolRegistry,
    checkpointer: Any,
    evaluation: EvaluationDependencies | None = None,
    experience_source: Any | None = None,
) -> Any:
    """Compile the persisted end-to-end graph with native human interrupts."""

    async def retrieve_node(state: PosterAgentState) -> dict[str, object]:
        return await retrieve_generation_knowledge(state, retriever=retriever)

    async def plan_node(state: PosterAgentState) -> dict[str, object]:
        return await plan_design(state, text_provider=text_provider, experience_source=experience_source)

    async def generate_node(state: PosterAgentState) -> dict[str, object]:
        return await generate_visual(
            state,
            image_provider=image_provider,
            run_directory=_run_directory(state),
        )

    def render_initial_node(state: PosterAgentState) -> dict[str, object]:
        return render_draft(
            state,
            renderer=renderer,
            run_directory=_run_directory(state),
        )

    async def evaluate_initial_node(state: PosterAgentState) -> dict[str, object]:
        return await evaluate_draft(
            state,
            dependencies=evaluation,
            run_directory=_run_directory(state),
        )

    async def decide_node(state: PosterAgentState) -> dict[str, object]:
        return await react_decide(state, text_provider=text_provider, experience_source=experience_source)

    async def tool_node(state: PosterAgentState) -> dict[str, object]:
        return await execute_react_tool(state, tools=tools)

    def render_round_node(state: PosterAgentState) -> dict[str, object]:
        return render_round(
            state,
            renderer=renderer,
            run_directory=_run_directory(state),
        )

    async def evaluate_round_node(state: PosterAgentState) -> dict[str, object]:
        return await evaluate_optimized(
            state,
            dependencies=evaluation,
            run_directory=_run_directory(state),
        )

    async def candidates_node(state: PosterAgentState) -> dict[str, object]:
        if len(state["round_snapshots"]) >= 3:
            return {"layout_candidates": []}
        return await propose_layout_candidates(state, renderer=renderer, evaluation=evaluation, run_directory=_run_directory(state))

    workflow = StateGraph(PosterAgentState)
    workflow.add_node("retrieve_generation_knowledge", retrieve_node)
    workflow.add_node("plan_design", plan_node)
    workflow.add_node("generate_visual", generate_node)
    workflow.add_node("render_draft", render_initial_node)
    workflow.add_node("evaluate_draft", evaluate_initial_node)
    workflow.add_node("human_review", human_review)
    workflow.add_node("react_decide", decide_node)
    workflow.add_node("execute_react_tool", tool_node)
    workflow.add_node("render_round", render_round_node)
    workflow.add_node("evaluate_round", evaluate_round_node)
    workflow.add_node("complete_round", complete_round)
    workflow.add_node("propose_layout_candidates", candidates_node)
    workflow.add_node("finalize", finalize)

    initial_sequence = [
        "retrieve_generation_knowledge",
        "plan_design",
        "generate_visual",
        "render_draft",
        "evaluate_draft",
        "propose_layout_candidates",
    ]
    workflow.add_edge(START, initial_sequence[0])
    for source, target in zip(initial_sequence[:-1], initial_sequence[1:], strict=True):
        workflow.add_edge(source, target)
    workflow.add_conditional_edges(
        "human_review",
        route_human_decision,
        {
            "react_decide": "react_decide",
            "finalize": "finalize",
        },
    )
    workflow.add_conditional_edges(
        "react_decide",
        route_react_decision,
        {
            "execute_react_tool": "execute_react_tool",
            "finish_round": "render_round",
        },
    )
    workflow.add_edge("execute_react_tool", "react_decide")
    workflow.add_edge("render_round", "evaluate_round")
    workflow.add_edge("evaluate_round", "complete_round")
    workflow.add_edge("complete_round", "propose_layout_candidates")
    workflow.add_conditional_edges(
        "propose_layout_candidates",
        route_after_round,
        {
            "human_review": "human_review",
            "finalize": "finalize",
        },
    )
    workflow.add_edge("finalize", END)
    return workflow.compile(checkpointer=checkpointer)


def _run_directory(state: PosterAgentState) -> str:
    run_directory = state["run_directory"]
    if not run_directory:
        raise ValueError("run_directory is required for persisted graph execution")
    return run_directory


def create_generation_graph(*, retriever: Retriever, text_provider: JsonChatProvider) -> Any:
    """Compile the first, independently testable part of the full poster workflow."""

    async def retrieve_node(state: PosterAgentState) -> dict[str, object]:
        return await retrieve_generation_knowledge(state, retriever=retriever)

    async def plan_node(state: PosterAgentState) -> dict[str, object]:
        return await plan_design(state, text_provider=text_provider)

    workflow = StateGraph(PosterAgentState)
    workflow.add_node("retrieve_generation_knowledge", retrieve_node)
    workflow.add_node("plan_design", plan_node)
    workflow.add_edge(START, "retrieve_generation_knowledge")
    workflow.add_edge("retrieve_generation_knowledge", "plan_design")
    workflow.add_edge("plan_design", END)
    return workflow.compile()


def create_optimization_graph(
    *,
    retriever: Retriever,
    text_provider: JsonChatProvider,
    image_provider: ImageProvider,
    renderer: PosterRenderer,
    run_directory: str,
    evaluation: EvaluationDependencies | None = None,
) -> Any:
    """Compile the offline-testable MVP: generate, evaluate, optimize once, and re-evaluate."""

    async def retrieve_generation_node(state: PosterAgentState) -> dict[str, object]:
        return await retrieve_generation_knowledge(state, retriever=retriever)

    async def plan_design_node(state: PosterAgentState) -> dict[str, object]:
        return await plan_design(state, text_provider=text_provider)

    async def generate_visual_node(state: PosterAgentState) -> dict[str, object]:
        return await generate_visual(
            state,
            image_provider=image_provider,
            run_directory=run_directory,
        )

    def render_draft_node(state: PosterAgentState) -> dict[str, object]:
        return render_draft(state, renderer=renderer, run_directory=run_directory)

    async def evaluate_draft_node(state: PosterAgentState) -> dict[str, object]:
        return await evaluate_draft(
            state,
            dependencies=evaluation,
            run_directory=run_directory,
        )

    async def retrieve_optimization_node(state: PosterAgentState) -> dict[str, object]:
        return await retrieve_optimization_knowledge(state, retriever=retriever)

    async def plan_optimization_node(state: PosterAgentState) -> dict[str, object]:
        return await plan_optimization(state, text_provider=text_provider)

    def apply_optimization_node(state: PosterAgentState) -> dict[str, object]:
        return apply_optimization(state, renderer=renderer, run_directory=run_directory)

    async def evaluate_optimized_node(state: PosterAgentState) -> dict[str, object]:
        return await evaluate_optimized(
            state,
            dependencies=evaluation,
            run_directory=run_directory,
        )

    workflow = StateGraph(PosterAgentState)
    workflow.add_node("retrieve_generation_knowledge", retrieve_generation_node)
    workflow.add_node("plan_design", plan_design_node)
    workflow.add_node("generate_visual", generate_visual_node)
    workflow.add_node("render_draft", render_draft_node)
    workflow.add_node("evaluate_draft", evaluate_draft_node)
    workflow.add_node("retrieve_optimization_knowledge", retrieve_optimization_node)
    workflow.add_node("plan_optimization", plan_optimization_node)
    workflow.add_node("apply_optimization", apply_optimization_node)
    workflow.add_node("evaluate_optimized", evaluate_optimized_node)
    workflow.add_node("finalize", finalize)
    sequence = [
        "retrieve_generation_knowledge",
        "plan_design",
        "generate_visual",
        "render_draft",
        "evaluate_draft",
        "retrieve_optimization_knowledge",
        "plan_optimization",
        "apply_optimization",
        "evaluate_optimized",
        "finalize",
    ]
    workflow.add_edge(START, sequence[0])
    for source, target in zip(sequence[:-1], sequence[1:], strict=True):
        workflow.add_edge(source, target)
    workflow.add_edge(sequence[-1], END)
    return workflow.compile()


def create_react_round_graph(
    *,
    text_provider: JsonChatProvider,
    tools: ReactToolRegistry,
    renderer: PosterRenderer,
    run_directory: str | Path,
    evaluation: EvaluationDependencies | None = None,
) -> Any:
    """Compile one bounded ReAct optimization round with deterministic evaluation."""

    async def decide_node(state: PosterAgentState) -> dict[str, object]:
        return await react_decide(state, text_provider=text_provider)

    async def tool_node(state: PosterAgentState) -> dict[str, object]:
        return await execute_react_tool(state, tools=tools)

    def render_node(state: PosterAgentState) -> dict[str, object]:
        return render_round(state, renderer=renderer, run_directory=run_directory)

    async def evaluate_node(state: PosterAgentState) -> dict[str, object]:
        return await evaluate_optimized(
            state,
            dependencies=evaluation,
            run_directory=run_directory,
        )

    workflow = StateGraph(PosterAgentState)
    workflow.add_node("react_decide", decide_node)
    workflow.add_node("execute_react_tool", tool_node)
    workflow.add_node("render_round", render_node)
    workflow.add_node("evaluate_round", evaluate_node)
    workflow.add_node("complete_round", complete_round)
    workflow.add_edge(START, "react_decide")
    workflow.add_conditional_edges(
        "react_decide",
        route_react_decision,
        {
            "execute_react_tool": "execute_react_tool",
            "finish_round": "render_round",
        },
    )
    workflow.add_edge("execute_react_tool", "react_decide")
    workflow.add_edge("render_round", "evaluate_round")
    workflow.add_edge("evaluate_round", "complete_round")
    workflow.add_edge("complete_round", END)
    return workflow.compile()
