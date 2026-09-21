import { useState } from 'react';
import { askDesign, confirmDesign, type DesignAnswer } from '../../api/assistant';
import type { RunRecord } from '../../api/client';
import '../../styles/assistant.css';

type Props = { run?: RunRecord | null; roundNumber?: number; onModified: (run: RunRecord) => void };
const toolLabels: Record<string, string> = { search_knowledge: '检索设计知识', search_cases: '检索审核案例', inspect_poster: '查看海报评测', analyze_image: '分析当前图片', read_history: '查看修改历史' };

export function DesignAssistant({ run, roundNumber, onModified }: Props) {
  const [question, setQuestion] = useState('');
  const [answers, setAnswers] = useState<DesignAnswer[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [confirming, setConfirming] = useState<string | null>(null);
  const [applied, setApplied] = useState<string[]>([]);

  async function ask() {
    if (!question.trim() || busy) return;
    setBusy(true); setError('');
    try {
      const answer = await askDesign(question.trim(), run?.id, answers.at(-1)?.conversation_id);
      setAnswers(current => [...current, answer]); setQuestion('');
    } catch (reason) { setError(reason instanceof Error ? reason.message : '问答失败。'); }
    finally { setBusy(false); }
  }

  async function confirm(answer: DesignAnswer) {
    setConfirming(answer.id); setError('');
    try {
      const next = await confirmDesign(answer.id);
      setApplied(current => [...current, answer.id]); onModified(next);
    } catch (reason) { setError(reason instanceof Error ? reason.message : '修改提交失败。'); }
    finally { setConfirming(null); }
  }

  return <section className="design-assistant" aria-label="海报设计助手">
    <header><div><h2>设计助手</h2><p>{run ? '围绕当前海报，解释问题、查找依据、讨论修改。' : '可以先聊配色、字体和构图，再开始创作。'}</p></div>
      {answers.length > 0 && <button type="button" className="text-action" disabled={busy || confirming !== null} onClick={() => { setAnswers([]); setError(''); }}>新对话</button>}
    </header>
    <div className="design-chat" aria-live="polite">
      {answers.map(answer => <article key={answer.id}>
        <p className="design-question">{answer.question}</p>
        <p className="design-answer">{answer.answer}</p>
        {answer.degraded && <small>当前为降级响应，未生成可执行修改。</small>}
        {answer.trace.length > 0 && <details><summary>查看工具记录 · {answer.trace.length} 步</summary><ol>{answer.trace.map((item, index) => <li key={index}>{toolLabels[item.tool] || item.tool}：{item.success ? item.summary : `不可用，${item.summary}`}</li>)}</ol></details>}
        {answer.citations.length > 0 && <details><summary>参考依据 · {answer.citations.length} 条</summary>{answer.citations.map(citation => <blockquote key={citation.id}><strong>{citation.title}</strong><p>{citation.excerpt}</p><small>{citation.source}</small></blockquote>)}</details>}
        {answer.proposal && <div className="design-proposal"><strong>待确认的修改建议</strong><p>{answer.proposal.instruction}</p>
          <small>确认后进入现有优化轮次，不保证得分提升。当前只支持排版与整体色彩调整，不重绘主视觉。</small>
          <button className="secondary-action" type="button" disabled={busy || confirming !== null || applied.includes(answer.id) || run?.status !== 'waiting_for_human' || answer.round_number !== roundNumber}
            onClick={() => void confirm(answer)}>{applied.includes(answer.id) ? '已提交修改' : confirming === answer.id ? '正在提交…' : answer.round_number !== roundNumber ? '建议已过期，请重新提问' : '确认修改这张海报'}</button>
        </div>}
      </article>)}
    </div>
    <form onSubmit={event => { event.preventDefault(); void ask(); }}>
      <label htmlFor="design-question">你的设计问题</label>
      <textarea id="design-question" value={question} maxLength={1000} rows={3} placeholder={run ? '为什么标题不够醒目？怎样调整，同时保留主视觉？' : '社团招新海报怎样安排标题和活动信息？'} onChange={event => setQuestion(event.target.value)} disabled={busy} />
      <div className="design-question-actions"><small>问答不会自动修改海报。</small><button className="secondary-action" disabled={busy || !question.trim() || confirming !== null}>{busy ? '正在检索与分析…' : '发送问题'}</button></div>
    </form>
    {error && <p role="alert" className="inline-error">{error}</p>}
  </section>;
}
