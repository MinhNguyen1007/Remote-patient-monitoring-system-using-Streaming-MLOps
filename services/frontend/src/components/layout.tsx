import { Activity, Bell, Cpu, LayoutGrid, Link2, LogOut, SlidersHorizontal, Users, Volume2, VolumeX, type LucideIcon } from 'lucide-react';
import { useEffect, useState, type ReactNode } from 'react';
import { Link, NavLink, Outlet } from 'react-router-dom';

import { api } from '@/api/client';
import { AlertReveal } from '@/components/AlertReveal';
import { useAuth } from '@/context/AuthContext';
import { useRealtime, useServerEvents } from '@/context/WebSocketContext';
import { useAlertSound, type AlertSound } from '@/hooks/useAlertSound';
import { ROLE_LABEL } from '@/lib/risk';
import { cn } from '@/lib/utils';

export function Logo({ to }: { to?: string }) {
  const content = (
    <>
      <span className="app-brand-icon">
        <Activity aria-hidden size={20} strokeWidth={2.2} />
      </span>
      <span className="app-brand-text">
        RPM Monitor
        <small>ICU · REALTIME</small>
      </span>
    </>
  );
  return to ? (
    <Link to={to} className="app-brand" aria-label="RPM Monitor — trang chính">
      {content}
    </Link>
  ) : (
    <span className="app-brand">{content}</span>
  );
}

export function RealtimeIndicator() {
  const { status } = useRealtime();
  const connected = status === 'open';
  const color = connected ? '#83a65f' : 'var(--risk-warning)';
  return (
    <span className="inline-flex items-center gap-2 text-[12px] text-muted-foreground" role="status" aria-live="polite">
      <span aria-hidden className="size-2" style={{ background: color, boxShadow: `0 0 0 4px color-mix(in srgb, ${color} 18%, transparent)` }} />
      {connected ? 'Realtime · đã kết nối' : status === 'connecting' ? 'Đang kết nối…' : 'Đang kết nối lại…'}
    </span>
  );
}

function NavItem({ to, icon: Icon, label, badge }: { to: string; icon: LucideIcon; label: string; badge?: number }) {
  const name = badge ? `${label}, ${badge} cảnh báo đang mở` : label;
  return (
    <NavLink to={to} className="tn-hbtn" aria-label={name} title={label}>
      <Icon aria-hidden />
      <span className="tn-hbtn-label">{label}</span>
      {badge ? <span className="app-badge" aria-hidden>{badge}</span> : null}
    </NavLink>
  );
}

/** Badge số cảnh báo mở trên header: tải khi mở trang, tải lại khi có cảnh báo mới/đổi trạng thái. */
function useOpenAlertCount(enabled: boolean): number {
  const [count, setCount] = useState(0);
  const [version, setVersion] = useState(0);
  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    api.openAlertCount(controller.signal).then((r) => setCount(r.open)).catch(() => {});
    return () => controller.abort();
  }, [enabled, version]);
  useServerEvents((event) => {
    if (enabled && (event.type === 'alert' || event.type === 'alert_update')) setVersion((v) => v + 1);
  });
  return count;
}

function SoundToggle({ sound }: { sound: AlertSound }) {
  const label = sound.muted ? 'Âm báo tắt' : 'Âm báo bật';
  const hint = sound.saved ? '' : ' (không lưu được trên trình duyệt này, chỉ áp dụng phiên hiện tại)';
  return (
    <button type="button" className="tn-hbtn tn-hbtn--ghost" onClick={sound.toggle} aria-pressed={!sound.muted} aria-label={`${label}${hint}`} title={`${label}${hint}`}>
      {sound.muted ? <VolumeX aria-hidden /> : <Volume2 aria-hidden />}
      <span className="tn-hbtn-label">
        {label}
        {!sound.saved && ' *'}
      </span>
    </button>
  );
}

export function AppShell() {
  const { user, logout } = useAuth();
  const isAdmin = user?.role === 'ADMIN';
  const openAlerts = useOpenAlertCount(!isAdmin);
  const sound = useAlertSound();
  if (!user) return null;
  return (
    <div className="tn-shell app-shell">
      <header className="tn-header app-header">
        <Logo to={isAdmin ? '/admin/users' : '/patients'} />
        <nav className="app-nav" aria-label="Điều hướng chính">
          {isAdmin ? (
            <>
              <NavItem to="/admin/users" icon={Users} label="Người dùng" />
              <NavItem to="/admin/assignments" icon={Link2} label="Phân công" />
              <NavItem to="/admin/thresholds" icon={SlidersHorizontal} label="Ngưỡng cảnh báo" />
              <NavItem to="/admin/models" icon={Cpu} label="Giám sát mô hình" />
            </>
          ) : (
            <>
              <NavItem to="/patients" icon={LayoutGrid} label="Bệnh nhân" />
              <NavItem to="/alerts" icon={Bell} label="Cảnh báo" badge={openAlerts} />
            </>
          )}
        </nav>
        <div className="tn-header-actions">
          <SoundToggle sound={sound} />
          <div className="app-user">
            <strong>{user.full_name}</strong>
            <span>{ROLE_LABEL[user.role]}</span>
          </div>
          <button type="button" onClick={logout} className="tn-hbtn" aria-label="Đăng xuất" title="Đăng xuất">
            <LogOut aria-hidden />
          </button>
        </div>
      </header>
      <main className="tn-main app-main">
        <Outlet />
      </main>
      <footer className="tn-footer app-footer">
        <span>RPM Monitor · đồ án giám sát bệnh nhân từ xa bằng Streaming + MLOps</span>
        <span>Dữ liệu: MIMIC-III Clinical Database Demo (PhysioNet) · âm báo tổng hợp bằng Web Audio</span>
      </footer>
      <AlertReveal sound={sound} />
    </div>
  );
}

/** Tiêu đề trang kiểu CS:GO: 32 px / 400 căn giữa, dòng đếm (số màu vàng), mô tả, rồi các thao tác. */
export function PageHeader({ eyebrow, title, subtitle, actions }: { eyebrow?: ReactNode; title: ReactNode; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="page-head">
      <h1 className="page-title">{title}</h1>
      {eyebrow && <p className="page-counter">{eyebrow}</p>}
      {subtitle && <p className="page-sub">{subtitle}</p>}
      {actions && <div className="mt-2 flex flex-wrap items-center justify-center gap-3">{actions}</div>}
    </header>
  );
}

export function Segmented<T extends string>({
  options,
  value,
  onChange,
  label,
}: {
  options: { value: T; label: string; count?: number }[];
  value: T;
  onChange: (value: T) => void;
  label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="segmented">
      {options.map((option) => (
        <button key={option.value} type="button" role="radio" aria-checked={option.value === value} onClick={() => onChange(option.value)}>
          {option.label}
          {option.count !== undefined && <span className="count">{option.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function StateMessage({ children, tone = 'muted' }: { children: ReactNode; tone?: 'muted' | 'error' }) {
  return (
    <div
      className={cn('card px-5 py-8 text-center text-[13.5px]', tone === 'error' ? 'border-risk-critical/60 text-foreground' : 'text-muted-foreground')}
      role={tone === 'error' ? 'alert' : undefined}
    >
      {children}
    </div>
  );
}
