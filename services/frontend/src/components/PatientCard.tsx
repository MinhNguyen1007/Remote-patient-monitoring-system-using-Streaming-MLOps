import { Bell } from 'lucide-react';
import type { CSSProperties } from 'react';
import { Link } from 'react-router-dom';

import { AnomalyChip, News2Chip, RiskBadge, Vital } from '@/components/clinical';
import { bloodPressure, timeAgo, vitalText } from '@/lib/format';
import { RECENT_HOURS } from '@/lib/realtime';
import { RISK_META } from '@/lib/risk';
import type { PatientSummary } from '@/types/api';

/** Thẻ bệnh nhân (02_8 mục 2.8.4b): thẻ CS:GO của truanayangi-ui — ánh màu mức rủi ro dâng lên từ thanh đáy 5 px. */
export function PatientCard({ patient, now }: { patient: PatientSummary; now: number }) {
  const latest = patient.latest;
  const color = latest ? RISK_META[latest.risk_level].color : 'var(--border)';
  const padding = Math.max(0, RECENT_HOURS - patient.recent_risk_levels.length);
  return (
    <Link
      to={`/patients/${patient.id}`}
      data-slot="patient-card"
      className="tn-card tn-card--small patient-card"
      style={{ '--tn-rarity': color } as CSSProperties}
      aria-label={`${patient.display_name}${latest ? ', ' + RISK_META[latest.risk_level].label : ''}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-[3px]">
          <span className="text-[19px] text-white">{patient.display_name}</span>
          <span className="muted text-[12.5px]">
            {patient.age ?? '—'} tuổi · {patient.gender === 'M' ? 'Nam' : patient.gender === 'F' ? 'Nữ' : '—'}
            {latest && ` · giờ thứ ${latest.hour_index}`}
          </span>
        </div>
        {latest ? <RiskBadge level={latest.risk_level} score={latest.risk_score} /> : <span className="muted text-[12px]">Chưa có dữ liệu</span>}
      </div>
      <div className="grid grid-cols-4 gap-2.5">
        <Vital label="HR" value={vitalText(latest?.heart_rate)} unit="bpm" />
        <Vital label="SPO₂" value={vitalText(latest?.spo2)} unit="%" />
        <Vital label="RR" value={vitalText(latest?.respiratory_rate)} unit="/ph" />
        <Vital label="HA" value={latest ? bloodPressure(latest.systolic_bp, latest.diastolic_bp) : '—'} unit="" />
      </div>
      <div className="flex flex-col gap-1.5">
        <div className="muted flex justify-between text-[12px]">
          <span>Rủi ro 12 giờ qua</span>
          <span>bây giờ</span>
        </div>
        <div className="flex gap-0.5" role="img" aria-label={`Mức rủi ro ${patient.recent_risk_levels.length} giờ gần nhất`}>
          {Array.from({ length: padding }, (_, i) => (
            <span key={`pad-${i}`} className="h-2 grow bg-[#ffffff14]" />
          ))}
          {patient.recent_risk_levels.map((level, i) => (
            <span key={i} className="h-2 grow" style={{ background: RISK_META[level].color, opacity: 0.85 }} title={RISK_META[level].label} />
          ))}
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <News2Chip score={latest?.news2_score ?? null} />
        <AnomalyChip score={latest?.anomaly_score ?? null} flagged={latest?.is_anomaly} hourIndex={latest?.hour_index} />
      </div>
      <div className="flex items-center justify-between border-t border-[#ffffff20] pt-3">
        {patient.open_alerts > 0 ? (
          <span className="inline-flex items-center gap-1.5 text-[13px]">
            <Bell aria-hidden size={15} color="var(--risk-critical)" strokeWidth={2} />
            {patient.open_alerts} cảnh báo mở
          </span>
        ) : (
          <span className="muted text-[12.5px]">Không có cảnh báo mở</span>
        )}
        <span className="muted text-[12px]">{timeAgo(latest?.recorded_at, now)}</span>
      </div>
    </Link>
  );
}
