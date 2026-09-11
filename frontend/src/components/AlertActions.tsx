import { Check } from 'lucide-react';
import { useState } from 'react';

import { api } from '@/api/client';
import { Button } from '@/components/ui/button';
import type { Alert } from '@/types/api';

/**
 * Thao tác UC07 (chỉ Bác sĩ): Mở → Xác nhận; Đã xác nhận → Đã xử lý kèm ghi chú bắt buộc.
 * Backend kiểm tra lại quyền và thứ tự chuyển trạng thái (409 nếu sai), giao diện chỉ hiện nút hợp lệ.
 */
export function AlertActions({ alert, onChanged, compact = false }: { alert: Alert; onChanged: (updated: Alert) => void; compact?: boolean }) {
  const [note, setNote] = useState('');
  const [resolving, setResolving] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async (action: () => Promise<Alert>) => {
    setBusy(true);
    setError(null);
    try {
      onChanged(await action());
      setResolving(false);
      setNote('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thực hiện được');
    } finally {
      setBusy(false);
    }
  };

  if (alert.status === 'RESOLVED') return null;

  if (alert.status === 'OPEN') {
    return (
      <div className="flex flex-col items-end gap-1">
        <Button onClick={() => run(() => api.acknowledge(alert.id))} disabled={busy} className={compact ? 'h-8 px-3' : 'h-9 px-3.5'}>
          <Check strokeWidth={2.2} />
          Xác nhận
        </Button>
        {error && <span role="alert" className="text-[12px] text-risk-critical">{error}</span>}
      </div>
    );
  }

  if (!resolving) {
    return (
      <Button variant="outline" onClick={() => setResolving(true)} className={compact ? 'h-8 px-3' : 'h-9 px-3.5'}>
        Đã xử lý…
      </Button>
    );
  }

  return (
    <form
      className="flex w-full flex-col gap-2"
      onSubmit={(event) => {
        event.preventDefault();
        if (note.trim()) run(() => api.resolve(alert.id, note.trim()));
      }}
    >
      <textarea
        autoFocus
        required
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="Ghi chú xử lý (bắt buộc)"
        aria-label="Ghi chú xử lý"
        rows={2}
        className="min-h-[60px] resize-y border border-input bg-background px-3 py-2 text-[13px] outline-none focus-visible:outline-2 focus-visible:outline-primary"
      />
      <div className="flex gap-2">
        <Button type="submit" disabled={busy || !note.trim()} className="h-9 px-3.5">
          Đã xử lý
        </Button>
        <Button type="button" variant="ghost" onClick={() => setResolving(false)} className="h-9 px-3.5">
          Hủy
        </Button>
      </div>
      {error && <span role="alert" className="text-[12px] text-risk-critical">{error}</span>}
    </form>
  );
}
