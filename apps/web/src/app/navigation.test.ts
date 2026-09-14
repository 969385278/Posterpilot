import { afterEach, describe, expect, it } from 'vitest';
import { readRoute } from './navigation';

describe('reloadable task addresses', () => {
  afterEach(() => window.history.replaceState(null, '', '/'));
  it('restores a task route from the browser address', () => {
    window.history.replaceState(null, '', '/#runs/12345678-aaaa-bbbb-cccc-dddddddddddd');
    expect(readRoute()).toEqual({ page: 'workspace', runId: '12345678-aaaa-bbbb-cccc-dddddddddddd' });
  });
  it('supports history and rejects path-like task IDs', () => {
    window.history.replaceState(null, '', '/#history');
    expect(readRoute()).toEqual({ page: 'history' });
    window.history.replaceState(null, '', '/#runs/../../private');
    expect(readRoute()).toEqual({ page: 'home' });
  });
});
