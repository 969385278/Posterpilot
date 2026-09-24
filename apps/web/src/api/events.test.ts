import { afterEach, expect, it, vi } from 'vitest';
import { subscribeRunEvents } from './client';

afterEach(() => vi.unstubAllGlobals());

it('reconnects after transient errors and closes only on an explicit stream end', () => {
  const listeners = new Map<string, (event: {data: string}) => void>();
  const close = vi.fn();
  let instance: {onerror?: () => void};
  vi.stubGlobal('EventSource', class {
    onerror?: () => void;
    close = close;
    constructor() { instance = this; }
    addEventListener(type: string, callback: (event: {data: string}) => void) {
      listeners.set(type, callback);
    }
  });
  const onEvent = vi.fn();
  const onError = vi.fn();
  const stop = subscribeRunEvents('run-id', onEvent, onError);
  for (const type of ['human_input_required', 'human_input_received', 'tool_completed', 'run_completed']) {
    listeners.get(type)!({data: JSON.stringify({type})});
  }
  expect(onEvent).toHaveBeenCalledTimes(4);
  expect(close).not.toHaveBeenCalled();
  instance!.onerror!();
  expect(close).not.toHaveBeenCalled();
  expect(onError).toHaveBeenCalledOnce();
  listeners.get('stream_end')!({data: '{}'});
  expect(close).toHaveBeenCalledOnce();
  stop();
  expect(close).toHaveBeenCalledTimes(2);
});
