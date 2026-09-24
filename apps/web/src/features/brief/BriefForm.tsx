import { useEffect, useState, type FormEvent } from 'react';

import type { PosterBriefInput } from '../../api/client';
import { CaseGallery } from '../design/CaseGallery';
import { PriorityEditor } from '../design/PriorityEditor';
import { TitleFontPicker } from './TitleFontPicker';
import type { PriorityRole } from '../../api/design';
import showcase from '../../data/showcase.json';

type BriefFormProps = {
  onSubmit: (brief: PosterBriefInput) => void;
  isSubmitting: boolean;
  suggestedBrief?: Partial<PosterBriefInput>;
};

const blankBrief: PosterBriefInput = {
  poster_type: 'cultural_event',
  topic: '',
  target_audience: '',
  title: '',
  subtitle: '',
  event_time: '',
  location: '',
  organizer: '',
  style_preferences: [],
  color_preferences: [],
  visual_elements: [],
  avoid_elements: [],
  notes: '',
};

export function BriefForm({ onSubmit, isSubmitting, suggestedBrief }: BriefFormProps) {
  const [brief, setBrief] = useState<PosterBriefInput>(blankBrief);
  const [showCases, setShowCases] = useState(false);
  useEffect(() => {
    if (suggestedBrief) setBrief({ ...blankBrief, ...suggestedBrief, subtitle: suggestedBrief.subtitle ?? '' });
  }, [suggestedBrief]);

  function update(field: keyof PosterBriefInput, value: string) {
    setBrief((current) => {
      const next = { ...current, [field]: value };
      next.attention_priority = current.attention_priority?.filter(role => availableRoles(next).includes(role));
      return next;
    });
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit({ ...brief, title: brief.title.trim(), topic: brief.topic.trim() || brief.title.trim() });
  }

  return (
    <form className="brief-form" onSubmit={submit}>
      <div className="brief-form-heading">
        <div>
          <p className="section-kicker">需求输入</p>
          <h2>创建一张可优化的海报</h2>
        </div>
      </div>

      <div className="form-span sample-briefs" aria-label="虚构活动样例">
        <span>填入样例：</span>
        {showcase.entries.map(sample => <button className="text-action" type="button" key={sample.id}
          disabled={isSubmitting} onClick={() => setBrief({ ...blankBrief, ...sample.brief,
            attention_layout: true, use_case_memory: true } as PosterBriefInput)}>{sample.label}</button>)}
        <p className="form-description">仅填入虚构活动信息，不会立即提交。正式环境仍调用已配置的模型，不会直接复制展示背景。</p>
      </div>

      <p className="form-description form-span">只有主标题必填。主题留空时沿用标题；其他信息按需填写，未填写的时间、地点和主办方不会显示。</p>

      <label>
        海报类型
        <select value={brief.poster_type} onChange={(event) => update('poster_type', event.target.value)}>
          <option value="cultural_event">文化活动</option>
          <option value="campus_lecture">校园讲座</option>
          <option value="club_recruitment">社团招新</option>
        </select>
      </label>
      <label>
        活动主题
        <input placeholder="可选，留空沿用主标题" value={brief.topic} onChange={(event) => update('topic', event.target.value)} />
      </label>
      <label>
        主标题
        <input required pattern=".*\S.*" title="请输入非空的主标题" value={brief.title} onChange={(event) => update('title', event.target.value)} />
      </label>
      <label>
        副标题
        <input value={brief.subtitle} onChange={(event) => update('subtitle', event.target.value)} />
      </label>
      <TitleFontPicker value={brief.title_font ?? 'auto'} title={brief.title} disabled={isSubmitting}
        onChange={title_font => setBrief(current => ({ ...current, title_font }))} />
      <label>
        时间
        <input placeholder="可选，不填则不显示" value={brief.event_time} onChange={(event) => update('event_time', event.target.value)} />
      </label>
      <label>
        地点
        <input placeholder="可选，不填则不显示" value={brief.location} onChange={(event) => update('location', event.target.value)} />
      </label>
      <label>
        主办方
        <input placeholder="可选，不填则不显示" value={brief.organizer} onChange={(event) => update('organizer', event.target.value)} />
      </label>
      <label>
        目标受众
        <input
          placeholder="可选，例如：大学生"
          value={brief.target_audience}
          onChange={(event) => update('target_audience', event.target.value)}
        />
      </label>
      <label className="form-span">
        视觉偏好
        <textarea
          value={brief.notes}
          placeholder="例如：避免复杂装饰，主标题需清晰可见"
          onChange={(event) => update('notes', event.target.value)}
        />
      </label>
      <details className="form-span brief-cases" onToggle={event => setShowCases(event.currentTarget.open)}>
        <summary>选择参考海报（可选，已选 {brief.references?.length ?? 0} 张）</summary>
        {showCases && <CaseGallery value={brief.references ?? []} disabled={isSubmitting} onChange={references => setBrief(current => ({ ...current, references }))} />}
      </details>
      <details className="form-span"><summary>设置注意力辅助排版</summary>
        <label className="inline-checkbox"><input type="checkbox" checked={brief.attention_layout ?? true} onChange={event => setBrief(current => ({ ...current, attention_layout: event.target.checked }))} />生成后提供候选排版供我比较</label>
        <PriorityEditor value={brief.attention_priority ?? []} available={availableRoles(brief)} onChange={attention_priority => setBrief(current => ({ ...current, attention_priority }))} disabled={isSubmitting} />
      </details>
      <button className="primary-action form-span" type="submit" disabled={isSubmitting}>
        {isSubmitting ? '正在创建任务' : '开始生成'}
      </button>
      <label className="inline-checkbox form-span"><input type="checkbox" checked={brief.use_case_memory ?? true} disabled={isSubmitting} onChange={event => setBrief(current => ({ ...current, use_case_memory: event.target.checked }))} />参考已审核的历史经验（不匹配时沿用原流程）</label>
      <label className="inline-checkbox form-span"><input type="checkbox" checked={brief.use_user_memory ?? false} disabled={isSubmitting} onChange={event => setBrief(current => ({ ...current, use_user_memory: event.target.checked }))} />使用本机用户已确认的设计偏好（本次要求优先）</label>
      <p className="form-footnote form-span">生成可能需要一些时间。初版完成后，你可以选择保留结果或继续优化。</p>
    </form>
  );
}

function availableRoles(brief: PosterBriefInput): PriorityRole[] {
  const roles: PriorityRole[] = ['title', 'main_visual'];
  if (brief.subtitle?.trim()) roles.push('subtitle');
  if (brief.event_time.trim() || brief.location.trim()) roles.push('event_info');
  if (brief.organizer.trim()) roles.push('organizer');
  return roles;
}
