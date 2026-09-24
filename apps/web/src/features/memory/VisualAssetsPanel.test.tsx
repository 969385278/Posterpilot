import { fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { VisualAssetsPanel } from './VisualAssetsPanel';

afterEach(() => vi.unstubAllGlobals());
const asset = { id: 'asset-1', revision: 3, status: 'candidate', metadata: { title: '星空海报', description: '夜空', composition: '上方留白', visible_text: '', cautions: '', styles: [], scenarios: ['campus_lecture'] }, sources: [{ creator: '测试作者', source_url: null, rights: '测试使用', origin: 'original' }], measured: { width: 64, height: 96, palette: [{ color: '#000080', fraction: 1 }] }, near_duplicates: [], enrichment: { proposal: { title: '模型标题', description: '模型描述', composition: '顶部文字', visible_text: '', cautions: '', styles: [], scenarios: ['campus_lecture'] } }, audit: [], image_sha256: 'hash' };

it('keeps model proposals as editable drafts and requires saving before review', async () => {
  const fetcher = vi.fn(async (_url: string, options?: RequestInit) => ({ ok: true, json: async () => options ? {} : [asset] }));
  vi.stubGlobal('fetch', fetcher);
  render(<VisualAssetsPanel />);
  fireEvent.click(await screen.findByRole('button', { name: /星空海报/ }));
  const editor = within(screen.getByRole('region', { name: '素材详情' }));
  fireEvent.change(editor.getByLabelText('素材审查人'), { target: { value: '审查人' } });
  fireEvent.change(editor.getByLabelText('素材审查说明'), { target: { value: '核对完成' } });
  expect(editor.getByRole('button', { name: '审核并允许引用' })).toBeDisabled();
  fireEvent.click(editor.getByLabelText('已核对所有来源的使用权、描述及适用范围'));
  expect(editor.getByRole('button', { name: '审核并允许引用' })).toBeEnabled();
  fireEvent.click(editor.getByRole('button', { name: '将候选填入编辑区' }));
  expect(editor.getByLabelText('素材标题')).toHaveValue('模型标题');
  expect(editor.getByRole('button', { name: '审核并允许引用' })).toBeDisabled();
  expect(fetcher.mock.calls.filter(([, options]) => options)).toHaveLength(0);
});

it('shows lexical fallback and never labels missing vectors as semantic results', async () => {
  vi.stubGlobal('fetch', vi.fn(async (_url: string, options?: RequestInit) => ({ ok: true, json: async () => options ? { mode: 'lexical_fallback', fallback_reason: '没有当前版本的语义索引', matches: [] } : [] })));
  render(<VisualAssetsPanel />);
  fireEvent.change(screen.getByLabelText('检索需求'), { target: { value: '星空' } });
  fireEvent.click(screen.getByRole('button', { name: '检索已审核素材' }));
  expect(await screen.findByText(/词法检索 · 没有当前版本/)).toBeInTheDocument();
  expect(screen.queryByText(/语义与词法混合检索/)).not.toBeInTheDocument();
});
