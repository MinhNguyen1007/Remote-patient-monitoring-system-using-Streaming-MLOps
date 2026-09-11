import { Activity, Bell, Cpu, LayoutGrid, Link2, LogOut, SlidersHorizontal, Users, type LucideIcon } from 'lucide-react';
import { useEffect, useState, type ReactNode } from 'react';
import { NavLink, Outlet } from 'react-router-dom';

import { api } from '@/api/client';
import { useAuth } from '@/context/AuthContext';
import { useRealtime, useServerEvents } from '@/context/WebSocketContext';
import { initials } from '@/lib/format';
import { ROLE_LABEL } from '@/lib/risk';
import { cn } from '@/lib/utils';

export function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <div className="flex size-[34px] items-center justify-center bg-primary">
        <Activity aria-hidden size={20} strokeWidth={2.4} color="var(--primary-foreground)" />
      </div>
      <div className="flex flex-col leading-[1.1]">
        <span className="text-[17px] font-extrabold tracking-[-0.5px]">RPM Monitor</span>
        <span className="mono text-[10.5px] tracking-[1.5px] text-muted-foreground">ICU · REALTIME</span>
      </div>
    </div>
  );
}

export function RealtimeIndicator() {
  const { status } = useRealtime();
  const connected = status === 'open';
  const color = connected ? 'var(--primary)' : 'var(--risk-warning)';
  return (
    <span className="mono inline-flex items-center gap-2 text-[12px] text-muted-foreground" role="status" aria-live="polite">
      <span aria-hidden className="size-2" style={{ background: color, boxShadow: `0 0 0 4px color-mix(in srgb, ${color} 15%, transparent)` }} />
      {connected ? 'Realtime · đã kết nối' : status === 'connecting' ? 'Đang kết nối…' : 'Đang kết nối lại…'}
    </span>
  );
}

function NavItem({ to, icon: Icon, label, badge }: { to: string; icon: LucideIcon; label: string; badge?: number }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        cn('flex h-10 items-center gap-2.5 px-3 font-medium text-muted-foreground', isActive && 'bg-accent font-semibold text-accent-foreground')
      }
    >
      <Icon aria-hidden size={18} />
      <span>{label}</span>
      {badge ? (
        <span className="mono ml-auto flex h-5 min-w-[22px] items-center justify-center bg-risk-critical px-1.5 text-[11.5px] font-semibold text-foreground" aria-label={`${badge} cảnh báo đang mở`}>
          {badge}
        </span>
      ) : null}
    </NavLink>
  );
}

/** Badge số cảnh báo mở trên sidebar: tải khi mở trang, tải lại khi có cảnh báo mới/đổi trạng thái. */
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

export function AppShell() {
  const { user, logout } = useAuth();
  const isAdmin = user?.role === 'ADMIN';
  const openAlerts = useOpenAlertCount(!isAdmin);
  if (!user) return null;
  return (
    <div className="flex min-h-screen bg-background">
      <aside className="sticky top-0 flex h-screen w-[248px] shrink-0 flex-col gap-7 border-r border-border bg-card px-3.5 py-5">
        <div className="px-1.5">
          <Logo />
        </div>
        <nav className="flex flex-col gap-1" aria-label="Điều hướng chính">
          {isAdmin ? (
            <>
              <div className="mono px-3 pb-1.5 text-[10.5px] tracking-[1.8px] text-muted-foreground">QUẢN TRỊ</div>
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
        <div className="mt-auto flex items-center gap-2.5 border border-border bg-background p-3">
          <div className="flex size-[34px] shrink-0 items-center justify-center bg-secondary text-[13px] font-bold">{initials(user.full_name)}</div>
          <div className="flex min-w-0 flex-col leading-tight">
            <span className="truncate text-[13px] font-semibold">{user.full_name}</span>
            <span className="mono text-[11px] text-muted-foreground">{ROLE_LABEL[user.role]}</span>
          </div>
          <button type="button" onClick={logout} className="ml-auto flex p-1 text-muted-foreground hover:text-foreground" aria-label="Đăng xuất" title="Đăng xuất">
            <LogOut size={18} />
          </button>
        </div>
      </aside>
      <main className="flex min-w-0 grow flex-col gap-6 px-9 pt-7 pb-9">
        <Outlet />
      </main>
    </div>
  );
}

export function PageHeader({ eyebrow, title, subtitle, actions }: { eyebrow: string; title: ReactNode; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-6">
      <div className="flex flex-col gap-2.5">
        <div className="eyebrow">{eyebrow}</div>
        <h1 className="page-title">{title}</h1>
        {subtitle && <p className="m-0 max-w-[720px] text-pretty text-muted-foreground">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-3">{actions}</div>}
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
    <div role="radiogroup" aria-label={label} className="flex gap-0.5 border border-border bg-card p-[3px]">
      {options.map((option) => {
        const active = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(option.value)}
            className={cn('flex h-8 items-center gap-[7px] px-3 text-[13px] font-semibold', active ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground')}
          >
            {option.label}
            {option.count !== undefined && <span className="mono opacity-80">{option.count}</span>}
          </button>
        );
      })}
    </div>
  );
}

export function StateMessage({ children, tone = 'muted' }: { children: ReactNode; tone?: 'muted' | 'error' }) {
  return (
    <div
      className={cn('card px-5 py-8 text-center text-[13.5px]', tone === 'error' ? 'border-risk-critical/50 text-foreground' : 'text-muted-foreground')}
      role={tone === 'error' ? 'alert' : undefined}
    >
      {children}
    </div>
  );
}
