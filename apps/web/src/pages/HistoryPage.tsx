import { useEffect, useState } from 'react';

import { listRuns, type RunRecord } from '../api/client';
import { RunHistory } from '../features/history/RunHistory';
import { ThemeSelect } from '../features/theme/ThemeSelect';

type HistoryPageProps = {
  onBack: () => void;
};

export function HistoryPage({ onBack }: HistoryPageProps) {
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    void listRuns().then((records) => { if (active) setRuns(records); }).catch((reason: unknown) => {
      if (active) setError(reason instanceof Error ? reason.message : '读取任务历史失败。');
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  return (
    <main className="workspace-shell">
      <header className="workspace-topbar">
        <div>
          <a className="wordmark" href="/" aria-label="PosterPilot 首页">
            PosterPilot
          </a>
          <span>本地任务历史</span>
        </div>
        <div className="topbar-actions"><ThemeSelect /><button className="text-action" type="button" onClick={onBack}>
          返回工作台
        </button></div>
      </header>
      <section className="history-page" aria-labelledby="history-title">
        <p className="section-kicker">任务历史</p>
        <h1 id="history-title">保留每次生成和优化的结果。</h1>
        {loading ? <p role="status">正在读取任务历史…</p> : error ? <p className="inline-error" role="alert">{error}</p> : <RunHistory runs={runs} />}
      </section>
    </main>
  );
}
