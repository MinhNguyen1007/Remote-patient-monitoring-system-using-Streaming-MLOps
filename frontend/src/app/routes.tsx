import type { ReactNode } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';

import { useAuth } from '@/context/AuthContext';
import type { Role } from '@/types/api';

/** Trang chính theo vai trò (02_8 mục 2.8.3): Admin không theo dõi bệnh nhân. */
export function homeFor(role: Role): string {
  return role === 'ADMIN' ? '/admin/users' : '/patients';
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, token, restoring } = useAuth();
  const location = useLocation();
  if (restoring) return <div className="p-10 text-muted-foreground">Đang khôi phục phiên đăng nhập…</div>;
  if (!token || !user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <>{children}</>;
}

/** Chặn route theo vai trò đúng bảng phân quyền ở 02_2; sai vai trò thì về trang chính của vai trò đó. */
export function RequireRole({ roles }: { roles: Role[] }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (!roles.includes(user.role)) return <Navigate to={homeFor(user.role)} replace />;
  return <Outlet />;
}

export function HomeRedirect() {
  const { user } = useAuth();
  return <Navigate to={user ? homeFor(user.role) : '/login'} replace />;
}
