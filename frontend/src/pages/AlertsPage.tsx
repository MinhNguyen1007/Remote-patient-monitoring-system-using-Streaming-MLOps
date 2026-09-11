import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import { api } from '@/api/client';
import { AlertActions } from '@/components/AlertActions';
import { AlertStatusPill, AlertTypeLabel } from '@/components/clinical';
import { PageHeader, RealtimeIndicator, Segmented, StateMessage } from '@/components/layout';
import { useAuth } from '@/context/AuthContext';
import { useServerEvents } from '@/context/WebSocketContext';
import { useAsync } from '@/hooks/useAsync';
import { clock, vn } from '@/lib/format';
import { cn } from '@/lib/utils';
import type { Alert, AlertStatus, AlertType } from '@/types/api';

type StatusFilter = AlertStatus | 'ALL';
type TypeFilter = AlertType | 'ALL';

/** UC06, UC07 — cảnh báo của mọi bệnh nhân được phân công; chỉ Bác sĩ có cột Thao tác. */
export function AlertsPage() {
  const { user } = useAuth();
  const isDoctor = user?.role === 'DOCTOR';
  const [status, setStatus] = useState<StatusFilter>('OPEN');
  const [type, setType] = useState<TypeFilter>('ALL');
  const [arrived, setArrived] = useState<Set<string>>(() => new Set());

  // Tải toàn bộ (tối đa 500) rồi lọc tại chỗ để đếm được số lượng của từng trạng thái
  const alerts = useAsync((signal) => api.alerts({}, signal), []);

  useServerEvents((event) => {
    if (event.type === 'alert') {
      setArrived((ids) => new Set(ids).add(event.data.alert_id));
      alerts.reload();
    } else if (event.type === 'alert_update') {
      alerts.setData((list) => (list ?? []).map((a) => (a.id === event.data.id ? event.data : a)));
    }
  });

  const all = alerts.data ?? [];
  const counts = useMemo(
    () => ({
      OPEN: all.filter((a) => a.status === 'OPEN').length,
      ACKNOWLEDGED: all.filter((a) => a.status === 'ACKNOWLEDGED').length,
      RESOLVED: all.filter((a) => a.status === 'RESOLVED').length,
      ALL: all.length,
    }),
    [all],
  );
  const visible = all.filter((a) => (status === 'ALL' || a.status === status) && (type === 'ALL' || a.alert_type === type));
  const replace = (updated: Alert) => alerts.setData((list) => (list ?? []).map((a) => (a.id === updated.id ? updated : a)));

  return (
    <>
      <PageHeader eyebrow="Cảnh báo của bệnh nhân được phân công" title="Trung tâm cảnh báo" actions={<RealtimeIndicator />} />
      <div className="flex flex-wrap items-center justify-between gap-4">
        <Segmented
          label="Lọc theo trạng thái"
          value={status}
          onChange={setStatus}
          options={[
            { value: 'OPEN', label: 'Mở', count: counts.OPEN },
            { value: 'ACKNOWLEDGED', label: 'Đã xác nhận', count: counts.ACKNOWLEDGED },
            { value: 'RESOLVED', label: 'Đã xử lý', count: counts.RESOLVED },
            { value: 'ALL', label: 'Tất cả', count: counts.ALL },
          ]}
        />
        <Segmented
          label="Lọc theo loại"
          value={type}
          onChange={setType}
          options={[
            { value: 'ALL', label: 'Mọi loại' },
            { value: 'RISK', label: 'Rủi ro' },
            { value: 'ANOMALY', label: 'Bất thường' },
          ]}
        />
      </div>
      {alerts.error ? (
        <StateMessage tone="error">Không tải được cảnh báo: {alerts.error.message}</StateMessage>
      ) : alerts.loading && !alerts.data ? (
        <StateMessage>Đang tải cảnh báo…</StateMessage>
      ) : !visible.length ? (
        <StateMessage>Không có cảnh báo nào khớp bộ lọc.</StateMessage>
      ) : (
        <section className="card overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr>
                <th className="th">Loại</th>
                <th className="th">Bệnh nhân</th>
                <th className="th">Thời điểm</th>
                <th className="th">NEWS2</th>
                <th className="th">Điểm</th>
                <th className="th">Trạng thái</th>
                {isDoctor && <th className="th text-right">Thao tác</th>}
              </tr>
            </thead>
            <tbody>
              {visible.map((alert) => {
                const isNew = arrived.has(alert.id) && alert.status === 'OPEN';
                return (
                  <tr key={alert.id} className={cn(isNew && 'arrive')}>
                    <td className="td">
                      <div className="flex items-center gap-2.5">
                        <AlertTypeLabel type={alert.alert_type} />
                        {isNew && <span className="mono bg-primary px-1.5 py-0.5 text-[10.5px] font-semibold tracking-[1px] text-primary-foreground">MỚI</span>}
                      </div>
                    </td>
                    <td className="td">
                      <Link to={`/patients/${alert.patient_id}`} className="font-bold hover:text-primary">{alert.patient_display_name}</Link>
                    </td>
                    <td className="td">
                      <span className="mono">{clock(alert.prediction_recorded_at)}</span>
                      <span className="text-[12px] text-muted-foreground"> · giờ {alert.hour_index ?? '—'}</span>
                    </td>
                    <td className="td mono font-semibold">{alert.alert_type === 'ANOMALY' ? '—' : (alert.news2_score ?? '—')}</td>
                    <td className="td">
                      <div className="flex flex-col">
                        <span className="mono font-semibold">{alert.alert_type === 'ANOMALY' ? vn(alert.anomaly_score, 3) : vn(alert.risk_score)}</span>
                        <span className="text-[11.5px] text-muted-foreground">{alert.alert_type === 'ANOMALY' ? 'Điểm bất thường' : 'Xác suất nguy kịch'}</span>
                      </div>
                    </td>
                    <td className="td"><AlertStatusPill status={alert.status} /></td>
                    {isDoctor && (
                      <td className="td w-[280px] text-right">
                        <div className="flex justify-end">
                          <AlertActions alert={alert} onChanged={replace} compact />
                        </div>
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
      )}
    </>
  );
}
