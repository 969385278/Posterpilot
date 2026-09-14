import { useEffect, useState } from 'react';

type Theme = 'system' | 'light' | 'dark';

function readTheme(): Theme {
  try {
    const saved = localStorage.getItem('posterpilot-theme');
    return saved === 'light' || saved === 'dark' ? saved : 'system';
  } catch { return 'system'; }
}

export function ThemeSelect() {
  const [theme, setTheme] = useState<Theme>(readTheme);
  useEffect(() => {
    if (theme === 'system') delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = theme;
    try { localStorage.setItem('posterpilot-theme', theme); } catch { /* Storage is optional. */ }
  }, [theme]);
  return (
    <select className="theme-select" aria-label="页面外观" value={theme}
      onChange={(event) => setTheme(event.target.value as Theme)}>
      <option value="system">跟随系统</option>
      <option value="light">浅色</option>
      <option value="dark">深色</option>
    </select>
  );
}
