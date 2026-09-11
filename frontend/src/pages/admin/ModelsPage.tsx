import { CircleCheck, RefreshCw, X } from 'lucide-react';
import { useEffect, useState } from 'react';

import { api } from '@/api/client';
import { DriftChart } from '@/components/charts/DriftChart';
import { PageHeader, StateMessage } from '@/components/layout';
import { Button } from '@/components/ui/button';
import { useAsync } from '@/hooks/useAsync';
import { dateTime, vn } from '@/lib/format';
import type { ModelVersion, RetrainStatus } from '@/types/api';

import { AdminTabs } from './AdminTabs';

const TERMINAL = new Set(['success', 'failed']);
const POLL_MS = 3000;

const MODEL_INFO: Record<string, { title: string; family: string; metrics: [string, string, string?][] }> = {
  risk_classifier: {
    title: 'Dự báo rủi ro 4 giờ tới',
    family: 'Random Forest',
    metrics: [
      ['MACRO F1', 'test_macro_f1', 'persistence_test_macro_f1'],
      ['RECALL CRITICAL', 'test_recall_critical', 'persistence_test_recall_critical'],
      ['AUROC', 'test_auroc_ovr'],
    ],
  },
  anomaly_detector: {
    title: 'Phát hiện bất thường',
    family: 'LSTM-Autoencoder',
    metrics: [['AUROC', 'test_auroc'], ['PRECISION', 'test_precision'], ['GẮN CỜ NHẦM', 'test_false_positive_rate']],
  },
};

function ChampionTag() {
  return <span className="mono bg-primary px-2 py-0.5 text-[11px] font-semibold tracking-[1px] text-primary-foreground">CHAMPION</span>;
}

