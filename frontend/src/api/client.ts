import type {
  AdminPatient,
  Alert,
  AlertSettings,
  AlertStatus,
  AlertType,
  Assignment,
  DriftReport,
  ModelVersion,
  PatientDetail,
  PatientSummary,
  RetrainStatus,
  Role,
  TimelinePoint,
  TokenResponse,
  User,
} from '@/types/api';

/** REST và WebSocket đi qua tiền tố /api (proxy Vite khi dev, nginx khi chạy Docker). */
export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api';
const TOKEN_KEY = 'rpm.token';

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export const tokenStore = {
  get: (): string | null => {
    try {
      return localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set: (token: string | null) => {
    try {
      if (token) localStorage.setItem(TOKEN_KEY, token);
      else localStorage.removeItem(TOKEN_KEY);
    } catch {
      /* trình duyệt chặn storage: phiên chỉ sống trong bộ nhớ */
    }
  },
};

let onUnauthorized: () => void = () => {};
/** AuthContext đăng ký hàm đăng xuất khi token hết hạn (401). */
export function setUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler;
}

function errorMessage(body: unknown, status: number): string {
  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) return 'Dữ liệu không hợp lệ: ' + detail.map((d) => d?.msg ?? '').join('; ');
  }
  return `Lỗi ${status}`;
}

export async function request<T>(path: string, options: { method?: string; body?: unknown; signal?: AbortSignal } = {}): Promise<T> {
  const token = tokenStore.get();
  const response = await fetch(`${API_BASE}${path}`, {
    method: options.method ?? 'GET',
    headers: {
      ...(options.body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    signal: options.signal,
  });
  if (response.status === 204) return undefined as T;
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401 && token) onUnauthorized();
    throw new ApiError(response.status, errorMessage(body, response.status));
  }
  return body as T;
}

const query = (params: Record<string, string | number | undefined | null>) => {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '');
  return entries.length ? '?' + new URLSearchParams(entries.map(([k, v]) => [k, String(v)])).toString() : '';
};

export const api = {
  // UC01
  login: (email: string, password: string) =>
    request<TokenResponse>('/auth/login', { method: 'POST', body: { email, password } }),
  me: () => request<User>('/auth/me'),

  // UC04–UC05
  patients: (signal?: AbortSignal) => request<PatientSummary[]>('/patients', { signal }),
  patient: (id: string, signal?: AbortSignal) => request<PatientDetail>(`/patients/${id}`, { signal }),
  timeline: (id: string, hours: number, signal?: AbortSignal) =>
    request<TimelinePoint[]>(`/patients/${id}/timeline${query({ hours })}`, { signal }),
  patientAlerts: (id: string, signal?: AbortSignal) => request<Alert[]>(`/patients/${id}/alerts`, { signal }),

  // UC06–UC07
  alerts: (filters: { status?: AlertStatus; type?: AlertType; patient_id?: string }, signal?: AbortSignal) =>
    request<Alert[]>(`/alerts${query(filters)}`, { signal }),
  openAlertCount: (signal?: AbortSignal) => request<{ open: number }>('/alerts/open-count', { signal }),
  acknowledge: (id: string) => request<Alert>(`/alerts/${id}/acknowledge`, { method: 'POST' }),
  resolve: (id: string, note: string) => request<Alert>(`/alerts/${id}/resolve`, { method: 'POST', body: { note } }),

  // UC03
  users: (signal?: AbortSignal) => request<User[]>('/users', { signal }),
  createUser: (body: { full_name: string; email: string; password: string; role: Role }) =>
    request<User>('/users', { method: 'POST', body }),
  updateUser: (id: string, body: Partial<{ full_name: string; role: Role; is_active: boolean; password: string }>) =>
    request<User>(`/users/${id}`, { method: 'PATCH', body }),

  // UC13
  adminPatients: (signal?: AbortSignal) => request<AdminPatient[]>('/admin/patients', { signal }),
  assign: (patient_id: string, user_id: string) =>
    request<Assignment>('/admin/assignments', { method: 'POST', body: { patient_id, user_id } }),
  unassign: (id: string) => request<void>(`/admin/assignments/${id}`, { method: 'DELETE' }),

  // UC08
  alertSettings: (signal?: AbortSignal) => request<AlertSettings>('/admin/alert-settings', { signal }),
  saveAlertSettings: (body: { risk_critical_threshold: number | null; anomaly_threshold: number; cooldown_hours: number }) =>
    request<AlertSettings>('/admin/alert-settings', { method: 'PUT', body }),

  // UC09–UC10
  models: (signal?: AbortSignal) => request<ModelVersion[]>('/admin/models', { signal }),
  driftReports: (signal?: AbortSignal) => request<DriftReport[]>('/admin/drift-reports', { signal }),
  triggerRetrain: () => request<RetrainStatus>('/admin/models/retrain', { method: 'POST' }),
  retrainStatus: (dagRunId: string) => request<RetrainStatus>(`/admin/models/retrain/${encodeURIComponent(dagRunId)}`),
};

/** URL WebSocket cùng origin với trang (qua proxy /api). */
export function websocketUrl(token: string): string {
  const explicit = import.meta.env.VITE_WS_BASE_URL;
  const base = explicit ?? `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}${API_BASE}`;
  return `${base}/ws?token=${encodeURIComponent(token)}`;
}
