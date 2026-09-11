import { Search } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

import { api } from '@/api/client';
import { RealtimeIndicator, PageHeader, Segmented, StateMessage } from '@/components/layout';
import { PatientCard } from '@/components/PatientCard';
import { useServerEvents } from '@/context/WebSocketContext';
import { useAsync } from '@/hooks/useAsync';
import { applyNewAlert, applyPrediction } from '@/lib/realtime';
import type { PatientSummary } from '@/types/api';

type Filter = 'ALL' | 'CRITICAL' | 'WARNING';

/** Đồng hồ cho nhãn "x giây trước", cập nhật mỗi 5 giây. */
function useNow(intervalMs = 5000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(timer);
  }, [intervalMs]);
  return now;
}

/** UC04 — chỉ bệnh nhân được phân công (backend lọc), sắp theo rủi ro dự báo, cập nhật qua WebSocket. */
export function DashboardPage() {
  const { data: patients, error, loading, setData, reload } = useAsync<PatientSummary[]>((signal) => api.patients(signal), []);
  const [filter, setFilter] = useState<Filter>('ALL');
  const [search, setSearch] = useState('');
  const now = useNow();

  useServerEvents((event) => {
    if (event.type === 'prediction') setData((current) => (current ? applyPrediction(current, event.data) : current!));
    else if (event.type === 'alert') setData((current) => (current ? applyNewAlert(current, event.data.patient_id) : current!));
    else if (event.type === 'alert_update') reload();
  });

  const counts = useMemo(() => {
    const list = patients ?? [];
    return {
      ALL: list.length,
      CRITICAL: list.filter((p) => p.latest?.risk_level === 'CRITICAL').length,
      WARNING: list.filter((p) => p.latest?.risk_level === 'WARNING').length,
    };
  }, [patients]);

  const visible = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    return (patients ?? []).filter(
      (p) => (filter === 'ALL' || p.latest?.risk_level === filter) && (!keyword || p.display_name.toLowerCase().includes(keyword)),
    );
  }, [patients, filter, search]);

  return (
    <>
      <PageHeader
        eyebrow={`Bệnh nhân được phân công · ${counts.ALL}`}
        title="Theo dõi bệnh nhân"
        actions={
          <>
            <RealtimeIndicator />
            <Segmented
              label="Lọc theo mức rủi ro"
              value={filter}
              onChange={setFilter}
              options={[
                { value: 'ALL', label: 'Tất cả', count: counts.ALL },
                { value: 'CRITICAL', label: 'Nguy kịch', count: counts.CRITICAL },
                { value: 'WARNING', label: 'Cảnh báo', count: counts.WARNING },
              ]}
            />
          </>
        }
      />
      <div className="flex flex-wrap items-center justify-between gap-4">
        <label className="flex h-[38px] w-[320px] items-center gap-2 border border-input bg-background px-3 focus-within:outline-2 focus-within:outline-offset-3 focus-within:outline-primary">
          <Search aria-hidden size={16} color="var(--muted-foreground)" />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Tìm theo mã bệnh nhân" aria-label="Tìm theo mã bệnh nhân" className="h-full grow bg-transparent outline-none" />
        </label>
        <span className="text-[13px] text-muted-foreground">Sắp xếp: rủi ro dự báo cao nhất lên đầu</span>
      </div>
      {error ? (
        <StateMessage tone="error">Không tải được danh sách bệnh nhân: {error.message}</StateMessage>
      ) : loading && !patients ? (
        <StateMessage>Đang tải danh sách bệnh nhân…</StateMessage>
      ) : !patients?.length ? (
        <StateMessage>Bạn chưa được phân công bệnh nhân nào. Liên hệ Quản trị viên để được phân công.</StateMessage>
      ) : !visible.length ? (
        <StateMessage>Không có bệnh nhân khớp bộ lọc.</StateMessage>
      ) : (
        <section className="card-grid grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {visible.map((patient) => (
            <PatientCard key={patient.id} patient={patient} now={now} />
          ))}
        </section>
      )}
    </>
  );
}
