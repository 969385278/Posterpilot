import type { RunResult } from '../../api/client';

type BeforeAfterProps = {
  result: RunResult;
  initialUrl: string;
  optimizedUrl: string;
};

export function BeforeAfter({ result, initialUrl, optimizedUrl }: BeforeAfterProps) {
  return (
    <section className="before-after" aria-label="初版与优化版对比">
      <div className="comparison-heading">
        <div>
          <p className="section-kicker">前后对比</p>
          <h2>{result.outcome === 'improved' ? '优化后评分提升' : '保留真实复评结果'}</h2>
        </div>
      </div>
      <div className="comparison-images">
        <figure>
          <img src={initialUrl} alt="初版海报" />
          <figcaption>初版</figcaption>
        </figure>
        <figure>
          <img src={optimizedUrl} alt="优化版海报" />
          <figcaption>优化版</figcaption>
        </figure>
      </div>
    </section>
  );
}
