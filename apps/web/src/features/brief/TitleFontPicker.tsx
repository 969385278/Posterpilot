import { useEffect, useState } from 'react';
import type { PosterBriefInput } from '../../api/client';

type FontId = NonNullable<PosterBriefInput['title_font']>;
const choices: { id: FontId; name: string; description: string }[] = [
  { id: 'auto', name: '自动匹配', description: '文化活动偏装饰宋体，社团招新偏活泼手写，讲座偏窄长标题；选择案例字体时优先参考案例。' },
  { id: 'standard', name: '常规粗体', description: '清晰稳重，适合长标题和正式内容。' },
  { id: 'mashanzheng', name: '马善政毛笔体', description: '厚实毛笔，适合国风、传统文化标题。' },
  { id: 'longcang', name: '龙藏体', description: '疏朗手写，适合文艺、书信感标题。' },
  { id: 'zhimangxing', name: '志莽行书', description: '连笔行草，适合短标题；长文字慎用。' },
  { id: 'zcoolkuaile', name: '站酷快乐体', description: '活泼不规则笔画，适合招新、趣味活动。' },
  { id: 'zcoolqingkehuangyou', name: '站酷庆科黄油体', description: '窄长圆角字形，适合现代醒目标题。' },
  { id: 'zcoolxiaowei', name: '站酷小薇体', description: '装饰宋体气质，适合文化、展览标题。' },
];

export function TitleFontPicker({ value, title, onChange, disabled }: {
  value: FontId; title: string; onChange: (value: FontId) => void; disabled: boolean;
}) {
  const [previewText, setPreviewText] = useState(title);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setPreviewText(title), 250);
    return () => clearTimeout(timer);
  }, [title]);
  useEffect(() => setFailed(false), [value, previewText]);
  const choice = choices.find(item => item.id === value)!;
  return <div className="form-span title-font-picker">
    <label>主标题字体
      <select value={value} onChange={event => onChange(event.target.value as FontId)} disabled={disabled}>
        {choices.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
      </select>
    </label>
    <p className="design-help">{choice.description}</p>
    {value !== 'auto' && <>
      {!failed ? <img style={{ width: '100%', maxWidth: 550, borderRadius: 8 }}
        src={`/api/v1/title-fonts/${value}/preview?text=${encodeURIComponent((previewText.trim() || '摄影社招新').slice(0, 120))}`}
        alt={`${choice.name}标题字形预览`} onError={() => setFailed(true)} />
        : <p role="status">字体预览暂不可用，请确认后端服务已启动。</p>}
      <p className="design-help">预览展示字形，不是最终字号与排版；手动选择优先于案例推荐。缺字时整标题回退常规粗体，实际字体见生成后的分析。</p>
    </>}
    {value !== 'auto' && value !== 'standard' && <a href={`https://github.com/google/fonts/tree/main/ofl/${value}`} target="_blank" rel="noreferrer">开源来源与许可（SIL OFL 1.1）</a>}
  </div>;
}
