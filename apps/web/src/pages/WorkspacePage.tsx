import { useEffect, useState } from 'react';
import { openRun } from '../app/navigation';

import {
  artifactUrl,
  createRun,
  getPendingHumanInput,
  getRun,
  getRunResult,
  submitHumanDecision,
  subscribeRunEvents,
  type HumanCheckpoint,
  type HumanDecision,
  type PosterBriefInput,
  type RunEvent,
  type RunRecord,
  type RunResult,
} from '../api/client';
import { AgentTimeline } from '../features/agent/AgentTimeline';
import { AgentConsole } from '../features/agent/AgentConsole';
import { BriefForm } from '../features/brief/BriefForm';
import { BeforeAfter } from '../features/comparison/BeforeAfter';
import { EvaluationPanel } from '../features/evaluation/EvaluationPanel';
import { PosterPreview } from '../features/poster/PosterPreview';
import { RoundGallery } from '../features/poster/RoundGallery';
import { ThemeSelect } from '../features/theme/ThemeSelect';
import { CandidatePicker } from '../features/design/CandidatePicker';

type WorkspacePageProps = {
  onOpenHistory: () => void;
  initialRunId?: string;
};

export function WorkspacePage({ onOpenHistory, initialRunId }: WorkspacePageProps) {
  const [run, setRun] = useState<RunRecord | null>(null);
  const [result, setResult] = useState<RunResult | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [checkpoint, setCheckpoint] = useState<HumanCheckpoint | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isDeciding, setIsDeciding] = useState(false);
  const [error, setError] = useState('');
  const [loadingRun, setLoadingRun] = useState(Boolean(initialRunId));
  const [reload, setReload] = useState(0);
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null);

  useEffect(() => {
    if (!initialRunId) return;
    let active = true;
    setLoadingRun(true);
    setError('');
    void getRun(initialRunId).then((record) => { if (active) setRun(record); })
      .catch((reason: unknown) => { if (active) setError(reason instanceof Error ? reason.message : '读取任务失败。'); })
      .finally(() => { if (active) setLoadingRun(false); });
    return () => { active = false; };
  }, [initialRunId, reload]);

  const runId = run?.id;
  const runStatus = run?.status;
  useEffect(() => { setSelectedCandidateId(null); }, [runId, checkpoint?.round_number]);

  useEffect(() => {
    if (!runId || !runStatus) {
      return undefined;
    }
    let active = true;
    let timer: number | undefined;
    const stopEvents = subscribeRunEvents(
      runId,
      (event) => { if (active) setEvents((current) => (
        event.created_at && current.some((item) => item.created_at === event.created_at)
          ? current
          : [...current, event]
      )); },
      () => undefined,
    );
    async function refresh() {
      let repeat = false;
      try {
        if (runStatus === 'waiting_for_human') {
          const pending = await getPendingHumanInput(runId!);
          if (active) setCheckpoint(pending);
        } else if (runStatus === 'completed') {
          const completed = await getRunResult(runId!);
          if (active) { setResult(completed); setCheckpoint(null); }
        } else if (runStatus !== 'failed') {
          const next = await getRun(runId!);
          if (active) setRun(next);
          repeat = next.status === runStatus;
        }
        if (active) setError('');
      } catch (reason) {
        if (active) setError(reason instanceof Error ? reason.message : '读取任务状态失败。');
        repeat = true;
      }
      if (active && repeat) timer = window.setTimeout(() => void refresh(), 1500);
    }
    void refresh();
    return () => {
      active = false;
      stopEvents();
      window.clearTimeout(timer);
    };
  }, [runId, runStatus]);

  async function submit(brief: PosterBriefInput) {
    setIsSubmitting(true);
    setError('');
    setEvents([]);
    setCheckpoint(null);
    setResult(null);
    try {
      const created = await createRun(brief);
      setRun(created);
      openRun(created.id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '创建任务失败。');
    } finally {
      setIsSubmitting(false);
    }
  }

  async function decide(decision: HumanDecision) {
    if (!run || !checkpoint) return;
    setIsDeciding(true);
    setError('');
    try {
      const next = await submitHumanDecision(run.id, decision, checkpoint.round_number);
      setRun(next);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '提交人工决策失败。');
    } finally {
      setIsDeciding(false);
    }
  }

  function resetWorkspace() {
    window.location.hash = 'workspace';
    setRun(null);
    setResult(null);
    setCheckpoint(null);
    setEvents([]);
    setError('');
  }

  return (
    <main className="workspace-shell">
      {import.meta.env.VITE_POSTERPILOT_DEMO === 'true' ? (
        <p role="note">{import.meta.env.VITE_POSTERPILOT_SHOWCASE === 'true'
          ? '授权素材排版演示：背景来自已审核的公共领域图片，规划与修改动作固定；实际渲染和规则检查，不调用生图模型或 DeepGaze。'
          : '离线流程演示：模型决策和背景是固定测试素材，不代表真实生成质量；未调用付费服务。'}</p>
      ) : null}
      <header className="workspace-topbar">
        <div>
          <a className="wordmark" href="/" aria-label="PosterPilot 首页">
            PosterPilot
          </a>
          <span>海报创作工作台</span>
        </div>
        <div className="topbar-actions">
          <ThemeSelect />
          <a className="text-action" href={run ? `#datahub/${run.id}` : '#datahub'}>案例与反馈</a>
          {run ? <button className="text-action" type="button" onClick={resetWorkspace}>新建任务</button> : null}
          <button className="text-action" type="button" onClick={onOpenHistory}>任务历史</button>
        </div>
      </header>
      <section className="workspace-intro" aria-label="当前创作阶段">
        <div>
          <p className="section-kicker">CREATIVE WORKSPACE</p>
          <h1>{!run ? '把活动变成一张海报' : run.status === 'waiting_for_human' ? '看看结果，决定下一步' : run.status === 'completed' ? '这一轮创作，已保存' : run.status === 'failed' ? '任务未完成，请查看原因' : '正在准备你的海报'}</h1>
          <p>{!run ? '先填写活动信息，画面和排版交给系统。初版完成后，你可以继续提出修改要求。' : run.status === 'failed' ? '请先查看错误原因。当前任务已停止；处理问题后，可新建任务重新提交。' : '查看海报版本、评测依据与执行记录。你可以决定是否继续；最多优化三轮，达到上限后保存结果。'}</p>
        </div>
        <ol className="workspace-steps">
          {['填写需求', '生成评测', '确认与优化'].map((label, index) => {
            const active = !run ? 0 : checkpoint || result || run.status === 'waiting_for_human' ? 2 : 1;
            return <li key={label} className={index === active ? 'is-current' : index < active ? 'is-done' : ''} aria-current={index === active ? 'step' : undefined}><span>0{index + 1}</span>{label}</li>;
          })}
        </ol>
      </section>
      {loadingRun || (initialRunId && !run) ? (
        <section className="workspace-loading">
          {loadingRun ? <p role="status">正在恢复任务…</p> : <><p className="inline-error" role="alert">{error}</p><button className="secondary-action" onClick={() => setReload((value) => value + 1)}>重新读取任务</button></>}
        </section>
      ) : !run ? (
        <div className="workspace-grid">
          <BriefForm onSubmit={submit} isSubmitting={isSubmitting} />
          <div className="workspace-output">
            {error ? <p className="inline-error" role="alert">{error}</p> : null}
            <PosterPreview status={null} />
            <AgentTimeline status={null} events={events} />
          </div>
        </div>
      ) : (
        <div className="react-workbench">
          <section className="poster-workbench">
          {error || run.error_message ? <p className="inline-error" role="alert">{error || run.error_message}</p> : null}
          {checkpoint || result ? (
            <RoundGallery
              runId={run.id}
              initialAttentionArtifact={
                checkpoint
                  ? checkpoint.initial_attention_artifact ?? (checkpoint.round_number === 0 ? checkpoint.attention_artifact : undefined)
                  : result?.evaluation_initial.attention.heatmap_artifact
              }
              rounds={checkpoint?.rounds ?? result?.rounds ?? []}
              initialAnalysis={checkpoint?.initial_analysis ?? (checkpoint?.round_number === 0 ? checkpoint.analysis : result?.analysis_initial)}
              initialScore={
                checkpoint?.round_number === 0
                  ? checkpoint.score
                  : result?.evaluation_initial.scores.total
              }
            />
          ) : (
            <PosterPreview status={run.status} />
          )}
          {checkpoint?.layout_candidates && <CandidatePicker runId={run.id} candidates={checkpoint.layout_candidates} selectedId={selectedCandidateId} onSelect={setSelectedCandidateId} disabled={isDeciding || run.status !== 'waiting_for_human'} />}
          <AgentTimeline status={run.status} events={events} />
          {result ? (
            <>
              <BeforeAfter
                result={result}
                initialUrl={artifactUrl(run.id, 'poster_initial.png')}
                optimizedUrl={artifactUrl(
                  run.id,
                  result.rounds?.at(-1)?.poster_artifact ?? 'poster_initial.png',
                )}
              />
              <EvaluationPanel result={result} />
            </>
          ) : null}
          </section>
          <AgentConsole
            key={`${run.id}:${checkpoint?.round_number ?? 'inactive'}`}
            status={run.status}
            checkpoint={checkpoint}
            events={events}
            completedRounds={result?.rounds}
            isSubmitting={isDeciding}
            onApprove={() => void decide({ action: 'approve' })}
            onInstruct={(instruction) => void decide({ action: 'instruct', instruction })}
            onFinish={() => void decide({ action: 'finish' })}
            onControlledDecision={decision => void decide(decision)}
            selectedCandidateId={selectedCandidateId}
          />
        </div>
      )}
    </main>
  );
}
