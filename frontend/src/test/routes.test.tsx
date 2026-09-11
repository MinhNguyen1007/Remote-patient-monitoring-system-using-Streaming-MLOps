import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AppRoutes } from '@/app/App';
import { AuthProvider } from '@/context/AuthContext';
import type { Role } from '@/types/api';

import { FakeWebSocket, mockFetch, patient, prediction, user } from './fixtures';

function renderApp(path: string, role: Role | null, extraRoutes: Record<string, unknown> = {}) {
  if (role) localStorage.setItem('rpm.token', 'token');
  mockFetch({
    '/auth/me': role ? user(role, role === 'ADMIN' ? 'Quản trị viên' : 'ĐD. Cường') : undefined,
    '/patients': [],
    '/alerts/open-count': { open: 0 },
    '/users': [],
    '/admin/patients': [],
    ...extraRoutes,
  });
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  FakeWebSocket.instances = [];
  vi.stubGlobal('WebSocket', FakeWebSocket);
});

describe('chặn route theo vai trò (02_2, 02_8 mục 2.8.3)', () => {
  it('chưa đăng nhập → trang đăng nhập', async () => {
    renderApp('/patients', null);
    expect(await screen.findByRole('heading', { name: 'Đăng nhập' })).toBeInTheDocument();
  });

  it('Điều dưỡng vào trang quản trị → về dashboard, sidebar không có mục Quản trị', async () => {
    renderApp('/admin/users', 'NURSE');
    expect(await screen.findByRole('heading', { name: 'Theo dõi bệnh nhân' })).toBeInTheDocument();
    expect(screen.queryByText('Người dùng')).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Cảnh báo/ })).toBeInTheDocument();
  });

  it('Admin không theo dõi bệnh nhân: vào /patients → về trang Người dùng', async () => {
    renderApp('/patients', 'ADMIN');
    expect(await screen.findByRole('heading', { name: 'Người dùng' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Bệnh nhân' })).not.toBeInTheDocument();
  });
});

describe('dashboard hiển thị đúng danh sách backend trả về và cập nhật qua WebSocket', () => {
  it('không tự lọc thêm; sự kiện prediction đưa bệnh nhân nguy kịch lên đầu', async () => {
    renderApp('/patients', 'DOCTOR', { '/patients': [patient('a'), patient('b')] });
    expect(await screen.findByText('BN-a')).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: /^BN-/ }).map((l) => l.textContent?.slice(0, 4))).toEqual(['BN-a', 'BN-b']);

    await act(async () => FakeWebSocket.instances[0].emit({ type: 'prediction', data: prediction('b') }));
    const cards = screen.getAllByRole('link', { name: /^BN-/ });
    expect(cards[0]).toHaveAccessibleName(/BN-b, Nguy kịch/);
    expect(screen.getByRole('status')).toHaveTextContent('Realtime · đã kết nối');
  });

  it('chưa được phân công bệnh nhân nào → thông báo rõ ràng', async () => {
    renderApp('/patients', 'NURSE');
    expect(await screen.findByText(/chưa được phân công bệnh nhân nào/)).toBeInTheDocument();
  });
});

describe('đăng nhập (UC01)', () => {
  it('sai thông tin: hiển thị lỗi ngay dưới nút', async () => {
    mockFetch({ '/auth/login': { detail: 'Email hoặc mật khẩu không đúng' } }, 401);
    render(
      <MemoryRouter initialEntries={['/login']}>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </MemoryRouter>,
    );
    await userEvent.type(screen.getByPlaceholderText('ten@benhvien.vn'), 'x@rpm.local');
    await userEvent.type(screen.getByLabelText('Mật khẩu'), 'sai-mat-khau');
    await userEvent.click(screen.getByRole('button', { name: 'Đăng nhập' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Email hoặc mật khẩu không đúng');
  });
});
