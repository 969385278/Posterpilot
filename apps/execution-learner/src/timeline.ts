export const FPS = 30;
export const INTRO = 30;
export const STEP_FRAMES = 120;
export const STEP_COUNT = 9;
export const DURATION = INTRO + STEP_COUNT * STEP_FRAMES;
export const startFrame = (index: number) => INTRO + index * STEP_FRAMES;
export const stopFrame = (index: number) => startFrame(index) + STEP_FRAMES - 1;
export function position(frame: number) {
  const clamped = Math.max(0, Math.min(DURATION - 1, Math.floor(frame)));
  const index = clamped < INTRO ? -1 : Math.min(STEP_COUNT - 1, Math.floor((clamped - INTRO) / STEP_FRAMES));
  const local = index < 0 ? 0 : clamped - startFrame(index);
  return {frame: clamped, index, local, revealed: index >= 0 && local >= 78, complete: index >= 0 && clamped === stopFrame(index)};
}
export const nextStop = (frame: number) => Array.from({length: STEP_COUNT}, (_, i) => stopFrame(i)).find(f => f > frame) ?? null;
export const nextIndex = (frame: number) => Math.min(STEP_COUNT - 1, position(frame).index + 1);
export const previousFrame = (frame: number) => position(frame).index <= 0 ? 0 : stopFrame(position(frame).index - 1);
export const crossedStop = (frame: number, target: number | null) => target !== null && frame >= target;
export const shouldIgnoreShortcut = (target: EventTarget | null, selected: string) => Boolean(selected || (target instanceof Element && target.closest('input,textarea,select,button,a,pre,code,[contenteditable="true"],[data-inspector]')));