function ChampionCard({ version, tau }: { version: ModelVersion | undefined; tau: string }) {
  if (!version) return null;
  const info = MODEL_INFO[version.model_name];
  const metrics = version.metrics ?? {};
  return (
    <div className="card flex flex-col gap-4 p-5">
      <div className="flex items-center justify-between gap-3">
        <div className="flex flex-col gap-0.5">
          <h2 className="block-title">{info?.title ?? version.model_name}</h2>
          <span className="mono text-[12px] text-muted-foreground">{version.model_name} v{version.mlflow_version} · {info?.family} · τ {tau}</span>
        </div>
        <ChampionTag />
      </div>
      <div className="grid grid-cols-3 gap-3">
        {(info?.metrics ?? []).map(([label, key, reference]) => {
          const value = metrics[key];
          const percent = key.endsWith('false_positive_rate');
          return (
            <div key={key} className="flex flex-col gap-0.5">
              <span className="mono text-[10.5px] tracking-[1.2px] text-muted-foreground">{label}</span>
              <span className="mono text-[22px] font-semibold tracking-[-0.5px]">{value === undefined ? '—' : percent ? `${vn(value * 100, 1)}%` : vn(value, 3)}</span>
              {reference && metrics[reference] !== undefined && <span className="mono text-[11.5px] text-muted-foreground">persistence {vn(metrics[reference], 3)}</span>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** Kích hoạt retrain (UC10): nhận dag_run_id rồi hỏi trạng thái định kỳ, không giữ request chờ DAG. */
function RetrainControl() {
  const [run, setRun] = useState<RetrainStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!run || TERMINAL.has(run.state)) return;
    const timer = setTimeout(() => {
      api.retrainStatus(run.dag_run_id).then(setRun).catch((err) => setError(err instanceof Error ? err.message : String(err)));
    }, POLL_MS);
    return () => clearTimeout(timer);
  }, [run]);

  const trigger = async () => {
    setBusy(true);
    setError(null);
    try {
      setRun(await api.triggerRetrain());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không kích hoạt được');
    } finally {
      setBusy(false);
    }
  };

  const running = run !== null && !TERMINAL.has(run.state);
  return (
    <div className="flex flex-wrap items-center gap-3">
      {run && (
        <div className="flex items-center gap-3 border border-border bg-card px-3.5 py-2.5" role="status" aria-live="polite">
          {running ? <RefreshCw size={16} color="var(--primary)" className="motion-safe:animate-spin" /> : run.state === 'success' ? <CircleCheck size={16} color="var(--risk-normal)" /> : <X size={16} color="var(--risk-critical)" />}
          <div className="flex flex-col leading-tight">
            <span className="text-[13px] font-semibold">{running ? 'Đang huấn luyện lại…' : run.state === 'success' ? 'Huấn luyện lại xong' : 'Huấn luyện lại thất bại'}</span>
            <span className="mono text-[11.5px] text-muted-foreground">{run.dag_run_id} · {run.state}</span>
          </div>
        </div>
      )}
      <Button onClick={trigger} disabled={busy || running} className="h-9 px-3.5">
        <RefreshCw strokeWidth={2.2} />
        Kích hoạt huấn luyện lại
      </Button>
      {error && <span role="alert" className="basis-full text-right text-[12.5px] text-risk-critical">{error}</span>}
    </div>
  );
}

/** UC09, UC10 — champion hiện tại, drift theo thời gian, lịch sử version kèm kết quả quality gate. */
export function ModelsPage() {
  const models = useAsync((signal) => api.models(signal), []);
  const drift = useAsync((signal) => api.driftReports(signal), []);
  const settings = useAsync((signal) => api.alertSettings(signal), []);

  const versions = models.data ?? [];
  const champion = (name: string) => versions.find((v) => v.model_name === name && v.is_champion);

  return (
    <>
      <PageHeader eyebrow="Quản trị hệ thống · UC09 · UC10" title="Giám sát mô hình" actions={<RetrainControl />} />
      <AdminTabs />
      {models.error ? (
        <StateMessage tone="error">{models.error.message}</StateMessage>
      ) : (
        <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <ChampionCard version={champion('risk_classifier')} tau={vn(settings.data?.champion_tau_critical)} />
          <ChampionCard version={champion('anomaly_detector')} tau={vn(settings.data?.anomaly_threshold)} />
        </section>
      )}
      <section className="card flex flex-col gap-3 p-5">
        <div className="flex flex-col gap-0.5">
          <h2 className="block-title">Drift dữ liệu</h2>
          <span className="text-[12.5px] text-muted-foreground">Max PSI của 7 đặc trưng mỗi lần kiểm tra (24 giờ dữ liệu gần nhất) so với phân phối huấn luyện của champion</span>
        </div>
        {drift.error ? <StateMessage tone="error">{drift.error.message}</StateMessage> : <DriftChart reports={drift.data ?? []} />}
      </section>
      <section className="card overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr>
              <th className="th">Mô hình</th>
              <th className="th">Version</th>
              <th className="th">Quality gate</th>
              <th className="th">Kích hoạt</th>
              <th className="th">Metric trên test</th>
              <th className="th">Huấn luyện</th>
              <th className="th" />
            </tr>
          </thead>
          <tbody>
            {versions.map((v) => {
              const m = v.metrics ?? {};
              const summary = v.model_name === 'risk_classifier'
                ? `Macro F1 ${vn(m.test_macro_f1, 3)} · Recall ${vn(m.test_recall_critical, 3)}`
                : `AUROC ${vn(m.test_auroc, 3)}`;
              return (
                <tr key={v.id}>
                  <td className="td mono text-[13px]">{v.model_name}</td>
                  <td className="td mono font-semibold">v{v.mlflow_version}</td>
                  <td className="td">
                    <span className="inline-flex items-center gap-1.5 font-semibold">
                      {v.gate_status === 'PROMOTED' ? <CircleCheck size={15} color="var(--risk-normal)" /> : <X size={15} color="var(--risk-critical)" />}
                      {v.gate_status === 'PROMOTED' ? 'Promoted' : 'Từ chối'}
                    </span>
                  </td>
                  <td className="td"><span className="inline-flex h-[22px] items-center border border-border bg-secondary px-2 text-[11.5px] font-semibold">{v.trigger}</span></td>
                  <td className="td mono text-[12.5px] whitespace-nowrap">{summary}</td>
                  <td className="td mono text-[12.5px] text-muted-foreground">{dateTime(v.trained_at)}</td>
                  <td className="td">{v.is_champion && <ChampionTag />}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {!versions.length && <div className="p-6 text-center text-muted-foreground">Chưa có version nào được ghi nhận.</div>}
      </section>
    </>
  );
}
