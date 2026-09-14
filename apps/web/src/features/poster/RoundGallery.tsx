import { useEffect, useMemo, useState } from 'react';

import { artifactUrl, type RoundSnapshot } from '../../api/client';
import { AttentionMap } from '../evaluation/AttentionMap';
import { AnalysisPanel, VerificationPanel } from '../design/AnalysisPanel';
import type { PosterAnalysis } from '../../api/design';

type RoundGalleryProps = {
  runId: string;
  rounds: RoundSnapshot[];
  initialScore?: number;
  initialAttentionArtifact?: string | null;
  initialAnalysis?: PosterAnalysis | null;
};

export function RoundGallery({ runId, rounds, initialScore, initialAttentionArtifact, initialAnalysis }: RoundGalleryProps) {
  const versions = useMemo(
    () => [
      {
        key: 'initial',
        label: '初版',
        artifact: 'poster_initial.png',
        score: initialScore,
        attentionArtifact: initialAttentionArtifact,
        comparisonReason: null,
        analysis: initialAnalysis,
        verification: null,
      },
      ...rounds.map((round) => ({
        key: `round-${round.round_number}`,
        label: `第 ${round.round_number} 轮`,
        artifact: round.poster_artifact,
        score: round.score,
        attentionArtifact: round.attention_artifact,
        comparisonReason: round.comparison_reason,
        analysis: round.analysis,
        verification: round.goal_verification,
      })),
    ],
    [initialScore, initialAttentionArtifact, initialAnalysis, rounds],
  );
  const [selected, setSelected] = useState('initial');
  useEffect(() => {
    setSelected(rounds.length ? `round-${rounds.at(-1)!.round_number}` : 'initial');
  }, [rounds]);
  const current = versions.find((version) => version.key === selected) ?? versions.at(-1)!;

  return (
    <section className="round-gallery" aria-label="轮次海报">
      <div className="round-tabs">
        {versions.map((version) => (
          <button
            type="button"
            key={version.key}
            className={current.key === version.key ? 'is-active' : ''}
            onClick={() => setSelected(version.key)}
          >
            {version.label}{version.score === undefined ? '' : ` · ${version.score.toFixed(1)}`}
          </button>
        ))}
      </div>
      <div className="round-poster-frame">
        <img src={artifactUrl(runId, current.artifact)} alt={`${current.label}海报`} />
      </div>
      {current.comparisonReason && <p role="note">{current.comparisonReason}</p>}
      <AnalysisPanel analysis={current.analysis} />
      <VerificationPanel verification={current.verification} />
      {current.attentionArtifact !== undefined && (
        <details className="round-attention">
          <summary>查看{current.label}注意力预测</summary>
          <AttentionMap
            imageUrl={current.attentionArtifact ? artifactUrl(runId, current.attentionArtifact) : undefined}
            availability={current.attentionArtifact ? 'available' : 'unavailable'}
          />
        </details>
      )}
    </section>
  );
}
