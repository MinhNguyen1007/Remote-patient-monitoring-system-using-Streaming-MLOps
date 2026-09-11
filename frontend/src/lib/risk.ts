import type { AlertStatus, AlertType, Role, RiskLevel } from '@/types/api';

/** Mức rủi ro: luôn gồm màu + nhãn + icon (02_8 mục 2.8.2a), không truyền đạt chỉ bằng màu. */
export const RISK_META: Record<RiskLevel, { label: string; color: string; icon: 'normal' | 'warning' | 'critical'; rank: number }> = {
  CRITICAL: { label: 'Nguy kịch', color: 'var(--risk-critical)', icon: 'critical', rank: 0 },
  WARNING: { label: 'Cảnh báo', color: 'var(--risk-warning)', icon: 'warning', rank: 1 },
  NORMAL: { label: 'Bình thường', color: 'var(--risk-normal)', icon: 'normal', rank: 2 },
};

export const ALERT_STATUS_META: Record<AlertStatus, { label: string; color: string }> = {
  OPEN: { label: 'Mở', color: 'var(--primary)' },
  ACKNOWLEDGED: { label: 'Đã xác nhận', color: 'var(--series-2)' },
  RESOLVED: { label: 'Đã xử lý', color: 'var(--muted-foreground)' },
};

export const ALERT_TYPE_META: Record<AlertType, { label: string; color: string }> = {
  RISK: { label: 'Rủi ro nguy kịch', color: 'var(--risk-critical)' },
  ANOMALY: { label: 'Bất thường', color: 'var(--anomaly-flag)' },
};

export const ROLE_LABEL: Record<Role, string> = { ADMIN: 'Quản trị viên', DOCTOR: 'Bác sĩ', NURSE: 'Điều dưỡng' };

/** Ngưỡng gắn cờ bất thường mặc định (mục 2.9.6); giá trị thật đến từ `is_anomaly` của backend. */
export const DEFAULT_TAU_ANOMALY = 0.99;
/** anomaly_score sớm nhất có ở hour_index 16 (baseline 6 giờ + cửa sổ 12 giờ, mục 2.9.3). */
export const FIRST_ANOMALY_HOUR = 16;

/** So sánh để sắp bệnh nhân: rủi ro cao nhất trước, cùng mức thì xác suất nguy kịch cao hơn trước. */
export function compareByRisk(
  a: { display_name: string; latest: { risk_level: RiskLevel; risk_score: number } | null },
  b: { display_name: string; latest: { risk_level: RiskLevel; risk_score: number } | null },
): number {
  const rank = (x: typeof a) => (x.latest ? RISK_META[x.latest.risk_level].rank : 3);
  return rank(a) - rank(b) || (b.latest?.risk_score ?? 0) - (a.latest?.risk_score ?? 0) || a.display_name.localeCompare(b.display_name);
}
