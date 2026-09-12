import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import { AlertActions } from '@/components/AlertActions';
import { AnomalyChip, News2Chip, RiskBadge } from '@/components/clinical';
import { PatientCard } from '@/components/PatientCard';

import { alert, latest, mockFetch, patient } from './fixtures';

describe('RiskBadge — mức rủi ro không truyền đạt chỉ bằng màu (02_8 mục 2.8.2a)', () => {
  it.each([
    ['NORMAL', 'Bình thường'],
    ['WARNING', 'Cảnh báo'],
    ['CRITICAL', 'Nguy kịch'],
  ] as const)('%s có nhãn chữ, icon và xác suất', (level, label) => {
    const { container } = render(<RiskBadge level={level} score={0.72} />);
    expect(screen.getByText(label)).toBeInTheDocument();
    expect(screen.getByText('0,72')).toBeInTheDocument();
    expect(container.querySelector('svg')).not.toBeNull();
    expect(container.querySelector('[data-level]')).toHaveAttribute('data-level', level);
  });
});

describe('Chip NEWS2 và bất thường', () => {
  it('NEWS2 trung tính, thiếu điểm hiển thị gạch ngang', () => {
    render(<News2Chip score={null} />);
    expect(screen.getByText('—')).toBeInTheDocument();
  });

  it('bất thường: chưa đủ 16 giờ, ổn định, bị gắn cờ', () => {
    const { rerender } = render(<AnomalyChip score={null} />);
    expect(screen.getByText('Chưa đủ 16 giờ')).toBeInTheDocument();
    rerender(<AnomalyChip score={null} hourIndex={9} />);
    expect(screen.getByText('Chưa đủ 16 giờ')).toBeInTheDocument();
    // Quá giờ 16 mà vẫn chưa có điểm thì nguyên nhân là cửa sổ 12 giờ thiếu giá trị đo, không phải "chưa đủ giờ"
    rerender(<AnomalyChip score={null} hourIndex={88} />);
    expect(screen.getByText('Thiếu dữ liệu cửa sổ')).toBeInTheDocument();
    rerender(<AnomalyChip score={0.42} flagged={false} />);
    expect(screen.getByText('Ổn định')).toBeInTheDocument();
    rerender(<AnomalyChip score={0.995} flagged />);
    expect(screen.getByText('Bất thường')).toBeInTheDocument();
    expect(screen.getByText('0,995')).toBeInTheDocument();
  });
});

describe('PatientCard', () => {
  it('hiển thị badge dự báo, NEWS2, vitals và dải 12 giờ (ô trống khi chưa đủ 12 giờ)', () => {
    const p = patient('p1', {
      latest: latest({ risk_level: 'CRITICAL', risk_score: 0.72, news2_score: 9, heart_rate: 126 }),
      recent_risk_levels: ['WARNING', 'CRITICAL', 'CRITICAL'],
      open_alerts: 2,
    });
    render(<MemoryRouter><PatientCard patient={p} now={Date.parse('2026-09-11T05:30:05Z')} /></MemoryRouter>);
    expect(screen.getByText('Nguy kịch')).toBeInTheDocument();
    expect(screen.getByText('126')).toBeInTheDocument();
    expect(screen.getByText('2 cảnh báo mở')).toBeInTheDocument();
    expect(screen.getByText('5 giây trước')).toBeInTheDocument();
    expect(screen.getByRole('img', { name: /3 giờ gần nhất/ }).children).toHaveLength(12);
    expect(screen.getByRole('link')).toHaveAttribute('href', '/patients/p1');
  });
});

describe('AlertActions — vòng đời OPEN → ACKNOWLEDGED → RESOLVED (UC07)', () => {
  it('OPEN chỉ có nút Xác nhận và gọi API acknowledge', async () => {
    const fetchMock = mockFetch({ '/alerts/a1/acknowledge': alert({ status: 'ACKNOWLEDGED' }) });
    const onChanged = vi.fn();
    render(<AlertActions alert={alert()} onChanged={onChanged} />);
    await userEvent.click(screen.getByRole('button', { name: /Xác nhận/ }));
    expect(fetchMock).toHaveBeenCalledWith('/api/alerts/a1/acknowledge', expect.objectContaining({ method: 'POST' }));
    expect(onChanged).toHaveBeenCalledWith(expect.objectContaining({ status: 'ACKNOWLEDGED' }));
  });

  it('ACKNOWLEDGED bắt buộc ghi chú trước khi Đã xử lý', async () => {
    const fetchMock = mockFetch({ '/alerts/a1/resolve': alert({ status: 'RESOLVED', resolution_note: 'Đã xử trí' }) });
    render(<AlertActions alert={alert({ status: 'ACKNOWLEDGED' })} onChanged={vi.fn()} />);
    await userEvent.click(screen.getByRole('button', { name: /Đã xử lý…/ }));
    const submit = screen.getByRole('button', { name: 'Đã xử lý' });
    expect(submit).toBeDisabled();
    await userEvent.type(screen.getByLabelText('Ghi chú xử lý'), 'Đã xử trí');
    await userEvent.click(submit);
    expect(fetchMock).toHaveBeenCalledWith('/api/alerts/a1/resolve', expect.objectContaining({ body: JSON.stringify({ note: 'Đã xử trí' }) }));
  });

  it('RESOLVED không còn thao tác', () => {
    const { container } = render(<AlertActions alert={alert({ status: 'RESOLVED' })} onChanged={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('lỗi từ backend (409) hiển thị cho người dùng', async () => {
    mockFetch({ '/alerts/a1/acknowledge': { detail: 'Chỉ xác nhận được cảnh báo OPEN' } }, 409);
    render(<AlertActions alert={alert()} onChanged={vi.fn()} />);
    await userEvent.click(screen.getByRole('button', { name: /Xác nhận/ }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Chỉ xác nhận được cảnh báo OPEN');
  });
});
