// Hàng đợi "cảnh báo mới" (02_8 mục 2.8.2d): sự kiện realtime → overlay toàn màn hình hoặc toast, kèm âm báo.
// Hàm thuần để test; component AlertReveal chỉ gọi setState với kết quả.
import type { Tier } from '@/truanayangi-ui/core/rarity';
import type { AlertEvent, DriftReportEvent, RetrainCompletedEvent, Role, ServerEvent } from '@/types/api';

import { vn } from './format';

export type RevealItem =
  | { kind: 'risk'; key: string; alert: AlertEvent }
  | { kind: 'anomaly'; key: string; alert: AlertEvent }
  | { kind: 'drift'; key: string; report: DriftReportEvent }
  | { kind: 'retrain'; key: string; result: RetrainCompletedEvent };

/** Giữ tối đa bấy nhiêu mục chờ; backend đã chống trùng/chống bão cảnh báo nên số này hiếm khi chạm. */
export const MAX_QUEUE = 20;
export const MAX_TOASTS = 4;
export const TOAST_MS = 20_000;

/**
 * Sự kiện nào đáng "báo" cho người đang xem. Server chỉ đẩy cảnh báo của bệnh nhân được phân công;
 * Admin chỉ nhận sự kiện MLOps, và chỉ drift cần báo (notify_admin) mới hiện.
 */
export function revealFor(event: ServerEvent, role: Role): RevealItem | null {
  if (event.type === 'alert' && role !== 'ADMIN') {
    if (event.data.status !== 'OPEN') return null;
    const kind = event.data.alert_type === 'RISK' ? 'risk' : 'anomaly';
    return { kind, key: `alert:${event.data.alert_id}`, alert: event.data };
  }
  if (event.type === 'drift_report' && role === 'ADMIN') {
    if (!event.data.drift_detected || !event.data.notify_admin) return null;
    return { kind: 'drift', key: `drift:${event.data.drift_report_id}`, report: event.data };
  }
  if (event.type === 'retrain_completed' && role === 'ADMIN') {
    return { kind: 'retrain', key: `retrain:${event.data.dag_run_id}`, result: event.data };
  }
  return null;
}

/** Thêm vào cuối hàng đợi, bỏ trùng theo key, giữ `limit` mục mới nhất. */
export function enqueue(queue: RevealItem[], item: RevealItem, limit = MAX_QUEUE): RevealItem[] {
  if (queue.some((x) => x.key === item.key)) return queue;
  return [...queue, item].slice(-limit);
}

/** Âm báo theo mức của bộ âm tổng hợp: nguy kịch = hạng đỏ (3), bất thường = hạng tím (1). */
export function soundTier(item: RevealItem): Tier {
  switch (item.kind) {
    case 'risk':
      return 3;
    case 'anomaly':
      return 1;
    case 'drift':
      return 2;
    case 'retrain':
      return 0;
  }
}

export const patientName = (subjectId: number) => `BN-${subjectId}`;

const MODEL_LABEL: Record<string, string> = { risk_classifier: 'Mô hình rủi ro', anomaly_detector: 'Mô hình bất thường' };
const RETRAIN_STATUS: Record<string, string> = { PROMOTED: 'lên champion', REJECTED: 'bị gate từ chối', FAILED: 'lỗi' };

/** Nội dung toast (overlay rủi ro dựng riêng trong component). */
export function toastContent(item: RevealItem): { title: string; body: string; href: string; linkLabel: string } {
  switch (item.kind) {
    case 'risk':
    case 'anomaly': {
      const a = item.alert;
      const body =
        item.kind === 'anomaly'
          ? `Điểm bất thường ${vn(a.anomaly_score, 3)} · giờ thứ ${a.hour_index}`
          : `Xác suất nguy kịch ${Math.round(a.risk_score * 100)}% · giờ thứ ${a.hour_index}`;
      return {
        title: `${patientName(a.subject_id)} · ${item.kind === 'anomaly' ? 'Diễn biến bất thường' : 'Rủi ro nguy kịch'}`,
        body,
        href: `/patients/${a.patient_id}`,
        linkLabel: 'Xem bệnh nhân →',
      };
    }
    case 'drift': {
      const r = item.report;
      const features = r.drifted_features.length ? r.drifted_features.join(', ') : '—';
      const next = r.triggered_retrain ? 'Đã tự kích hoạt huấn luyện lại.' : r.retrain_blocked_reason ? `Chưa huấn luyện lại: ${r.retrain_blocked_reason}.` : '';
      return {
        title: 'Phát hiện drift dữ liệu',
        body: `Đặc trưng lệch: ${features} · PSI lớn nhất ${vn(r.max_psi)}. ${next}`.trim(),
        href: '/admin/models',
        linkLabel: 'Xem giám sát mô hình →',
      };
    }
    case 'retrain': {
      const parts = item.result.results.map((m) => `${MODEL_LABEL[m.model_name] ?? m.model_name}${m.version ? ` v${m.version}` : ''} ${RETRAIN_STATUS[m.status] ?? m.status}`);
      return {
        title: item.result.trigger === 'DRIFT' ? 'Huấn luyện lại (do drift) đã xong' : 'Huấn luyện lại thủ công đã xong',
        body: parts.join(' · ') || 'Không có mô hình nào được huấn luyện.',
        href: '/admin/models',
        linkLabel: 'Xem giám sát mô hình →',
      };
    }
  }
}
