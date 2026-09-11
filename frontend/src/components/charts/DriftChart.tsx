import { useEffect, useRef, useState } from 'react';

import { CHART } from '@/components/charts/palette';
import { clock, vn } from '@/lib/format';
import type { DriftReport } from '@/types/api';

const THRESHOLDS = [
  { value: 0.1, label: '0,10 · lệch trung bình', color: CHART.risk.WARNING },
  { value: 0.25, label: '0,25 · lệch đáng kể → retrain', color: CHART.risk.CRITICAL },
];

/** Max PSI mỗi lần kiểm tra drift (mục 2.9.4); điểm vượt 0,25 tô đỏ = đã tự động kích hoạt retrain. */
export function DriftChart({ reports }: { reports: DriftReport[] }) {
  const container = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(900);
  const [hover, setHover] = useState<number | null>(null);

  useEffect(() => {
    const element = container.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(480, Math.floor(entry.contentRect.width))));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const runs = [...reports].filter((r) => r.max_psi !== null).sort((a, b) => a.run_at.localeCompare(b.run_at));
  if (!runs.length) {
    return (
      <div ref={container} className="py-10 text-center text-[13px] text-muted-foreground">
        Chưa có lần kiểm tra drift nào. DAG <span className="mono">drift_check</span> ghi báo cáo vào đây sau mỗi lần chạy.
      </div>
    );
  }

  const left = 44;
  const top = 14;
  const height = 170;
  const plotW = width - left - 12;
  const yMax = Math.max(0.5, ...runs.map((r) => r.max_psi ?? 0)) * 1.05;
  const x = (i: number) => left + (runs.length > 1 ? (i * plotW) / (runs.length - 1) : plotW / 2);
  const y = (v: number) => top + ((yMax - v) / yMax) * height;
  const path = runs.map((r, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(r.max_psi ?? 0).toFixed(1)}`).join(' ');
  const tickEvery = Math.max(1, Math.ceil(runs.length / 6));
  const hovered = hover !== null ? runs[hover] : null;

  return (
    <div ref={container} className="relative w-full">
      <svg
        width={width}
        height={top + height + 30}
        role="img"
        aria-label={`Max PSI của ${runs.length} lần kiểm tra drift`}
        onMouseMove={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          const i = Math.round(((e.clientX - rect.left - left) / (plotW || 1)) * (runs.length - 1));
          setHover(Math.min(runs.length - 1, Math.max(0, i)));
        }}
        onMouseLeave={() => setHover(null)}
        className="block"
      >
        {[0, 0.1, 0.25, 0.5].map((tick) => (
          <text key={tick} x={left - 8} y={y(tick) + 4} fill={CHART.axis} fontFamily="var(--font-mono)" fontSize={10} textAnchor="end">{vn(tick)}</text>
        ))}
        <line x1={left} x2={left + plotW} y1={y(0)} y2={y(0)} stroke={CHART.grid} />
        {THRESHOLDS.map((t) => (
          <g key={t.value}>
            <line x1={left} x2={left + plotW} y1={y(t.value)} y2={y(t.value)} stroke={t.color} strokeOpacity={0.7} strokeDasharray="4 4" />
            <text x={left + 8} y={y(t.value) - 6} fill={CHART.muted} fontSize={11}>{t.label}</text>
          </g>
        ))}
        <path d={path} fill="none" stroke={CHART.series} strokeWidth={2} strokeLinejoin="round" />
        {runs.map((r, i) => {
          const high = (r.max_psi ?? 0) >= 0.25;
          return <circle key={r.id} cx={x(i)} cy={y(r.max_psi ?? 0)} r={high ? 5 : 3.5} fill={high ? CHART.risk.CRITICAL : CHART.series} stroke={CHART.surface} strokeWidth={2} />;
        })}
        {runs.map((r, i) =>
          i % tickEvery === 0 ? (
            <text key={r.id} x={x(i)} y={top + height + 18} fill={CHART.axis} fontFamily="var(--font-mono)" fontSize={10} textAnchor="middle">{clock(r.run_at).slice(0, 5)}</text>
          ) : null,
        )}
        {hover !== null && <line x1={x(hover)} x2={x(hover)} y1={top} y2={top + height} stroke={CHART.ink} strokeOpacity={0.4} />}
      </svg>
      {hovered && hover !== null && (
        <div className="pointer-events-none absolute top-4 flex w-[220px] flex-col gap-1 border border-border bg-popover px-3 py-2.5 text-[12.5px]" style={{ left: x(hover) > width / 2 ? x(hover) - 236 : x(hover) + 14 }}>
          <span className="mono text-[11px] text-muted-foreground">{clock(hovered.run_at)} · {hovered.n_records} bản ghi</span>
          <span>Max PSI <span className="mono font-semibold">{vn(hovered.max_psi, 3)}</span></span>
          <span className="text-muted-foreground">{hovered.drift_detected ? (hovered.triggered_retrain ? 'Drift đáng kể · đã kích hoạt retrain' : 'Drift đáng kể') : 'Không đáng kể'}</span>
        </div>
      )}
    </div>
  );
}
