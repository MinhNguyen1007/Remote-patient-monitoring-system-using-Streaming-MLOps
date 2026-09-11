// Cập nhật dữ liệu trên màn hình từ sự kiện WebSocket — hàm thuần để kiểm thử độc lập với React.
import { compareByRisk } from '@/lib/risk';
import type { LatestState, PatientSummary, PredictionEvent, TimelinePoint } from '@/types/api';

export const RECENT_HOURS = 12;

/** Trạng thái hiện hành từ sự kiện: vitals sau forward-fill (giống `latest` của API). */
export function latestFromEvent(event: PredictionEvent): LatestState {
  return {
    recorded_at: event.recorded_at,
    hour_index: event.hour_index,
    ...event.vitals_filled,
    news2_score: event.news2_score,
    risk_level: event.risk_level,
    risk_score: event.risk_score,
    anomaly_score: event.anomaly_score,
    is_anomaly: event.is_anomaly,
  };
}

/** Điểm biểu đồ từ sự kiện: vitals đo gốc, giờ không đo để trống (giống `timeline` của API). */
export function timelinePointFromEvent(event: PredictionEvent): TimelinePoint {
  return { ...latestFromEvent(event), ...event.vitals };
}

/** Dashboard: cập nhật đúng bệnh nhân, nối dải 12 giờ, sắp lại theo rủi ro. Bệnh nhân ngoài danh sách bị bỏ qua. */
export function applyPrediction(patients: PatientSummary[], event: PredictionEvent): PatientSummary[] {
  const index = patients.findIndex((p) => p.id === event.patient_id);
  if (index === -1) return patients;
  const current = patients[index];
  if (current.latest && current.latest.hour_index >= event.hour_index) return patients;
  const updated: PatientSummary = {
    ...current,
    latest: latestFromEvent(event),
    recent_risk_levels: [...current.recent_risk_levels, event.risk_level].slice(-RECENT_HOURS),
  };
  const next = patients.slice();
  next[index] = updated;
  return next.sort(compareByRisk);
}

export function applyNewAlert(patients: PatientSummary[], patientId: string): PatientSummary[] {
  return patients.map((p) => (p.id === patientId ? { ...p, open_alerts: p.open_alerts + 1 } : p));
}

/** Biểu đồ chi tiết: thêm giờ mới, bỏ giờ cũ nhất khi vượt cửa sổ đang xem. */
export function appendTimeline(points: TimelinePoint[], event: PredictionEvent, windowHours: number): TimelinePoint[] {
  const last = points[points.length - 1];
  if (last && last.hour_index >= event.hour_index) return points;
  return [...points, timelinePointFromEvent(event)].slice(-windowHours);
}
