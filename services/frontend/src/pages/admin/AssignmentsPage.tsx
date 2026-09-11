import { Plus, Search, X } from 'lucide-react';
import { useMemo, useState } from 'react';

import { api } from '@/api/client';
import { PageHeader, StateMessage } from '@/components/layout';
import { Button } from '@/components/ui/button';
import { useAsync } from '@/hooks/useAsync';
import { dateTime, initials } from '@/lib/format';
import { ROLE_LABEL } from '@/lib/risk';
import { cn } from '@/lib/utils';
import type { AdminPatient } from '@/types/api';

import { AdminTabs, fieldClass } from './AdminTabs';

/** UC13 — master-detail: chọn bệnh nhân, gán/gỡ bác sĩ và điều dưỡng phụ trách. */
export function AssignmentsPage() {
  const patients = useAsync((signal) => api.adminPatients(signal), []);
  const users = useAsync((signal) => api.users(signal), []);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [candidate, setCandidate] = useState('');
  const [error, setError] = useState<string | null>(null);

  const list = patients.data ?? [];
  const selected = list.find((p) => p.id === selectedId) ?? list[0];
  const visible = list.filter((p) => p.display_name.toLowerCase().includes(search.trim().toLowerCase()));
  const candidates = useMemo(
    () => (users.data ?? []).filter((u) => u.is_active && u.role !== 'ADMIN' && !selected?.assignments.some((a) => a.user_id === u.id)),
    [users.data, selected],
  );

  const replacePatient = (updated: AdminPatient) => patients.setData((current) => (current ?? []).map((p) => (p.id === updated.id ? updated : p)));

  const assign = async () => {
    if (!selected || !candidate) return;
    setError(null);
    try {
      const created = await api.assign(selected.id, candidate);
      replacePatient({ ...selected, assignments: [...selected.assignments, created] });
      setCandidate('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không phân công được');
    }
  };

  const unassign = async (assignmentId: string) => {
    if (!selected) return;
    setError(null);
    try {
      await api.unassign(assignmentId);
      replacePatient({ ...selected, assignments: selected.assignments.filter((a) => a.id !== assignmentId) });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không gỡ được');
    }
  };

  return (
    <>
      <PageHeader
        eyebrow="Quản trị hệ thống · UC13"
        title="Phân công"
        subtitle="Bác sĩ và Điều dưỡng chỉ xem và nhận cảnh báo của bệnh nhân được phân công. Một bệnh nhân có thể có nhiều người phụ trách."
      />
      <AdminTabs />
      {patients.error ? (
        <StateMessage tone="error">{patients.error.message}</StateMessage>
      ) : !patients.data ? (
        <StateMessage>Đang tải…</StateMessage>
      ) : !list.length ? (
        <StateMessage>Chưa có bệnh nhân nào đang được giám sát. Bệnh nhân xuất hiện khi dữ liệu streaming bắt đầu phát lại.</StateMessage>
      ) : (
        <section className="grid grid-cols-1 items-start gap-4 lg:grid-cols-[320px_minmax(0,1fr)]">
          <div className="card flex flex-col gap-1 p-3">
            <label className="mb-2 flex h-[38px] items-center gap-2 border border-input bg-background px-3">
              <Search aria-hidden size={16} color="var(--muted-foreground)" />
              <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Tìm bệnh nhân" aria-label="Tìm bệnh nhân" className="h-full grow bg-transparent outline-none" />
            </label>
            <div className="flex max-h-[560px] flex-col gap-1 overflow-y-auto" role="listbox" aria-label="Danh sách bệnh nhân">
              {visible.map((p) => {
                const active = p.id === selected?.id;
                const count = p.assignments.length;
                return (
                  <button
                    key={p.id}
                    type="button"
                    role="option"
                    aria-selected={active}
                    onClick={() => setSelectedId(p.id)}
                    className={cn('flex h-11 items-center justify-between px-3 text-left', active ? 'bg-accent font-bold text-accent-foreground' : 'hover:bg-secondary')}
                  >
                    <span>{p.display_name}</span>
                    <span className="mono text-[12px]" style={{ color: count === 0 ? 'var(--risk-warning)' : 'var(--muted-foreground)' }}>
                      {count === 0 ? 'chưa có người phụ trách' : `${count} người`}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
          {selected && (
            <div className="card flex flex-col gap-[18px] p-[22px]">
              <div className="flex flex-col gap-1">
                <h2 className="m-0 text-[22px] font-extrabold">{selected.display_name}</h2>
                <span className="text-[13px] text-muted-foreground">
                  {selected.age ?? '—'} tuổi · {selected.gender === 'M' ? 'Nam' : selected.gender === 'F' ? 'Nữ' : '—'} · MIMIC {selected.mimic_subject_id} · đợt ICU {selected.mimic_icustay_id}
                </span>
              </div>
              <div className="flex flex-col gap-2.5">
                <span className="eyebrow">Đang phụ trách</span>
                {!selected.assignments.length && <span className="text-muted-foreground">Chưa có ai phụ trách: cảnh báo của bệnh nhân này sẽ không gửi tới ai.</span>}
                {selected.assignments.map((a) => (
                  <div key={a.id} className="flex flex-wrap items-center gap-3 border border-border bg-background px-3.5 py-3">
                    <div className="flex size-[34px] items-center justify-center bg-secondary text-[12px] font-bold">{initials(a.user_full_name)}</div>
                    <span className="font-semibold">{a.user_full_name}</span>
                    <span className="inline-flex h-6 items-center border border-border bg-secondary px-2.5 text-[12px] font-semibold">{ROLE_LABEL[a.user_role]}</span>
                    <span className="mono ml-auto text-[12px] text-muted-foreground">phân công {dateTime(a.assigned_at)}</span>
                    <Button variant="ghost" onClick={() => unassign(a.id)} className="h-8 px-2.5" aria-label={`Gỡ ${a.user_full_name}`}>
                      <X />
                      Gỡ
                    </Button>
                  </div>
                ))}
              </div>
              <div className="flex flex-col gap-2.5 border-t border-border pt-4">
                <span className="eyebrow">Thêm người phụ trách</span>
                <div className="flex gap-2.5">
                  <select value={candidate} onChange={(e) => setCandidate(e.target.value)} className={`${fieldClass} grow`} aria-label="Chọn bác sĩ hoặc điều dưỡng">
                    <option value="">Chọn Bác sĩ / Điều dưỡng…</option>
                    {candidates.map((u) => <option key={u.id} value={u.id}>{u.full_name} · {ROLE_LABEL[u.role]}</option>)}
                  </select>
                  <Button onClick={assign} disabled={!candidate} className="h-[38px] px-3.5">
                    <Plus strokeWidth={2.2} />
                    Phân công
                  </Button>
                </div>
                <span className="text-[12.5px] text-muted-foreground">Danh sách chỉ gồm tài khoản Bác sĩ / Điều dưỡng đang hoạt động.</span>
                {error && <span role="alert" className="text-[13px] text-risk-critical">{error}</span>}
              </div>
            </div>
          )}
        </section>
      )}
    </>
  );
}
