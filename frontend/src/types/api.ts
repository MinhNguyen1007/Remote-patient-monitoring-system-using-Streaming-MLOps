// Kiểu dữ liệu khớp schema Pydantic của backend (backend/app/schemas/*) và sự kiện Kafka (streaming/src/consumer.py).

export type Role = 'ADMIN' | 'DOCTOR' | 'NURSE';
export type RiskLevel = 'NORMAL' | 'WARNING' | 'CRITICAL';
export type AlertType = 'RISK' | 'ANOMALY';
export type AlertStatus = 'OPEN' | 'ACKNOWLEDGED' | 'RESOLVED';

export interface User {
  id: string;
  full_name: string;
  email: string;
  role: Role;
  is_active: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export const VITALS = ['heart_rate', 'spo2', 'respiratory_rate', 'systolic_bp', 'diastolic_bp', 'temperature'] as const;
export type Vital = (typeof VITALS)[number];

/** Một giờ dữ liệu: vitals + kết quả dự đoán. */
export interface LatestState {
  recorded_at: string;
  hour_index: number;
  heart_rate: number | null;
  spo2: number | null;
  respiratory_rate: number | null;
  systolic_bp: number | null;
  diastolic_bp: number | null;
  temperature: number | null;
  news2_score: number | null;
  risk_level: RiskLevel;
  risk_score: number;
  anomaly_score: number | null;
  is_anomaly: boolean | null;
}

export type TimelinePoint = LatestState;

export interface Patient {
  id: string;
  display_name: string;
  gender: string | null;
  age: number | null;
  mimic_subject_id: number;
  mimic_icustay_id: number;
  admitted_at: string;
}

export interface PatientSummary extends Patient {
  latest: LatestState | null;
  open_alerts: number;
  /** Mức rủi ro dự báo tối đa 12 giờ gần nhất, cũ → mới */
  recent_risk_levels: RiskLevel[];
}

export interface PatientDetail extends PatientSummary {
  /** Điểm NEWS2 (0–3) từng thông số, backend tính bằng rpm_common */
  news2_components: Record<'respiratory_rate' | 'spo2' | 'systolic_bp' | 'heart_rate' | 'temperature', number | null> | null;
}

export interface Alert {
  id: string;
  patient_id: string;
  patient_display_name: string;
  alert_type: AlertType;
  status: AlertStatus;
  created_at: string;
  prediction_id: string;
  prediction_recorded_at: string;
  hour_index: number | null;
  news2_score: number | null;
  risk_level: RiskLevel | null;
  risk_score: number | null;
  anomaly_score: number | null;
  acknowledged_by: string | null;
  acknowledged_at: string | null;
  resolved_by: string | null;
  resolved_at: string | null;
  resolution_note: string | null;
}

export interface Assignment {
  id: string;
  patient_id: string;
  user_id: string;
  user_full_name: string;
  user_role: Role;
  assigned_by: string | null;
  assigned_at: string;
}

export interface AdminPatient extends Patient {
  assignments: Assignment[];
}

export interface AlertSettings {
  risk_critical_threshold: number | null;
  anomaly_threshold: number;
  cooldown_hours: number;
  updated_by: string | null;
  updated_at: string | null;
  champion_tau_critical: number | null;
  effective_risk_threshold: number | null;
}

export interface ModelVersion {
  id: string;
  model_name: string;
  mlflow_version: string;
  mlflow_run_id: string;
  gate_status: 'PROMOTED' | 'REJECTED';
  is_champion: boolean;
  trigger: 'INITIAL' | 'DRIFT' | 'MANUAL';
  drift_report_id: string | null;
  dag_run_id: string | null;
  metrics: Record<string, number> | null;
  trained_at: string | null;
}

export interface DriftReport {
  id: string;
  run_at: string;
  window_start: string | null;
  window_end: string | null;
  n_records: number;
  reference_model_version_id: string | null;
  max_psi: number | null;
  feature_stats: Record<string, { psi: number; ks_statistic: number; n: number }> | null;
  drift_detected: boolean;
  triggered_retrain: boolean;
  dag_run_id: string | null;
}

export interface RetrainStatus {
  dag_run_id: string;
  state: string;
  start_date?: string | null;
  end_date?: string | null;
}

// ------------------------------------------------------------------ sự kiện WebSocket (/ws)

/** Sự kiện `prediction` (predictions-stream). */
export interface PredictionEvent {
  prediction_id: string;
  patient_id: string;
  subject_id: number;
  hour_index: number;
  recorded_at: string;
  predicted_at: string;
  vitals: Record<Vital, number | null>;
  vitals_filled: Record<Vital, number | null>;
  news2_score: number | null;
  risk_level: RiskLevel;
  risk_score: number;
  tau_critical: number;
  anomaly_score: number | null;
  is_anomaly: boolean | null;
  risk_model_version: string;
  anomaly_model_version: string | null;
}

/** Sự kiện `alert` (alerts-stream). */
export interface AlertEvent {
  alert_id: string;
  patient_id: string;
  subject_id: number;
  alert_type: AlertType;
  status: AlertStatus;
  created_at: string;
  prediction_id: string;
  prediction_recorded_at: string;
  hour_index: number;
  news2_score: number | null;
  risk_level: RiskLevel;
  risk_score: number;
  anomaly_score: number | null;
}

export type ServerEvent =
  | { type: 'connected'; data: { user_id: string; role: Role } }
  | { type: 'prediction'; data: PredictionEvent }
  | { type: 'alert'; data: AlertEvent }
  | { type: 'alert_update'; data: Alert };
