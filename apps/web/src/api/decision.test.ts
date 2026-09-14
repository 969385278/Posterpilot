import { afterEach, expect, it, vi } from 'vitest';
import { submitHumanDecision } from './client';

afterEach(() => vi.unstubAllGlobals());

it('sends a required round precondition with the human decision', async () => {
  const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'running' }) });
  vi.stubGlobal('fetch', fetch);
  await submitHumanDecision('run-id', { action: 'approve' }, 2);
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({
    action: 'approve', expected_round_number: 2,
  });
});

it('does not retry a conflict or silently use a newer round', async () => {
  const fetch = vi.fn().mockResolvedValue({ ok: false, status: 409 });
  vi.stubGlobal('fetch', fetch);
  await expect(submitHumanDecision('run-id', { action: 'finish' }, 0)).rejects.toThrow('刷新');
  expect(fetch).toHaveBeenCalledTimes(1);
});
