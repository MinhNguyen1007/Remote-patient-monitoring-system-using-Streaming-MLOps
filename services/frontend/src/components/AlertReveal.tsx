import { Activity, Cpu, OctagonAlert, X } from 'lucide-react';
import { useEffect, useState, type CSSProperties } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { api } from '@/api/client';
import { useAuth } from '@/context/AuthContext';
import { useServerEvents } from '@/context/WebSocketContext';
import type { AlertSound } from '@/hooks/useAlertSound';
import { enqueue, MAX_TOASTS, patientName, revealFor, soundTier, TOAST_MS, toastContent, type RevealItem } from '@/lib/alertReveal';
import { WinnerOverlay } from '@/truanayangi-ui/react/WinnerOverlay';

const TOAST_COLOR: Record<RevealItem['kind'], string> = {
  risk: 'var(--risk-critical)',
  anomaly: 'var(--anomaly-flag)',
  drift: 'var(--risk-warning)',
  retrain: 'var(--series)',
};

/**
 * Cảnh báo mới (02_8 mục 2.8.2d), theo mẫu "reveal" của truanayangi-ui:
 * - rủi ro nguy kịch → overlay toàn màn hình kiểu "NEW ITEM" (Esc hoặc "Để sau" để đóng, nhiều cảnh báo thì xếp hàng);
 * - bất thường, drift, huấn luyện lại xong → toast góc dưới, tự ẩn sau 20 giây.
 * Không có yếu tố ngẫu nhiên: nội dung là đúng dữ liệu của sự kiện.
 */
export function AlertReveal({ sound }: { sound: AlertSound }) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [overlays, setOverlays] = useState<RevealItem[]>([]);
  const [toasts, setToasts] = useState<RevealItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useServerEvents((event) => {
    if (!user) return;
    const item = revealFor(event, user.role);
    if (!item) return;
    sound.play(soundTier(item));
    if (item.kind === 'risk') setOverlays((queue) => enqueue(queue, item));
    else setToasts((queue) => enqueue(queue, item, MAX_TOASTS));
  });

  // Overlay là modal: toast nằm dưới lớp nền mờ của nó. Dừng đồng hồ tự ẩn cho tới khi xử lý xong các cảnh báo
  // nguy kịch, nếu không toast bất thường có thể biến mất mà người dùng chưa từng thấy.
  const overlayOpen = overlays.length > 0;
  useEffect(() => {
    if (!toasts.length || overlayOpen) return;
    const timer = setTimeout(() => setToasts((queue) => queue.slice(1)), TOAST_MS);
    return () => clearTimeout(timer);
  }, [toasts, overlayOpen]);

  const current = overlays[0];
  const next = () => {
    setError(null);
    setOverlays((queue) => queue.slice(1));
  };

  const acknowledge = async (alertId: string) => {
    setBusy(true);
    setError(null);
    try {
      await api.acknowledge(alertId);
      next();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không xác nhận được');
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      {current?.kind === 'risk' && (
        <WinnerOverlay
          open
          onOpenChange={(open) => !open && next()}
          tier={3}
          color="var(--risk-critical)"
          label={
            <>
              CẢNH BÁO MỚI · RỦI RO NGUY KỊCH
              {overlays.length > 1 && <span className="alert-queue"> · còn {overlays.length - 1} cảnh báo chờ</span>}
            </>
          }
          title={patientName(current.alert.subject_id)}
          description={`Giờ dữ liệu thứ ${current.alert.hour_index} · NEWS2 hiện tại ${current.alert.news2_score ?? '—'}`}
          art={
            <div className="alert-art">
              <OctagonAlert aria-hidden size={64} strokeWidth={1.6} color="var(--risk-critical)" />
              <strong>
                {Math.round(current.alert.risk_score * 100)}
                <small>%</small>
              </strong>
              <span>xác suất nguy kịch trong 4 giờ tới (mô hình dự báo)</span>
            </div>
          }
          actions={
            <>
              {error && <span role="alert" className="mr-auto text-[13px] text-risk-critical">{error}</span>}
              {overlays.length > 1 && (
                <button type="button" className="tn-action tn-action--text" onClick={() => setOverlays([])}>
                  BỎ QUA TẤT CẢ ({overlays.length})
                </button>
              )}
              <button type="button" className="tn-action tn-action--text" onClick={next}>
                ĐỂ SAU
              </button>
              {user?.role === 'DOCTOR' && (
                <button type="button" className="tn-action tn-action--text" disabled={busy} onClick={() => acknowledge(current.alert.alert_id)}>
                  {busy ? 'ĐANG XÁC NHẬN…' : 'XÁC NHẬN'}
                </button>
              )}
              <button
                type="button"
                className="tn-action tn-action--primary"
                onClick={() => {
                  navigate(`/patients/${current.alert.patient_id}`);
                  next();
                }}
              >
                XEM BỆNH NHÂN
              </button>
            </>
          }
        />
      )}

      {toasts.length > 0 && (
        <div className="toast-stack" aria-live="polite">
          {toasts.map((item) => {
            const content = toastContent(item);
            const Icon = item.kind === 'anomaly' ? Activity : item.kind === 'risk' ? OctagonAlert : Cpu;
            return (
              <article key={item.key} className="toast" role="status" style={{ '--tn-rarity': TOAST_COLOR[item.kind] } as CSSProperties}>
                <Icon aria-hidden size={22} strokeWidth={1.8} color={TOAST_COLOR[item.kind]} />
                <div>
                  <h2>{content.title}</h2>
                  <p>{content.body}</p>
                  <Link to={content.href} onClick={() => setToasts((queue) => queue.filter((x) => x.key !== item.key))}>
                    {content.linkLabel}
                  </Link>
                </div>
                <button type="button" className="toast-close" aria-label="Đóng thông báo" onClick={() => setToasts((queue) => queue.filter((x) => x.key !== item.key))}>
                  <X size={16} />
                </button>
              </article>
            );
          })}
        </div>
      )}
    </>
  );
}
