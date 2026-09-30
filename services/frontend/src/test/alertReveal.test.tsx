import { act, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AppRoutes } from '@/app/App';
import { AuthProvider } from '@/context/AuthContext';
import { enqueue, MAX_TOASTS, revealFor, soundTier, TOAST_MS, toastContent, type RevealItem } from '@/lib/alertReveal';
import { readMuted, SOUND_PREF_KEY, writeMuted } from '@/lib/soundPref';
import type { AlertEvent, Role, ServerEvent } from '@/types/api';

import { FakeWebSocket, mockFetch, user } from './fixtures';

const alertEvent = (overrides: Partial<AlertEvent> = {}): AlertEvent => ({
  alert_id: 'a1',
  patient_id: 'p1',
  subject_id: 10032,
  alert_type: 'RISK',
  status: 'OPEN',
  created_at: '2026-09-30T10:00:00Z',
  prediction_id: 'pr1',
  prediction_recorded_at: '2026-09-30T10:00:00Z',
  hour_index: 88,
  news2_score: 7,
  risk_level: 'CRITICAL',
  risk_score: 0.57,
  anomaly_score: null,
  ...overrides,
});
const drift = { drift_report_id: 'd1', max_psi: 0.41, drift_detected: true, drifted_features: ['spo2'], triggered_retrain: true, retrain_dag_run_id: 'r1', retrain_blocked_reason: null, notify_admin: true };

describe('hàng đợi cảnh báo mới (hàm thuần)', () => {
  it('chỉ báo cảnh báo OPEN cho bác sĩ/điều dưỡng, và drift cần báo cho Admin', () => {
    const risk: ServerEvent = { type: 'alert', data: alertEvent() };
    expect(revealFor(risk, 'DOCTOR')?.kind).toBe('risk');
    expect(revealFor(risk, 'ADMIN')).toBeNull();
    expect(revealFor({ type: 'alert', data: alertEvent({ alert_type: 'ANOMALY', anomaly_score: 0.995 }) }, 'NURSE')?.kind).toBe('anomaly');
    expect(revealFor({ type: 'alert', data: alertEvent({ status: 'ACKNOWLEDGED' }) }, 'DOCTOR')).toBeNull();
    expect(revealFor({ type: 'drift_report', data: drift }, 'ADMIN')?.kind).toBe('drift');
    expect(revealFor({ type: 'drift_report', data: { ...drift, notify_admin: false } }, 'ADMIN')).toBeNull();
    expect(revealFor({ type: 'drift_report', data: drift }, 'DOCTOR')).toBeNull();
  });

  it('bỏ trùng theo key và giữ các mục mới nhất', () => {
    const item = (id: string): RevealItem => ({ kind: 'anomaly', key: id, alert: alertEvent({ alert_id: id }) });
    let queue: RevealItem[] = [];
    for (const id of ['1', '2', '2', '3', '4', '5']) queue = enqueue(queue, item(id), MAX_TOASTS);
    expect(queue.map((x) => x.key)).toEqual(['2', '3', '4', '5']);
  });

  it('âm báo: nguy kịch hạng đỏ, bất thường hạng tím; nội dung toast đúng số liệu', () => {
    const anomaly: RevealItem = { kind: 'anomaly', key: 'x', alert: alertEvent({ alert_type: 'ANOMALY', anomaly_score: 0.995 }) };
    expect(soundTier({ kind: 'risk', key: 'r', alert: alertEvent() })).toBe(3);
    expect(soundTier(anomaly)).toBe(1);
    expect(toastContent(anomaly)).toMatchObject({ title: 'BN-10032 · Diễn biến bất thường', body: 'Điểm bất thường 0,995 · giờ thứ 88', href: '/patients/p1' });
    expect(toastContent({ kind: 'drift', key: 'd', report: drift }).body).toContain('spo2');
  });

  it('lựa chọn tắt âm được nhớ; không lưu được thì báo false và mặc định là bật âm', () => {
    expect(readMuted()).toBe(false);
    expect(writeMuted(true)).toBe(true);
    expect(localStorage.getItem(SOUND_PREF_KEY)).toBe('1');
    expect(readMuted()).toBe(true);
    const broken = { getItem: () => { throw new Error('blocked'); }, setItem: () => { throw new Error('blocked'); } };
    expect(readMuted(broken)).toBe(false);
    expect(writeMuted(true, broken)).toBe(false);
  });
});

