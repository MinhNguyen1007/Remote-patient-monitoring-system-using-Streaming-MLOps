import { vi } from 'vitest';

import type { Alert, LatestState, PatientSummary, PredictionEvent, User } from '@/types/api';

export const user = (role: User['role'], name = 'Người dùng'): User => ({
  id: `${role}-id`,
  full_name: name,
  email: `${role.toLowerCase()}@rpm.local`,
  role,
  is_active: true,
  created_at: '2026-09-11T00:00:00Z',
});

export const latest = (overrides: Partial<LatestState> = {}): LatestState => ({
  recorded_at: '2026-09-11T05:30:00Z',
  hour_index: 10,
  heart_rate: 80,
  spo2: 97,
  respiratory_rate: 16,
  systolic_bp: 120,
  diastolic_bp: 70,
  temperature: 37,
  news2_score: 1,
  risk_level: 'NORMAL',
  risk_score: 0.05,
  anomaly_score: null,
  is_anomaly: null,
  ...overrides,
});

export const patient = (id: string, overrides: Partial<PatientSummary> = {}): PatientSummary => ({
  id,
  display_name: `BN-${id}`,
  gender: 'F',
  age: 70,
  mimic_subject_id: 1,
  mimic_icustay_id: 10,
  admitted_at: '2026-09-11T05:00:00Z',
  latest: latest(),
  open_alerts: 0,
  recent_risk_levels: ['NORMAL'],
  ...overrides,
});

export const prediction = (patientId: string, overrides: Partial<PredictionEvent> = {}): PredictionEvent => {
  const vitals = { heart_rate: 130, spo2: 90, respiratory_rate: 26, systolic_bp: 90, diastolic_bp: 50, temperature: null };
  return {
    prediction_id: 'p',
    patient_id: patientId,
    subject_id: 1,
    hour_index: 11,
    recorded_at: '2026-09-11T05:31:00Z',
    predicted_at: '2026-09-11T05:31:00Z',
    vitals,
    vitals_filled: { ...vitals, temperature: 38.1 },
    news2_score: 9,
    risk_level: 'CRITICAL',
    risk_score: 0.7,
    tau_critical: 0.22,
    anomaly_score: 0.995,
    is_anomaly: true,
    risk_model_version: '2',
    anomaly_model_version: '3',
    ...overrides,
  };
};

export const alert = (overrides: Partial<Alert> = {}): Alert => ({
  id: 'a1',
  patient_id: 'p1',
  patient_display_name: 'BN-p1',
  alert_type: 'RISK',
  status: 'OPEN',
  created_at: '2026-09-11T05:31:00Z',
  prediction_id: 'pred',
  prediction_recorded_at: '2026-09-11T05:31:00Z',
  hour_index: 11,
  news2_score: 9,
  risk_level: 'CRITICAL',
  risk_score: 0.7,
  anomaly_score: null,
  acknowledged_by: null,
  acknowledged_at: null,
  resolved_by: null,
  resolved_at: null,
  resolution_note: null,
  ...overrides,
});

/** WebSocket giả: không mở kết nối thật; test phát sự kiện bằng `emit`. */
export class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  static OPEN = 1;
  readyState = 1;
  onopen: (() => void) | null = null;
  onmessage: ((message: { data: string }) => void) | null = null;
  onclose: ((event: { code: number }) => void) | null = null;
  constructor(public url: string) {
    FakeWebSocket.instances.push(this);
    queueMicrotask(() => this.onopen?.());
  }
  send() {}
  close() {}
  emit(event: unknown) {
    this.onmessage?.({ data: JSON.stringify(event) });
  }
}

/** fetch giả theo đường dẫn: `routes['/patients'] = body`. */
export function mockFetch(routes: Record<string, unknown>, status = 200) {
  const fn = vi.fn(async (input: string | URL) => {
    const path = String(input).replace(/^\/api/, '').split('?')[0];
    const body = routes[path];
    return new Response(JSON.stringify(body ?? { detail: 'không có' }), { status: body === undefined ? 404 : status, headers: { 'Content-Type': 'application/json' } });
  });
  vi.stubGlobal('fetch', fn);
  return fn;
}
