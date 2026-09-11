import { ChevronLeft } from 'lucide-react';
import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { api } from '@/api/client';
import { AlertActions } from '@/components/AlertActions';
import { VitalsChart } from '@/components/charts/VitalsChart';
import { CHART } from '@/components/charts/palette';
import { AlertStatusPill, AlertTypeLabel, AnomalyChip, RiskBadge } from '@/components/clinical';
import { PageHeader, RealtimeIndicator, Segmented, StateMessage } from '@/components/layout';
import { useAuth } from '@/context/AuthContext';
import { useServerEvents } from '@/context/WebSocketContext';
import { useAsync } from '@/hooks/useAsync';
import { clock, dateTime, vn } from '@/lib/format';
import { appendTimeline } from '@/lib/realtime';
import { DEFAULT_TAU_ANOMALY, RISK_META } from '@/lib/risk';
import type { Alert, PatientDetail } from '@/types/api';

const WINDOWS = { '24': 24, '48': 48, all: 1000 } as const;
type WindowKey = keyof typeof WINDOWS;
const NEWS2_LABELS: [keyof NonNullable<PatientDetail['news2_components']>, string][] = [
  ['respiratory_rate', 'Nhịp thở'],
  ['spo2', 'SpO₂'],
  ['systolic_bp', 'Huyết áp tâm thu'],
  ['heart_rate', 'Nhịp tim'],
  ['temperature', 'Nhiệt độ'],
];

