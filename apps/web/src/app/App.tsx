import { useEffect, useState } from 'react';
import { readRoute } from './navigation';

import { HistoryPage } from '../pages/HistoryPage';
import { WorkspacePage } from '../pages/WorkspacePage';
import { ThemeSelect } from '../features/theme/ThemeSelect';

const workflow = [
  { title: '描述你的活动', description: '填写主题、时间与地点，把创作意图交给系统。' },
  { title: '生成与评测', description: '结合设计知识完成画面与排版，呈现评测依据。' },
  { title: '由你决定下一步', description: '接受当前版本，或提出要求让 Agent 继续调整。' },
];

export function App() {
  const [route, setRoute] = useState(readRoute);
  const page = route.page;
  useEffect(() => {
    const update = () => setRoute(readRoute());
    window.addEventListener('hashchange', update);
    return () => window.removeEventListener('hashchange', update);
  }, []);
  function navigate(page: 'home' | 'workspace' | 'history') {
    window.location.hash = page;
    setRoute({ page });
  }

  if (page === 'workspace') {
    return <WorkspacePage key={route.runId ?? 'new'} initialRunId={route.runId} onOpenHistory={() => navigate('history')} />;
  }

  if (page === 'history') {
    return <HistoryPage onBack={() => navigate('workspace')} />;
  }

  return (
    <main className="app-shell">
      <header className="topbar" aria-label="主导航">
        <a className="wordmark" href="/" aria-label="PosterPilot 首页">
          PosterPilot
        </a>
        <span className="topbar-context">海报创作工作台</span>
        <ThemeSelect />
      </header>

      <section className="hero" aria-labelledby="hero-title">
        <div className="hero-copy">
          <p className="eyebrow">海报生成优化 Agent</p>
          <h1 id="hero-title">从一个想法，<br />到一张好海报。</h1>
          <p className="hero-summary">
            描述活动，生成画面与中文排版。查看评测依据，再由你决定如何调整，让每一轮创作都有方向。
          </p>
          <button className="primary-action" type="button" onClick={() => navigate('workspace')}>
            创建海报
          </button>
          <p className="hero-footnote">校园讲座 · 文化活动 · 社团招新</p>
        </div>

        <div className="hero-visual">
          <img
            src="/templates/default-poster-portrait.png"
            alt="红楼梦文化活动海报示例"
            width="1080"
            height="1440"
          />
          <div className="hero-caption"><span>创作示例</span><strong>画面、文字与设计依据</strong></div>
        </div>
      </section>

      <section className="workflow" aria-label="工作流程">
        {workflow.map((item, index) => (
          <div className="workflow-item" key={item.title}>
            <span className="workflow-number">0{index + 1}</span>
            <strong>{item.title}</strong>
            <p>{item.description}</p>
          </div>
        ))}
      </section>
    </main>
  );
}
