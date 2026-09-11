import { useEffect, useState, type FormEvent, type ReactNode } from 'react';

import { api } from '@/api/client';
import { PageHeader, StateMessage } from '@/components/layout';
import { Button } from '@/components/ui/button';
import { useAsync } from '@/hooks/useAsync';
import { dateTime, vn } from '@/lib/format';

import { AdminTabs, fieldClass } from './AdminTabs';

function Field({ label, hint, children, last = false }: { label: string; hint: string; children: ReactNode; last?: boolean }) {
  return (
    <div className={`grid grid-cols-1 gap-6 py-5 md:grid-cols-[300px_minmax(0,1fr)] ${last ? '' : 'border-b border-border'}`}>
      <div className="flex flex-col gap-1">
        <span className="font-bold">{label}</span>
        <span className="text-[12.5px] text-pretty text-muted-foreground">{hint}</span>
      </div>
      {children}
    </div>
  );
}

const parse = (text: string) => Number(text.replace(',', '.'));

/** UC08 — mặc định dùng τ_critical của model champion; mỗi lần lưu là một bản ghi mới (có lịch sử). */
export function ThresholdsPage() {
  const settings = useAsync((signal) => api.alertSettings(signal), []);
  const [useChampion, setUseChampion] = useState(true);
  const [tauCritical, setTauCritical] = useState('0,30');
  const [tauAnomaly, setTauAnomaly] = useState('0,99');
  const [cooldown, setCooldown] = useState('4');
  const [message, setMessage] = useState<{ tone: 'ok' | 'error'; text: string } | null>(null);

  useEffect(() => {
    const s = settings.data;
    if (!s) return;
    setUseChampion(s.risk_critical_threshold === null);
    if (s.risk_critical_threshold !== null) setTauCritical(vn(s.risk_critical_threshold));
    setTauAnomaly(vn(s.anomaly_threshold));
    setCooldown(String(s.cooldown_hours));
  }, [settings.data]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setMessage(null);
    try {
      const saved = await api.saveAlertSettings({
        risk_critical_threshold: useChampion ? null : parse(tauCritical),
        anomaly_threshold: parse(tauAnomaly),
        cooldown_hours: Number(cooldown),
      });
      settings.setData(saved);
      setMessage({ tone: 'ok', text: 'Đã lưu. Stream consumer áp dụng ngưỡng mới trong vòng 30 giây.' });
    } catch (err) {
      setMessage({ tone: 'error', text: err instanceof Error ? err.message : 'Không lưu được' });
    }
  };

  const s = settings.data;
  const championTau = s?.champion_tau_critical;

  return (
    <form onSubmit={submit} className="contents">
      <PageHeader
        eyebrow="Quản trị hệ thống · UC08"
        title="Ngưỡng cảnh báo"
        actions={
          <>
            <Button type="button" variant="outline" onClick={() => settings.reload()} className="h-9 px-3.5">Hủy</Button>
            <Button type="submit" disabled={!s} className="h-9 px-3.5">Lưu thay đổi</Button>
          </>
        }
      />
      <AdminTabs />
      {settings.error && <StateMessage tone="error">{settings.error.message}</StateMessage>}
      {message && <StateMessage tone={message.tone === 'error' ? 'error' : 'muted'}>{message.text}</StateMessage>}
      <section className="card px-6 py-1">
        <Field label="Ngưỡng rủi ro nguy kịch (τ_critical)" hint="Bệnh nhân được gắn mức Nguy kịch và tạo cảnh báo khi xác suất nguy kịch trong 4 giờ tới ≥ ngưỡng.">
          <fieldset className="m-0 flex flex-col gap-2.5 border-0 p-0">
            <legend className="sr-only">Chọn cách đặt ngưỡng rủi ro</legend>
            <label className={`flex cursor-pointer items-center gap-3 border px-3.5 py-3 ${useChampion ? 'border-primary bg-primary/5' : 'border-border'}`}>
              <input type="radio" name="tau-mode" checked={useChampion} onChange={() => setUseChampion(true)} className="size-4 accent-[var(--primary)]" />
              <span className="font-semibold">Dùng ngưỡng khuyến nghị của model champion</span>
              <span className="mono ml-auto font-semibold">{championTau != null ? vn(championTau) : 'không đọc được'}</span>
            </label>
            <label className={`flex cursor-pointer flex-wrap items-center gap-3 border px-3.5 py-3 ${!useChampion ? 'border-primary bg-primary/5' : 'border-border'}`}>
              <input type="radio" name="tau-mode" checked={!useChampion} onChange={() => setUseChampion(false)} className="size-4 accent-[var(--primary)]" />
              <span>Tự đặt ngưỡng</span>
              <input
                aria-label="Ngưỡng τ_critical tự đặt (0–1)"
                disabled={useChampion}
                inputMode="decimal"
                value={tauCritical}
                onChange={(e) => setTauCritical(e.target.value)}
                className={`${fieldClass} mono ml-auto h-8 w-[110px] disabled:opacity-50`}
              />
            </label>
          </fieldset>
        </Field>
        <Field label="Ngưỡng bất thường (τ_anomaly)" hint="Cảnh báo bất thường khi điểm bất thường ≥ ngưỡng (0–1).">
          <div className="flex flex-wrap items-center gap-3">
            <input aria-label="Ngưỡng τ_anomaly" inputMode="decimal" value={tauAnomaly} onChange={(e) => setTauAnomaly(e.target.value)} className={`${fieldClass} mono w-[140px]`} />
            <span className="text-[12.5px] text-muted-foreground">0,99 ≈ 1% cửa sổ bình thường bị gắn cờ nhầm</span>
          </div>
        </Field>
        <Field last label="Thời gian chờ giữa 2 cảnh báo" hint="Cùng bệnh nhân, cùng loại: không tạo cảnh báo mới khi còn cảnh báo đang mở hoặc chưa hết thời gian chờ.">
          <div className="flex flex-wrap items-center gap-3">
            <span className={`${fieldClass} flex w-[140px] items-center`}>
              <input aria-label="Thời gian chờ (giờ dữ liệu)" type="number" min={0} max={72} value={cooldown} onChange={(e) => setCooldown(e.target.value)} className="mono w-full bg-transparent outline-none" />
              <span className="text-muted-foreground">giờ</span>
            </span>
            <span className="text-[12.5px] text-muted-foreground">tính theo giờ dữ liệu, không phải giờ đồng hồ</span>
          </div>
        </Field>
      </section>
      <section className="card flex flex-col gap-2.5 px-6 py-[18px]">
        <span className="eyebrow">Bản ghi hiện hành</span>
        <div className="flex flex-wrap gap-4 text-[13px]">
          <span className="mono text-muted-foreground">{s?.updated_at ? dateTime(s.updated_at) : 'chưa lưu lần nào'}</span>
          <span>{s?.updated_by ? 'Quản trị viên cập nhật' : 'Hệ thống (giá trị mặc định)'}</span>
          <span className="mono ml-auto text-muted-foreground">
            hiệu lực: τ_critical {vn(s?.effective_risk_threshold)} · τ_anomaly {vn(s?.anomaly_threshold)} · {s?.cooldown_hours ?? '—'} giờ
          </span>
        </div>
      </section>
    </form>
  );
}
