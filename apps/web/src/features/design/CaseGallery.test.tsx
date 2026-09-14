import { useState } from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { CaseGallery } from './CaseGallery';
import { caseFixture } from './fixtures';
import type { ReferenceSelection } from '../../api/design';

afterEach(() => vi.unstubAllGlobals());
describe('case Wiki', () => {
  it('loads actual API entries, exposes dimensions and selects only the requested one', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => [caseFixture] }));
    function Harness() { const [value, onChange] = useState<ReferenceSelection[]>([]); return <CaseGallery value={value} onChange={onChange} />; }
    render(<Harness />);
    fireEvent.click(await screen.findByRole('button', { name: /测试蓝橙海报/ }));
    fireEvent.click(screen.getByRole('checkbox', { name: /参考配色/ }));
    expect(screen.getByLabelText('已选参考')).toHaveTextContent('测试蓝橙海报：配色');
    expect(screen.getByRole('checkbox', { name: /参考字体气质/, hidden: true })).not.toBeChecked();
    fireEvent.change(screen.getByLabelText('搜索案例'), { target: { value: '不存在' } });
    expect(screen.getByText('没有匹配的案例，试试其他关键词。')).toBeInTheDocument();
    expect(screen.getByLabelText('已选参考')).toHaveTextContent('配色');
  });
  it('recovers from an API failure with explicit retry', async () => {
    const fetch = vi.fn().mockResolvedValueOnce({ ok: false }).mockResolvedValue({ ok: true, json: async () => [] });
    vi.stubGlobal('fetch', fetch);
    render(<CaseGallery value={[]} onChange={vi.fn()} />);
    expect(await screen.findByRole('alert')).toHaveTextContent('案例库暂时无法读取');
    fireEvent.click(screen.getByRole('button', { name: '重新读取案例' }));
    expect(await screen.findByText('案例库暂无已整理素材，可以先直接生成海报。')).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledTimes(2);
  });
});
