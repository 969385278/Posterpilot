import type { RunRecord } from '../../api/client';

type RunHistoryProps = {
  runs: RunRecord[];
};

export function RunHistory({ runs }: RunHistoryProps) {
  if (!runs.length) {
    return <p className="history-empty">还没有任务记录。创建第一张海报后，它会保留在这里。</p>;
  }
  return (
    <ol className="run-history">
      {runs.map((run) => (
        <li key={run.id}>
          <div>
            <a className="history-run-link" href={`#runs/${run.id}`}>打开海报任务</a>
            <span>{run.id.slice(0, 8)}</span>
          </div>
          <span className="status-label">{statusLabel(run.status)}</span>
        </li>
      ))}
    </ol>
  );
}

function statusLabel(status: RunRecord['status']): string {
  if (status === 'waiting_for_human') return '等待人工决策';
  if (status === 'running') return '执行中';
  if (status === 'completed') return '已完成';
  if (status === 'failed') return '失败';
  return '排队中';
}
