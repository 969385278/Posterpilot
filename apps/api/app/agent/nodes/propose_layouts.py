from pathlib import Path

from app.agent.nodes.common import with_event
from app.agent.nodes.evaluate import EvaluationDependencies, _evaluate_attention
from app.agent.state import PosterAgentState
from app.evaluation.design_analysis import analyze_design
from app.evaluation.hard_rules import evaluate_hard_rules
from app.poster.layout_candidates import propose_layouts, subject_overlap_ratio
from app.poster.renderer import PosterRenderer
from app.poster.design_guards import DesignConstraintError, assert_rendered_locks
from app.schemas.design_control import BackgroundTreatment, DesignControls, VerificationCheck
from app.schemas.evaluation import AttentionPrediction
from app.schemas.layout_candidate import LayoutCandidate


def _candidate_checks(layout, analysis, controls, baseline_analysis, subject_regions):
    checks = list(analysis.readability_checks)
    try:
        assert_rendered_locks(baseline_analysis, analysis, controls)
        checks.append(VerificationCheck(key="preserved_features", label="保留条件", status="passed", detail="实际字体与指定保留特征未发生越界变化。"))
    except DesignConstraintError as error:
        checks.append(VerificationCheck(key="preserved_features", label="保留条件", status="failed", detail=str(error)))
    rules = evaluate_hard_rules(layout, controls)
    blocking = [issue for issue in rules if issue.severity in {"critical", "high"}]
    checks.append(VerificationCheck(key="layout_rules", label="文字重叠与必要信息", status="failed" if blocking else "passed", detail="；".join(issue.problem for issue in blocking) or "未发现文字区域重叠或必要区域缺失。"))
    overflow = [fact.element_id for fact in analysis.text_facts if not fact.fits_box]
    checks.append(VerificationCheck(key="text_fit", label="文字实际区域", status="failed" if overflow else "passed", detail="超出区域：" + "、".join(overflow) if overflow else "实际绘制文字位于分配区域内。"))
    baseline_facts = {fact.element_id: fact for fact in baseline_analysis.text_facts}
    for lock in controls.locks:
        if "typography" not in lock.properties:
            continue
        for fact in analysis.text_facts:
            if fact.element_id != lock.element_id or fact.element_id not in baseline_facts:
                continue
            old = baseline_facts[fact.element_id]
            same = (old.actual_font_size, old.font_name) == (fact.actual_font_size, fact.font_name)
            checks.append(VerificationCheck(key=f"render_lock:{fact.element_id}", label="实际字体锁定", status="passed" if same else "failed", detail="排版位置变化也可能导致自动缩字；此处检查实际绘制结果。"))
    overlap = subject_overlap_ratio([fact.box for fact in analysis.text_facts], subject_regions, layout)
    checks.append(VerificationCheck(key="subject_protection", label="主体遮挡检查", status="unavailable" if overlap is None else "passed" if overlap <= 0.03 else "failed", after=overlap, detail="基于视觉模型估计的主体框与文字实际包围框，允许覆盖比例不超过3%；不是像素级分割。" if overlap is not None else "未获得可靠主体框，不能确认主体未被遮挡。"))
    return checks, overlap


