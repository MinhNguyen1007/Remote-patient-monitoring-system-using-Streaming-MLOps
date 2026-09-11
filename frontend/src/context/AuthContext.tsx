import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

import { api, setUnauthorizedHandler, tokenStore } from '@/api/client';
import type { User } from '@/types/api';

interface AuthState {
  user: User | null;
  token: string | null;
  /** true khi đang khôi phục phiên từ token đã lưu (tránh nháy về trang đăng nhập) */
  restoring: boolean;
  login: (email: string, password: string) => Promise<User>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => tokenStore.get());
  const [user, setUser] = useState<User | null>(null);
  const [restoring, setRestoring] = useState<boolean>(() => tokenStore.get() !== null);

  // UC02: JWT không lưu trạng thái ở server — đăng xuất là xóa token phía client
  const logout = useCallback(() => {
    tokenStore.set(null);
    setToken(null);
    setUser(null);
  }, []);

  useEffect(() => setUnauthorizedHandler(logout), [logout]);

  useEffect(() => {
    if (!token || user) {
      setRestoring(false);
      return;
    }
    let cancelled = false;
    api
      .me()
      .then((me) => !cancelled && setUser(me))
      .catch(() => !cancelled && logout())
      .finally(() => !cancelled && setRestoring(false));
    return () => {
      cancelled = true;
    };
  }, [token, user, logout]);

  const login = useCallback(async (email: string, password: string) => {
    const result = await api.login(email, password);
    tokenStore.set(result.access_token);
    setToken(result.access_token);
    setUser(result.user);
    return result.user;
  }, []);

  const value = useMemo(() => ({ user, token, restoring, login, logout }), [user, token, restoring, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth phải nằm trong AuthProvider');
  return context;
}

export { AuthContext };
