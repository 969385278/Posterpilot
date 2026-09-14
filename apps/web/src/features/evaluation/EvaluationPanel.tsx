import type { RunResult } from '../../api/client';

type EvaluationPanelProps = {
  result: RunResult;
};

export function EvaluationPanel({ result }: EvaluationPanelProps) {
  const deltaLabel = result.score_delta === null
    ? '不可直接比较'
    : result.score_delta > 0 ? `+${result.score_delta}` : `${result.score_delta}`;

  return (
    <section className="evaluation-panel" aria-label="评测结果">
      <p className="section-kicker">复评结果</p>
      <div>
        <dl>
          <div>
            <dt>初版综合评分</dt>
            <dd>{result.evaluation_initial.scores.total}</dd>
          </div>
          <div>
            <dt>优化版综合评分</dt>
            <dd>{result.evaluation_optimized.scores.total}</dd>
          </div>
          <div>
            <dt>评分变化</dt>
            <dd>{deltaLabel}</dd>
          </div>
        </dl>
        <p>可用评测权重：{result.evaluation_optimized.scores.available_weight}/100</p>
        {result.comparison_reason && <p role="note">{result.comparison_reason}</p>}
      </div>
    </section>
  );
}
