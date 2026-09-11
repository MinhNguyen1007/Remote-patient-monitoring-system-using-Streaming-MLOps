import { Plus } from 'lucide-react';
import { useMemo, useState, type FormEvent } from 'react';

import { api } from '@/api/client';
import { PageHeader, StateMessage } from '@/components/layout';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Switch } from '@/components/ui/switch';
import { useAuth } from '@/context/AuthContext';
import { useAsync } from '@/hooks/useAsync';
import { ROLE_LABEL } from '@/lib/risk';
import type { Role, User } from '@/types/api';

import { AdminTabs, fieldClass } from './AdminTabs';

/** UC03 — CRUD tài khoản. Không xóa cứng: khóa bằng is_active để giữ lịch sử xử lý cảnh báo. */
export function UsersPage() {
  const { user: me } = useAuth();
  const users = useAsync((signal) => api.users(signal), []);
  const patients = useAsync((signal) => api.adminPatients(signal), []);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const assignedCount = useMemo(() => {
    const counts = new Map<string, number>();
    for (const patient of patients.data ?? []) for (const a of patient.assignments) counts.set(a.user_id, (counts.get(a.user_id) ?? 0) + 1);
    return counts;
  }, [patients.data]);

  const update = async (target: User, body: Parameters<typeof api.updateUser>[1]) => {
    setError(null);
    try {
      const saved = await api.updateUser(target.id, body);
      users.setData((list) => (list ?? []).map((u) => (u.id === saved.id ? saved : u)));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không cập nhật được');
    }
  };

  return (
    <>
      <PageHeader
        eyebrow="Quản trị hệ thống"
        title="Người dùng"
        actions={
          <Button onClick={() => setCreating(true)} className="h-9 px-3.5">
            <Plus strokeWidth={2.2} />
            Thêm tài khoản
          </Button>
        }
      />
      <AdminTabs />
      {error && <StateMessage tone="error">{error}</StateMessage>}
      {users.error ? (
        <StateMessage tone="error">{users.error.message}</StateMessage>
      ) : !users.data ? (
        <StateMessage>Đang tải…</StateMessage>
      ) : (
        <section className="card overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr>
                <th className="th">Họ tên</th>
                <th className="th">Email</th>
                <th className="th">Vai trò</th>
                <th className="th">Trạng thái</th>
                <th className="th">Bệnh nhân phụ trách</th>
              </tr>
            </thead>
            <tbody>
              {users.data.map((u) => {
                const self = u.id === me?.id;
                return (
                  <tr key={u.id}>
                    <td className="td font-semibold">{u.full_name}{self && <span className="ml-2 text-[12px] font-normal text-muted-foreground">(bạn)</span>}</td>
                    <td className="td mono text-[13px]">{u.email}</td>
                    <td className="td">
                      <select
                        aria-label={`Vai trò của ${u.full_name}`}
                        value={u.role}
                        disabled={self}
                        onChange={(e) => update(u, { role: e.target.value as Role })}
                        className={`${fieldClass} h-8 pr-8`}
                      >
                        {(Object.keys(ROLE_LABEL) as Role[]).map((role) => <option key={role} value={role}>{ROLE_LABEL[role]}</option>)}
                      </select>
                    </td>
                    <td className="td">
                      <label className="inline-flex items-center gap-2.5">
                        <Switch checked={u.is_active} disabled={self} onCheckedChange={(checked) => update(u, { is_active: checked })} aria-label={`Kích hoạt tài khoản ${u.full_name}`} />
                        <span className={u.is_active ? '' : 'text-muted-foreground'}>{u.is_active ? 'Hoạt động' : 'Đã khóa'}</span>
                      </label>
                    </td>
                    <td className="td mono">{u.role === 'ADMIN' ? '—' : (assignedCount.get(u.id) ?? 0)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
      )}
      <CreateUserDialog open={creating} onOpenChange={setCreating} onCreated={(created) => users.setData((list) => [...(list ?? []), created])} />
    </>
  );
}

function CreateUserDialog({ open, onOpenChange, onCreated }: { open: boolean; onOpenChange: (open: boolean) => void; onCreated: (user: User) => void }) {
  const [form, setForm] = useState({ full_name: '', email: '', password: '', role: 'DOCTOR' as Role });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onCreated(await api.createUser(form));
      setForm({ full_name: '', email: '', password: '', role: 'DOCTOR' });
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không tạo được tài khoản');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="border border-border p-6 sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-[18px] font-bold">Thêm tài khoản</DialogTitle>
          <DialogDescription className="text-muted-foreground">Mật khẩu tối thiểu 8 ký tự. Bác sĩ/Điều dưỡng chỉ thấy bệnh nhân sau khi được phân công.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-3.5">
          <label className="flex flex-col gap-1.5 text-[13px] font-semibold">Họ tên
            <input required className={fieldClass} value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
          </label>
          <label className="flex flex-col gap-1.5 text-[13px] font-semibold">Email
            <input required type="email" className={fieldClass} value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </label>
          <label className="flex flex-col gap-1.5 text-[13px] font-semibold">Mật khẩu
            <input required minLength={8} type="password" autoComplete="new-password" className={fieldClass} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
          </label>
          <label className="flex flex-col gap-1.5 text-[13px] font-semibold">Vai trò
            <select className={fieldClass} value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as Role })}>
              {(Object.keys(ROLE_LABEL) as Role[]).map((role) => <option key={role} value={role}>{ROLE_LABEL[role]}</option>)}
            </select>
          </label>
          {error && <span role="alert" className="text-[13px] text-risk-critical">{error}</span>}
          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} className="h-9 px-3.5">Hủy</Button>
            <Button type="submit" disabled={busy} className="h-9 px-3.5">Tạo tài khoản</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