/** UC05, UC06, UC07 — chi tiết bệnh nhân được phân công (backend trả 403 nếu không được phân công). */
export function PatientDetailPage() {
  const { patientId = '' } = useParams();
  const { user } = useAuth();
  const [windowKey, setWindowKey] = useState<WindowKey>('48');
  const [model, setModel] = useState<{ tau: number; version: string } | null>(null);
  const hours = WINDOWS[windowKey];

  const patient = useAsync((signal) => api.patient(patientId, signal), [patientId]);
  const timeline = useAsync((signal) => api.timeline(patientId, hours, signal), [patientId, hours]);
  const alerts = useAsync((signal) => api.patientAlerts(patientId, signal), [patientId]);

  useServerEvents((event) => {
    if (event.type === 'prediction' && event.data.patient_id === patientId) {
      setModel({ tau: event.data.tau_critical, version: event.data.risk_model_version });
      timeline.setData((points) => appendTimeline(points ?? [], event.data, hours));
      patient.reload(); // điểm NEWS2 từng thông số do backend tính (rpm_common)
    } else if (event.type === 'alert' && event.data.patient_id === patientId) {
      alerts.reload();
    } else if (event.type === 'alert_update' && event.data.patient_id === patientId) {
      alerts.setData((list) => (list ?? []).map((a) => (a.id === event.data.id ? event.data : a)));
    }
  });

  if (patient.error) {
    return (
      <>
        <BackLink />
        <StateMessage tone="error">{patient.error.message}</StateMessage>
      </>
    );
  }
  const detail = patient.data;
  if (!detail) return <StateMessage>Đang tải bệnh nhân…</StateMessage>;

  const latest = detail.latest;
  const isDoctor = user?.role === 'DOCTOR';
  const replaceAlert = (updated: Alert) => alerts.setData((list) => (list ?? []).map((a) => (a.id === updated.id ? updated : a)));
  const openCount = (alerts.data ?? []).filter((a) => a.status === 'OPEN').length;
  const riskColor = latest ? RISK_META[latest.risk_level].color : 'var(--border)';

  return (
    <>
      <BackLink />
      <PageHeader
        eyebrow={`Chi tiết bệnh nhân · MIMIC ${detail.mimic_subject_id} · đợt ICU ${detail.mimic_icustay_id}`}
        title={detail.display_name}
        subtitle={`${detail.age ?? '—'} tuổi · ${detail.gender === 'M' ? 'Nam' : detail.gender === 'F' ? 'Nữ' : '—'} · theo dõi từ ${clock(detail.admitted_at)}${latest ? ` · giờ dữ liệu thứ ${latest.hour_index}` : ''}`}
        actions={<RealtimeIndicator />}
      />

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-[1.35fr_1fr_1fr]">
        <div
          className="card flex flex-col gap-3.5 p-5"
          style={{
            borderBottom: `3px solid ${riskColor}`,
            boxShadow: latest?.risk_level === 'CRITICAL' ? `0 0 0 1px color-mix(in srgb, ${riskColor} 25%, transparent), 0 0 32px color-mix(in srgb, ${riskColor} 12%, transparent)` : undefined,
          }}
        >
          <span className="eyebrow">Rủi ro dự báo 4 giờ tới</span>
          {latest ? (
            <>
              <div className="flex items-center gap-3.5">
                <RiskBadge level={latest.risk_level} size="lg" />
                <span className="mono text-[36px] font-semibold tracking-[-1.5px]">
                  {Math.round(latest.risk_score * 100)}
                  <span className="text-[18px] text-muted-foreground">%</span>
                </span>
              </div>
              <span className="text-[12.5px] text-muted-foreground">
                Xác suất nguy kịch trong 4 giờ tới{model && ` · ngưỡng τ_critical ${vn(model.tau)} (model champion v${model.version})`}
              </span>
            </>
          ) : (
            <span className="text-muted-foreground">Chưa có dự đoán</span>
          )}
        </div>
        <div className="card flex flex-col gap-3 p-5">
          <div className="flex items-baseline justify-between">
            <span className="eyebrow">NEWS2 hiện tại</span>
            <span className="mono text-[30px] font-semibold tracking-[-1px]">
              {latest?.news2_score ?? '—'}
              <span className="text-[14px] text-muted-foreground"> /15</span>
            </span>
          </div>
          <div className="flex flex-col gap-1.5 text-[12.5px]">
            {NEWS2_LABELS.map(([key, label]) => {
              const points = detail.news2_components?.[key] ?? null;
              return (
                <div key={key} className="flex items-center gap-2.5">
                  <span className="grow text-muted-foreground">{label}</span>
                  <div className="flex gap-[3px]" aria-hidden>
                    {[0, 1, 2].map((k) => (
                      <span key={k} className="h-2 w-3.5" style={{ background: points !== null && k < points ? CHART.ink : 'var(--secondary)', opacity: points !== null && k < points ? 0.85 : 1 }} />
                    ))}
                  </div>
                  <span className="mono w-3.5 text-right font-semibold">{points ?? '—'}</span>
                </div>
              );
            })}
          </div>
        </div>
        <div className="card flex flex-col gap-3 p-5">
          <span className="eyebrow">Diễn biến bất thường</span>
          <div>
            <AnomalyChip score={latest?.anomaly_score ?? null} flagged={latest?.is_anomaly} />
          </div>
          <span className="text-[12.5px] text-pretty text-muted-foreground">
            {latest?.anomaly_score === null || !latest
              ? 'Cần 16 giờ dữ liệu (baseline 6 giờ + cửa sổ 12 giờ) trước khi chấm điểm bất thường.'
              : `Lỗi tái tạo 12 giờ gần nhất lớn hơn ${vn((latest.anomaly_score ?? 0) * 100, 1)}% cửa sổ bình thường. Ngưỡng gắn cờ ${vn(DEFAULT_TAU_ANOMALY)}.`}
          </span>
        </div>
      </section>

      <section className="card flex flex-col gap-3.5 px-5 pt-5 pb-3">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <h2 className="block-title">Vitals {windowKey === 'all' ? 'cả đợt' : `${hours} giờ gần nhất`}</h2>
          <div className="flex flex-wrap items-center gap-4 text-[12px] text-muted-foreground">
            <span className="inline-flex items-center gap-1.5"><span className="h-0.5 w-3.5" style={{ background: CHART.series }} />Giá trị đo</span>
            <span className="inline-flex items-center gap-1.5"><span className="h-2 w-3.5 bg-white/10" />Vùng 0 điểm NEWS2</span>
            <span className="inline-flex items-center gap-1.5"><span className="h-3 w-0.5" style={{ background: CHART.anomaly }} />Giờ bị gắn cờ bất thường</span>
            <Segmented label="Khoảng thời gian" value={windowKey} onChange={setWindowKey} options={[{ value: '24', label: '24 giờ' }, { value: '48', label: '48 giờ' }, { value: 'all', label: 'Cả đợt' }]} />
          </div>
        </div>
        {timeline.error ? <StateMessage tone="error">{timeline.error.message}</StateMessage> : <VitalsChart points={timeline.data ?? []} tauAnomaly={DEFAULT_TAU_ANOMALY} />}
      </section>

      <section className="card flex flex-col gap-3 p-5">
        <div className="flex items-center justify-between">
          <h2 className="block-title">Cảnh báo của bệnh nhân</h2>
          <span className="mono text-[12px] text-muted-foreground">{alerts.data?.length ?? 0} cảnh báo · {openCount} đang mở</span>
        </div>
        {!alerts.data?.length ? (
          <span className="text-muted-foreground">Chưa có cảnh báo.</span>
        ) : (
          <div className="grid grid-cols-1 items-start gap-3 lg:grid-cols-3">
            {alerts.data.map((alert) => (
              <article key={alert.id} className="flex flex-col gap-2.5 border border-border bg-background p-3.5">
                <div className="flex items-center justify-between gap-2">
                  <AlertTypeLabel type={alert.alert_type} />
                  <AlertStatusPill status={alert.status} />
                </div>
                <span className="text-[12.5px] text-muted-foreground">
                  Giờ thứ {alert.hour_index ?? '—'} · {clock(alert.prediction_recorded_at)} ·{' '}
                  {alert.alert_type === 'ANOMALY' ? `điểm bất thường ${vn(alert.anomaly_score, 3)}` : `NEWS2 ${alert.news2_score ?? '—'} · xác suất ${vn(alert.risk_score)}`}
                </span>
                {alert.status === 'RESOLVED' && alert.resolution_note && (
                  <span className="text-[12.5px]">“{alert.resolution_note}” <span className="text-muted-foreground">— {dateTime(alert.resolved_at)}</span></span>
                )}
                {isDoctor && <AlertActions alert={alert} onChanged={replaceAlert} />}
              </article>
            ))}
          </div>
        )}
      </section>
    </>
  );
}

function BackLink() {
  return (
    <Link to="/patients" className="inline-flex items-center gap-1.5 text-[13px] font-semibold text-muted-foreground hover:text-foreground">
      <ChevronLeft size={16} />
      Danh sách bệnh nhân
    </Link>
  );
}
