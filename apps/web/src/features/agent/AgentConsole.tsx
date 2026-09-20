import { useState } from 'react';

import type { HumanCheckpoint, HumanDecision, RoundSnapshot, RunEvent } from '../../api/client';
import { DesignReviewPanel } from '../design/DesignReviewPanel';

type AgentConsoleProps = {
  status: string | null;
  checkpoint: HumanCheckpoint | null;
  events: RunEvent[];
  completedRounds?: RoundSnapshot[];
  isSubmitting: boolean;
  onApprove: () => void;
  onInstruct: (instruction: string) => void;
  onFinish: () => void;
  onControlledDecision?: (decision: HumanDecision) => void;
  selectedCandidateId?: string | null;
};

export function AgentConsole({
  status,
  checkpoint,
  events,
  completedRounds = [],
  isSubmitting,
  onApprove,
  onInstruct,
  onFinish,
  onControlledDecision,
  selectedCandidateId = null,
}: AgentConsoleProps) {
  const [instruction, setInstruction] = useState('');
  const waiting = status === 'waiting_for_human' && checkpoint !== null;
  const traces = checkpoint?.tool_traces ?? completedRounds.flatMap((round) => round.tool_traces);
  const references = new Map<string, { case_id: string; revision: number; problem: string; lesson: string }>();
  for (const event of events) {
    const candidates = event.payload?.experience_candidates;
    if (!Array.isArray(candidates)) continue;
    for (const reference of candidates) {
      if (reference && typeof reference.case_id === 'string' && typeof reference.revision === 'number') {
        references.set(`${reference.case_id}:${reference.revision}`, reference);
      }
    }
  }

  function submitInstruction() {
    const value = instruction.trim();
    if (!value) return;
    onInstruct(value);
  }

  return (
    <aside className={`agent-console ${waiting ? 'is-waiting' : ''}`} aria-label="Agent 操作台">
      <div className="agent-console__header">
        <div>
          <p className="section-kicker">Human-in-the-loop</p>
          <h2>Agent 操作台</h2>
        </div>
        <span className="agent-status">{statusLabel(status)}</span>
      </div>

      {checkpoint ? (
        <>
          <section className="agent-observation">
            <span>当前观察 · {checkpoint.score.toFixed(1)} 分</span>
            {checkpoint.evaluation_notes?.map((note) => <p key={note} className="evaluation-note">{note}</p>)}
            <p>{checkpoint.suggestion}</p>
            {checkpoint.primary_issues.length ? (
              <ul>
                {checkpoint.primary_issues.map((issue) => <li key={issue}>{issue}</li>)}
              </ul>
            ) : null}
          </section>

          {checkpoint.citations.length ? (
            <section className="agent-citations">
              <h3>设计知识依据</h3>
              {checkpoint.citations.map((citation) => (
                <p key={citation.card_id}>
                  {citation.title}
                  <small>
                    {citation.source_id === 'qinghua' ? '清华' : citation.source_id}
                    {citation.source_pages.length ? ` · 第 ${citation.source_pages.join('、')} 页` : ''}
                  </small>
                </p>
              ))}
            </section>
          ) : null}

        </>
      ) : (
        <p className="agent-console__empty">
          {status === 'completed' ? '任务已结束，当前海报与轮次记录已保存。' : status === 'failed' ? '任务未完成，请查看失败原因。' : events.at(-1)?.message ?? '提交需求后，这里会展示 Agent 的观察、工具选择和结果。'}
        </p>
      )}

      {traces.length ? (
        <section className="tool-traces">
          <h3>{checkpoint ? '本轮工具轨迹' : '完整工具轨迹'}</h3>
          <ol>
            {traces.map((trace) => (
              <li key={`${trace.round_number}-${trace.step}`}>
                <div>
                  <code>{trace.tool_name}</code>
                  <span>{trace.success ? '成功' : '失败'}</span>
                </div>
                <p>{trace.decision_summary}</p>
                <small>{trace.observation}</small>
              </li>
            ))}
          </ol>
        </section>
      ) : null}

      {references.size > 0 && <section className="agent-citations" aria-label="历史经验参考">
        <h3>本任务获得的历史经验</h3>
        <p>下列内容曾提供给模型作为参考，不代表已采纳或已改善效果。当前用户要求优先。</p>
        {[...references.values()].map(reference => <p key={`${reference.case_id}:${reference.revision}`}>
          <strong>{reference.problem}</strong><small>{reference.lesson}</small>
          <small>案例 {reference.case_id.slice(0, 8)} · v{reference.revision} · <a href="#datahub">查看案例与审核</a></small>
        </p>)}
      </section>}

      {waiting && checkpoint.layout && checkpoint.analysis && onControlledDecision ? (
        <DesignReviewPanel checkpoint={checkpoint} selectedCandidateId={selectedCandidateId} disabled={isSubmitting} onSubmit={onControlledDecision} />
      ) : waiting ? (
        <section className="human-decision-panel">
          <button type="button" className="primary-action" disabled={isSubmitting} onClick={onApprove}>
            按建议优化
          </button>
          <label htmlFor="human-instruction">告诉 Agent 这一轮怎么改</label>
          <textarea
            id="human-instruction"
            value={instruction}
            maxLength={1000}
            placeholder="例如：不要改变主视觉，只增强标题并增加信息区留白"
            onChange={(event) => setInstruction(event.target.value)}
          />
          <button
            type="button"
            className="secondary-action"
            disabled={isSubmitting || !instruction.trim()}
            onClick={submitInstruction}
          >
            提交修改要求
          </button>
          <button type="button" className="text-action" disabled={isSubmitting} onClick={onFinish}>
            结束任务，保留当前版本
          </button>
        </section>
      ) : null}
    </aside>
  );
}

function statusLabel(status: string | null): string {
  if (status === 'waiting_for_human') return '等待你的决定';
  if (status === 'running') return 'Agent 执行中';
  if (status === 'completed') return '已完成';
  if (status === 'failed') return '执行失败';
  return '尚未开始';
}