function renderApp(role: Role, path = role === 'ADMIN' ? '/admin/users' : '/patients') {
  localStorage.setItem('rpm.token', 'token');
  mockFetch({ '/auth/me': user(role, 'BS. An'), '/patients': [], '/alerts/open-count': { open: 0 }, '/users': [], '/admin/patients': [] });
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </MemoryRouter>,
  );
}

async function emit(event: ServerEvent) {
  await vi.waitFor(() => expect(FakeWebSocket.instances.length).toBeGreaterThan(0)); // kết nối mở sau khi /auth/me trả về
  await act(async () => FakeWebSocket.instances[0].emit(event));
}

describe('cảnh báo mới trên giao diện (overlay + toast)', () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    vi.stubGlobal('WebSocket', FakeWebSocket);
  });

  it('rủi ro nguy kịch → overlay toàn màn hình, xếp hàng, "Để sau" chuyển sang cảnh báo kế tiếp', async () => {
    renderApp('DOCTOR');
    await screen.findByRole('heading', { name: 'Theo dõi bệnh nhân' });
    await emit({ type: 'alert', data: alertEvent() });
    await emit({ type: 'alert', data: alertEvent({ alert_id: 'a2', subject_id: 40503, patient_id: 'p2', risk_score: 0.48 }) });

    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByRole('heading', { name: 'BN-10032' })).toBeInTheDocument();
    expect(dialog).toHaveTextContent('còn 1 cảnh báo chờ');
    expect(dialog).toHaveTextContent('57%');
    expect(within(dialog).getByRole('button', { name: 'XÁC NHẬN' })).toBeInTheDocument();

    await userEvent.click(within(dialog).getByRole('button', { name: 'ĐỂ SAU' }));
    expect(await screen.findByRole('heading', { name: 'BN-40503' })).toBeInTheDocument();
  });

  it('điều dưỡng không có nút Xác nhận; bất thường chỉ hiện toast, không che màn hình', async () => {
    renderApp('NURSE');
    await screen.findByRole('heading', { name: 'Theo dõi bệnh nhân' });
    await emit({ type: 'alert', data: alertEvent({ alert_type: 'ANOMALY', anomaly_score: 0.995 }) });
    expect(await screen.findByText('BN-10032 · Diễn biến bất thường')).toBeInTheDocument();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();

    await emit({ type: 'alert', data: alertEvent({ alert_id: 'a9' }) });
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).queryByRole('button', { name: 'XÁC NHẬN' })).not.toBeInTheDocument();
  });

  it('toast không tự ẩn khi overlay nguy kịch đang mở (nằm dưới lớp nền mờ), chỉ đếm giờ sau khi đóng overlay', async () => {
    // Đồng hồ giả phải bật trước khi toast xuất hiện, để chính setTimeout tự ẩn của nó chạy trên đồng hồ giả
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      renderApp('DOCTOR');
      await screen.findByRole('heading', { name: 'Theo dõi bệnh nhân' });
      await emit({ type: 'alert', data: alertEvent() });
      await emit({ type: 'alert', data: alertEvent({ alert_id: 'an1', alert_type: 'ANOMALY', anomaly_score: 0.995 }) });
      const dialog = await screen.findByRole('dialog');

      await act(async () => vi.advanceTimersByTime(TOAST_MS + 1000));
      expect(screen.getByText('BN-10032 · Diễn biến bất thường')).toBeInTheDocument();

      await act(async () => within(dialog).getByRole('button', { name: 'ĐỂ SAU' }).click());
      await act(async () => vi.advanceTimersByTime(TOAST_MS + 1000));
      expect(screen.queryByText('BN-10032 · Diễn biến bất thường')).not.toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it('Admin nhận toast drift; nút âm báo tắt/bật và nhớ lựa chọn', async () => {
    renderApp('ADMIN');
    await screen.findByRole('heading', { name: 'Người dùng' });
    await emit({ type: 'drift_report', data: drift });
    expect(await screen.findByText('Phát hiện drift dữ liệu')).toBeInTheDocument();

    const toggle = screen.getByRole('button', { name: 'Âm báo bật' });
    await userEvent.click(toggle);
    expect(screen.getByRole('button', { name: 'Âm báo tắt' })).toHaveAttribute('aria-pressed', 'false');
    expect(localStorage.getItem(SOUND_PREF_KEY)).toBe('1');
  });
});
