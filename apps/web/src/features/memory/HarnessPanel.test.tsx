import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { HarnessPanel } from './HarnessPanel';

afterEach(() => vi.unstubAllGlobals());

it('submits every resolution source and preserves the incomplete-coverage error', async () => {
  const gap = { id: 'gap', revision: 2, category: 'infrastructure', status: 'open', signature: 'run:timeout', origin: 'runtime', occurrences: 2, observations: [] };
  const fetchMock = vi.fn(async (url: string, options?: RequestInit) => {
    if (options?.method === 'POST') return { ok: false, json: async () => ({ error: { message: '解决证据仅覆盖部分原始需求' } }) };
    return { ok: true, json: async () => url.endsWith('/gaps') ? [gap] : [] };
  });
  vi.stubGlobal('fetch', fetchMock);
  render(<HarnessPanel />);
  await screen.findByText('run:timeout · 2 次');
  fireEvent.change(screen.getByLabelText('判断依据'), { target: { value: '两份需求分别重跑验收' } });
  fireEvent.change(screen.getByLabelText(/解决证据案例 ID/), { target: { value: 'first-id，second-id\nthird-id' } });
  fireEvent.click(screen.getByRole('button', { name: '核对证据并标记解决' }));
  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('解决证据仅覆盖部分原始需求'));
  const call = fetchMock.mock.calls.find(([, options]) => options?.method === 'POST');
  expect(JSON.parse(call?.[1]?.body as string)).toEqual({
    expected_revision: 2, category: 'infrastructure', note: '两份需求分别重跑验收',
    resolution_case_ids: ['first-id', 'second-id', 'third-id'], resolution_tool: null,
  });
  expect(screen.queryByText('已保存分类与验收记录。')).not.toBeInTheDocument();
});
