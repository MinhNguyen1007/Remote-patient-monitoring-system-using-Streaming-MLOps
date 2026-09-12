// Thành phần lâm sàng dùng chung — khớp bảng thành phần trong mockup (docs/design/mockups/png/Components.png).
import { Activity, CircleCheck, Clock, OctagonAlert, TriangleAlert, type LucideIcon } from 'lucide-react';

import { vn } from '@/lib/format';
import { ALERT_STATUS_META, ALERT_TYPE_META, DEFAULT_TAU_ANOMALY, FIRST_ANOMALY_HOUR, RISK_META } from '@/lib/risk';
import { cn } from '@/lib/utils';
import type { AlertStatus, AlertType, RiskLevel } from '@/types/api';

const RISK_ICON: Record<RiskLevel, LucideIcon> = { NORMAL: CircleCheck, WARNING: TriangleAlert, CRITICAL: OctagonAlert };

const tint = (color: string, percent: number) => `color-mix(in srgb, ${color} ${percent}%, transparent)`;

/** Badge rủi ro dự báo 4 giờ tới: icon + nhãn + xác suất; nền màu trạng thái 14%, chữ giữ màu foreground. */
export function RiskBadge({ level, score, size = 'md' }: { level: RiskLevel; score?: number | null; size?: 'md' | 'lg' }) {
  const meta = RISK_META[level];
  const Icon = RISK_ICON[level];
  const large = size === 'lg';
  return (
    <span
      data-slot="risk-badge"
      data-level={level}
      className={cn('inline-flex items-center gap-[7px] border font-bold whitespace-nowrap text-foreground', large ? 'h-10 px-3.5 text-[15px]' : 'h-7 px-2.5 text-[12.5px]')}
      style={{ background: tint(meta.color, 14), borderColor: tint(meta.color, 45) }}
    >
      <Icon aria-hidden size={large ? 18 : 15} strokeWidth={2} color={meta.color} />
      <span>{meta.label}</span>
      {score !== undefined && score !== null && <span className="mono font-medium text-muted-foreground">{vn(score)}</span>}
    </span>
  );
}

/** NEWS2 hiện tại (luật lâm sàng): màu trung tính, không lẫn với dự báo của mô hình. */
export function News2Chip({ score }: { score: number | null }) {
  return (
    <span className="mono inline-flex h-7 items-center gap-1.5 border border-border bg-secondary px-2.5" title="Điểm NEWS2 rút gọn hiện tại (0–15)">
      <span className="text-[10.5px] tracking-[1.2px] text-muted-foreground">NEWS2</span>
      <span className="text-[14px] font-semibold">{score ?? '—'}</span>
    </span>
  );
}

/** Điểm bất thường LSTM-Autoencoder.
 *
 * `null` có hai nguyên nhân khác nhau, không được nói lẫn: đợt ICU chưa đủ 16 giờ (baseline 6 giờ + cửa sổ 12 giờ),
 * hoặc đã quá giờ 16 nhưng cửa sổ 12 giờ gần nhất thiếu giá trị đo nên không dựng được (rất thường gặp: nhiều đợt
 * ICU có quãng dài không đo đủ 6 thông số).
 */
export function AnomalyChip({ score, flagged, hourIndex }: {
  score: number | null;
  flagged?: boolean | null;
  hourIndex?: number | null;
}) {
  if (score === null) {
    const tooEarly = hourIndex == null || hourIndex < FIRST_ANOMALY_HOUR;
    return (
      <span className="inline-flex items-center gap-1.5 text-[12px] text-muted-foreground">
        <Clock aria-hidden size={14} />
        {tooEarly ? 'Chưa đủ 16 giờ' : 'Thiếu dữ liệu cửa sổ'}
      </span>
    );
  }
  const isFlagged = flagged ?? score >= DEFAULT_TAU_ANOMALY;
  return (
    <span
      data-slot="anomaly-chip"
      className="inline-flex h-[26px] items-center gap-1.5 border px-2 text-[12px] font-semibold"
      style={{ borderColor: isFlagged ? tint('var(--anomaly-flag)', 50) : 'var(--border)', background: isFlagged ? tint('var(--anomaly-flag)', 14) : 'transparent' }}
    >
      <Activity aria-hidden size={14} strokeWidth={2} color={isFlagged ? 'var(--anomaly-flag)' : 'var(--muted-foreground)'} />
      <span>{isFlagged ? 'Bất thường' : 'Ổn định'}</span>
      <span className="mono font-medium text-muted-foreground">{vn(score, 3)}</span>
    </span>
  );
}

export function AlertStatusPill({ status }: { status: AlertStatus }) {
  const meta = ALERT_STATUS_META[status];
  return (
    <span className="inline-flex h-6 items-center gap-1.5 border px-2 text-[12px] font-semibold" style={{ borderColor: tint(meta.color, 50) }}>
      <span aria-hidden className="size-1.5" style={{ background: meta.color }} />
      {meta.label}
    </span>
  );
}

export function AlertTypeLabel({ type }: { type: AlertType }) {
  const meta = ALERT_TYPE_META[type];
  const Icon = type === 'RISK' ? OctagonAlert : Activity;
  return (
    <span className="inline-flex items-center gap-2 font-semibold">
      <span className="inline-flex size-7 items-center justify-center" style={{ background: tint(meta.color, 16) }}>
        <Icon aria-hidden size={16} strokeWidth={2} color={meta.color} />
      </span>
      {meta.label}
    </span>
  );
}

export function Vital({ label, value, unit }: { label: string; value: string; unit: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="mono text-[10.5px] tracking-[1.3px] text-muted-foreground">{label}</span>
      <span className="mono text-[20px] font-semibold tracking-[-0.5px]">
        {value}
        {unit && <span className="ml-[3px] text-[11px] font-medium text-muted-foreground">{unit}</span>}
      </span>
    </div>
  );
}
