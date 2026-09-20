import { fireEvent, render, screen } from '@testing-library/react';
import { expect, it } from 'vitest';
import { ShowcaseGallery } from './ShowcaseGallery';

it('shows real rendered pairs with provenance and incomplete goals rather than invented success', () => {
  render(<ShowcaseGallery />);
  expect(screen.getByRole('img', { name: '看见星云初版' })).toHaveAttribute('src', '/showcase/nebula-initial.png');
  expect(screen.getByText(/非生图模型输出/)).toBeInTheDocument();
  expect(screen.getByText('当前检查通过，可作为排版参考')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: '文化活动' }));
  expect(screen.getByRole('img', { name: '花间一课调整后' })).toHaveAttribute('src', '/showcase/irises-optimized.png');
  expect(screen.getByText('待改进，不进入成功经验库')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: '查看原图与许可' }).getAttribute('href')).toContain('commons.wikimedia.org');
  fireEvent.click(screen.getByRole('button', { name: '社团招新' }));
  expect(screen.getByRole('img', { name: '山河入镜初版' })).toBeInTheDocument();
  expect(screen.getByText(/查看未通过的检查（1）/)).toBeInTheDocument();
});
