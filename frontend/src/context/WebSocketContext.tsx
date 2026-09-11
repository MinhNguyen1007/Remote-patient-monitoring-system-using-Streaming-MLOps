import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react';

import { websocketUrl } from '@/api/client';
import { useAuth } from '@/context/AuthContext';
import type { ServerEvent } from '@/types/api';

export type ConnectionStatus = 'connecting' | 'open' | 'reconnecting';
type Listener = (event: ServerEvent) => void;

interface RealtimeState {
  status: ConnectionStatus;
  subscribe: (listener: Listener) => () => void;
}

const WebSocketContext = createContext<RealtimeState | null>(null);
const POLICY_VIOLATION = 1008; // server từ chối token (02_4 mục 2.4.2)
const MAX_BACKOFF_MS = 15_000;

/**
 * Một kết nối WebSocket cho cả ứng dụng. Mất kết nối thì tự nối lại với thời gian chờ tăng dần;
 * dữ liệu trên màn hình giữ nguyên cho tới khi có sự kiện mới. Server chỉ đẩy sự kiện của bệnh nhân
 * được phân công nên client không cần lọc thêm.
 */
export function WebSocketProvider({ children }: { children: ReactNode }) {
  const { token, logout } = useAuth();
  const [status, setStatus] = useState<ConnectionStatus>('connecting');
  const listeners = useRef(new Set<Listener>());

  useEffect(() => {
    if (!token) return;
    let socket: WebSocket | null = null;
    let retry = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let stopped = false;

    const connect = () => {
      setStatus(retry === 0 ? 'connecting' : 'reconnecting');
      socket = new WebSocket(websocketUrl(token));
      socket.onopen = () => {
        retry = 0;
        setStatus('open');
      };
      socket.onmessage = (message) => {
        try {
          const event = JSON.parse(message.data) as ServerEvent;
          listeners.current.forEach((listener) => listener(event));
        } catch {
          /* bỏ qua tin không phải JSON (vd "pong") */
        }
      };
      socket.onclose = (closeEvent) => {
        if (stopped) return;
        if (closeEvent.code === POLICY_VIOLATION) {
          logout();
          return;
        }
        setStatus('reconnecting');
        const delay = Math.min(MAX_BACKOFF_MS, 1000 * 2 ** retry);
        retry += 1;
        timer = setTimeout(connect, delay);
      };
    };

    connect();
    const keepAlive = setInterval(() => socket?.readyState === WebSocket.OPEN && socket.send('ping'), 25_000);
    return () => {
      stopped = true;
      clearTimeout(timer);
      clearInterval(keepAlive);
      socket?.close();
    };
  }, [token, logout]);

  const value = useRef<RealtimeState>({
    status,
    subscribe: (listener) => {
      listeners.current.add(listener);
      return () => listeners.current.delete(listener);
    },
  });
  value.current = { ...value.current, status };

  return <WebSocketContext.Provider value={value.current}>{children}</WebSocketContext.Provider>;
}

export function useRealtime(): RealtimeState {
  const context = useContext(WebSocketContext);
  if (!context) throw new Error('useRealtime phải nằm trong WebSocketProvider');
  return context;
}

/** Đăng ký nhận sự kiện realtime; `handler` luôn là bản mới nhất mà không phải đăng ký lại. */
export function useServerEvents(handler: Listener) {
  const { subscribe } = useRealtime();
  const latest = useRef(handler);
  latest.current = handler;
  useEffect(() => subscribe((event) => latest.current(event)), [subscribe]);
}

export { WebSocketContext };
