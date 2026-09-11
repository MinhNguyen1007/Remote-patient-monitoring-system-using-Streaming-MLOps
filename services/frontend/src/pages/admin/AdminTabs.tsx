import { NavLink } from 'react-router-dom';

import { cn } from '@/lib/utils';

const TABS = [
  { to: '/admin/users', label: 'Người dùng' },
  { to: '/admin/assignments', label: 'Phân công' },
  { to: '/admin/thresholds', label: 'Ngưỡng cảnh báo' },
  { to: '/admin/models', label: 'Giám sát mô hình' },
];

/** Thanh tab chung của trang quản trị (UC03, UC13, UC08, UC09–10). */
export function AdminTabs() {
  return (
    <nav className="flex gap-1 border-b border-border" aria-label="Các mục quản trị">
      {TABS.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          className={({ isActive }) =>
            cn('-mb-px border-b-2 px-3.5 py-2.5 text-[13.5px] font-semibold', isActive ? 'border-primary text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground')
          }
        >
          {tab.label}
        </NavLink>
      ))}
    </nav>
  );
}

export const fieldClass =
  'h-[38px] border border-input bg-background px-3 text-foreground outline-none focus-visible:outline-2 focus-visible:outline-offset-3 focus-visible:outline-primary';
