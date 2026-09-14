import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ThemeSelect } from './ThemeSelect';

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.removeItem('posterpilot-theme');
  delete document.documentElement.dataset.theme;
});

it('changes appearance, persists the preference, and restores system mode', () => {
  const {unmount} = render(<ThemeSelect />);
  fireEvent.change(screen.getByRole('combobox', {name: '页面外观'}), {target: {value: 'dark'}});
  expect(document.documentElement.dataset.theme).toBe('dark');
  unmount();
  render(<ThemeSelect />);
  expect(screen.getByRole('combobox', {name: '页面外观'})).toHaveValue('dark');
  fireEvent.change(screen.getByRole('combobox', {name: '页面外观'}), {target: {value: 'system'}});
  expect(document.documentElement.dataset.theme).toBeUndefined();
});

it('still permits switching when preference storage is unavailable', () => {
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked'); });
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked'); });
  render(<ThemeSelect />);
  fireEvent.change(screen.getByRole('combobox', {name: '页面外观'}), {target: {value: 'light'}});
  expect(document.documentElement.dataset.theme).toBe('light');
});