async def propose_layout_candidates(
    state: PosterAgentState, *, renderer: PosterRenderer,
    evaluation: EvaluationDependencies | None, run_directory: Path | str,
) -> dict[str, object]:
    report = state["evaluation_optimized"] or state["evaluation_initial"]
    analysis = state.get("analysis_current")
    if not state["brief"].attention_layout or report is None or analysis is None:
        return {"layout_candidates": []}
    layout = state["layout"] or state["design_spec"].layout
    controls = state.get("design_controls") or DesignControls()
    treatment = state.get("background_treatment") or BackgroundTreatment()
    directory = Path(run_directory)
    round_number = len(state["round_snapshots"])
    priority = controls.attention_priority or state["design_spec"].expected_attention_path
    current_path = state["poster_optimized_path"] or state["poster_initial_path"]
    checks, overlap = _candidate_checks(layout, analysis, controls, analysis, report.vision.subject_regions)
    candidates = [LayoutCandidate(
        id=f"r{round_number}-current", round_number=round_number, label="当前排版",
        poster_artifact=Path(current_path).name, layout=layout, analysis=analysis,
        attention=report.attention, checks=checks, subject_overlap=overlap,
        rank_score=0, is_current=True,
    )]
    # At most two alternatives are evaluated by DeepGaze; all previews remain
    # candidate artifacts and do not add optimization round snapshots.
    for index, (label, alternative) in enumerate(propose_layouts(layout, controls, report.vision.subject_regions), start=1):
        artifact = f"layout_r{round_number}_{index}.png"
        rendered = renderer.render(alternative, main_visual_path=state["main_visual_path"], output_path=directory / artifact, background_color=state["design_spec"].palette.background, treatment=treatment)
        measured = analyze_design(alternative, main_visual_path=state["main_visual_path"], treatment=treatment, text_facts=rendered.text_facts)
        checks, overlap = _candidate_checks(alternative, measured, controls, analysis, report.vision.subject_regions)
        # Readability is also shown for the current layout. Do not offer a new
        # candidate with a hard layout failure, overflow, lock violation or known
        # subject collision. A missing model signal remains visibly unavailable.
        if any(check.status == "failed" for check in checks if not check.key.startswith("readability:")):
            continue
        attention = await _evaluate_attention(
            evaluation.deepgaze if evaluation else None,
            poster_bytes=rendered.path.read_bytes(), poster_path=rendered.path,
            layout=alternative, heatmap_name=f"attention_layout_r{round_number}_{index}.png",
            run_directory=directory,
        )
        candidates.append(LayoutCandidate(
            id=f"r{round_number}-layout-{index}", round_number=round_number, label=label,
            poster_artifact=artifact, layout=alternative, analysis=measured,
            attention=attention, checks=checks, subject_overlap=overlap, rank_score=0,
        ))
        if len(candidates) >= 3:
            break
    attention_available = all(candidate.attention.availability != "unavailable" and candidate.attention.model and candidate.attention.predicted_path for candidate in candidates)
    attention_comparable = bool(attention_available and len({candidate.attention.model for candidate in candidates}) == 1)
    for candidate in candidates:
        readability = [check for check in candidate.checks if check.key.startswith("readability:")]
        clear_fraction = sum(check.status == "passed" for check in readability) / max(1, len(readability))
        layout_checks = [check for check in candidate.checks if not check.key.startswith("readability:") and check.status != "unavailable"]
        layout_fraction = sum(check.status == "passed" for check in layout_checks) / max(1, len(layout_checks))
        base = 0.65 * clear_fraction + 0.35 * layout_fraction
        if attention_comparable:
            path = candidate.attention.predicted_path
            match = sum(index < len(path) and path[index] == role for index, role in enumerate(priority)) / max(1, len(priority))
            candidate.rank_score = round(100 * (0.7 * base + 0.3 * match), 2)
            candidate.attention_used_for_ranking = True
        else:
            candidate.rank_score = round(100 * base, 2)
        candidate.notes = [
            "排序分仅用于本组候选比较，不是海报审美评分。",
            "当前 DeepGaze 接口用中心起点得到一张显著性图，再取分散热点作为顺序代理；不是逐步更新历史的完整扫视模拟。",
            "注意力项使用预测角色顺序匹配，不代表真实用户观看或理解。" if attention_comparable else "注意力缺失或模型不一致，本组统一不使用注意力项排序。",
            *(["主体框不可用，选择前请人工检查是否遮挡主角。"] if candidate.subject_overlap is None else []),
        ]
    candidates.sort(key=lambda candidate: (-candidate.rank_score, not candidate.is_current, candidate.id))
    return {
        "layout_candidates": candidates,
        "events": with_event(state, node="propose_layout_candidates", message=f"已比较当前排版与 {len(candidates) - 1} 个候选，等待人工选择。", payload={"candidate_ids": [candidate.id for candidate in candidates], "attention_used": attention_comparable}),
    }
