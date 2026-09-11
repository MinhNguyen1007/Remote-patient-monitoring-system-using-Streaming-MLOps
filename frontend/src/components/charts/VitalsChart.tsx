import { useEffect, useRef, useState, type KeyboardEvent, type MouseEvent } from 'react';

import { RiskBadge } from '@/components/clinical';
import { CHART } from '@/components/charts/palette';
import { clock, vn } from '@/lib/format';
import { RISK_META } from '@/lib/risk';
import type { TimelinePoint, Vital } from '@/types/api';

interface Strip {
  name: string;
  unit: string;
  lines: { key: Vital; color: string; dash?: string; label?: string }[];
  domain: [number, number];
  /** Khoảng 0 điểm NEWS2 của thông số (vùng xám) */
  band?: [number, number];
  digits: number;
  sparse?: boolean;
}

// 5 dải xếp chồng dùng chung trục thời gian — mỗi thông số một đơn vị nên không dùng 2 trục y (skill dataviz)
const STRIPS: Strip[] = [
  { name: 'Nhịp tim', unit: 'bpm', lines: [{ key: 'heart_rate', color: CHART.series }], domain: [60, 140], band: [51, 90], digits: 0 },
  { name: 'SpO₂', unit: '%', lines: [{ key: 'spo2', color: CHART.series }], domain: [86, 100], band: [96, 100], digits: 0 },
  { name: 'Nhịp thở', unit: '/phút', lines: [{ key: 'respiratory_rate', color: CHART.series }], domain: [10, 32], band: [12, 20], digits: 0 },
  {
    name: 'Huyết áp',
    unit: 'mmHg',
    lines: [
      { key: 'systolic_bp', color: CHART.series, label: 'Tâm thu' },
      { key: 'diastolic_bp', color: CHART.series2, dash: '5 4', label: 'Tâm trương' },
    ],
    domain: [40, 160],
    band: [111, 219],
    digits: 0,
  },
  { name: 'Nhiệt độ', unit: '°C', lines: [{ key: 'temperature', color: CHART.series }], domain: [35.5, 39.5], band: [36.1, 38.0], digits: 1, sparse: true },
];

const LEFT = 132;
const RIGHT = 84;
const STRIP_H = 64;
const GAP = 16;
const LANE_H = 44;
const BAND_H = 18;

function lastMeasured(points: TimelinePoint[], key: Vital): number | null {
  for (let i = points.length - 1; i >= 0; i -= 1) if (points[i][key] !== null) return points[i][key];
  return null;
}

/** Chuỗi path có ngắt quãng ở giờ không đo; dữ liệu thưa (nhiệt độ) thì nối các điểm đo. */
function linePath(points: TimelinePoint[], key: Vital, x: (i: number) => number, y: (v: number) => number, sparse: boolean): string {
  let d = '';
  let pen = false;
  points.forEach((p, i) => {
    const v = p[key];
    if (v === null) {
      pen = pen && sparse;
      return;
    }
    d += `${pen ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)} `;
    pen = true;
  });
  return d.trim();
}

export function VitalsChart({ points, tauAnomaly }: { points: TimelinePoint[]; tauAnomaly: number }) {
  const container = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(1000);
  const [hover, setHover] = useState<number | null>(null);

  useEffect(() => {
    const element = container.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(560, Math.floor(entry.contentRect.width))));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const n = points.length;
  const plotW = width - LEFT - RIGHT;
  const step = n > 1 ? plotW / (n - 1) : plotW;
  const x = (i: number) => LEFT + (n > 1 ? i * step : plotW / 2);
  const stripsTop = 8;
  const laneTop = stripsTop + STRIPS.length * (STRIP_H + GAP) + 6;
  const bandTop = laneTop + LANE_H + 18;
  const axisTop = bandTop + BAND_H + 12;
  const height = axisTop + 34;
  const tickEvery = Math.max(1, Math.ceil(n / 9));

  const pick = (clientX: number, rect: DOMRect) => {
    if (!n) return;
    const index = Math.round((clientX - rect.left - LEFT) / (step || 1));
    setHover(Math.min(n - 1, Math.max(0, index)));
  };
  const onMove = (event: MouseEvent<SVGSVGElement>) => pick(event.clientX, event.currentTarget.getBoundingClientRect());
  const onKey = (event: KeyboardEvent<SVGSVGElement>) => {
    if (!n) return;
    if (event.key === 'ArrowLeft') setHover((h) => Math.max(0, (h ?? n) - 1));
    else if (event.key === 'ArrowRight') setHover((h) => Math.min(n - 1, (h ?? -1) + 1));
    else if (event.key === 'Escape') setHover(null);
    else return;
    event.preventDefault();
  };

  const hovered = hover !== null ? points[hover] : null;

  return (
    <div ref={container} className="relative w-full">
      {n === 0 ? (
        <div className="py-16 text-center text-muted-foreground">Chưa có dữ liệu vitals.</div>
      ) : (
        <svg
          width={width}
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label={`Biểu đồ vitals ${n} giờ dữ liệu gần nhất. Dùng phím mũi tên để xem từng giờ.`}
          tabIndex={0}
          onMouseMove={onMove}
          onMouseLeave={() => setHover(null)}
          onKeyDown={onKey}
          onBlur={() => setHover(null)}
          className="block outline-none focus-visible:outline-2 focus-visible:outline-primary"
          style={{ fontFamily: 'var(--font-sans)' }}
        >
          {STRIPS.map((strip, s) => {
            const top = stripsTop + s * (STRIP_H + GAP);
            const values = strip.lines.flatMap((line) => points.map((p) => p[line.key]).filter((v): v is number => v !== null));
            const lo = Math.min(strip.domain[0], ...values);
            const hi = Math.max(strip.domain[1], ...values);
            const y = (v: number) => top + ((hi - v) / (hi - lo || 1)) * STRIP_H;
            const current = strip.lines[0].key === 'systolic_bp'
              ? `${vn(lastMeasured(points, 'systolic_bp'), 0)}/${vn(lastMeasured(points, 'diastolic_bp'), 0)}`
              : vn(lastMeasured(points, strip.lines[0].key), strip.digits);
            return (
              <g key={strip.name}>
                {strip.band && (
                  <rect x={LEFT} width={plotW} y={y(Math.min(strip.band[1], hi))} height={Math.max(0, y(Math.max(strip.band[0], lo)) - y(Math.min(strip.band[1], hi)))} fill="#ffffff" fillOpacity={0.045} />
                )}
                <line x1={LEFT} x2={LEFT + plotW} y1={top + STRIP_H} y2={top + STRIP_H} stroke={CHART.grid} />
                {points.map((p, i) =>
                  p.is_anomaly ? <line key={i} x1={x(i)} x2={x(i)} y1={top} y2={top + STRIP_H} stroke={CHART.anomaly} strokeOpacity={0.35} strokeWidth={1.5} /> : null,
                )}
                <text x={0} y={top + 14} fill={CHART.muted} fontFamily="var(--font-mono)" fontSize={11} letterSpacing={1}>{strip.name.toUpperCase()}</text>
                <text x={0} y={top + 38} fill={CHART.ink} fontFamily="var(--font-mono)" fontSize={20} fontWeight={600}>{current}</text>
                <text x={0} y={top + 54} fill={CHART.muted} fontFamily="var(--font-mono)" fontSize={11}>{strip.unit}</text>
                {[lo, hi].map((tick) => (
                  <text key={tick} x={LEFT - 8} y={y(tick) + 4} fill={CHART.axis} fontFamily="var(--font-mono)" fontSize={10} textAnchor="end">{vn(tick, strip.digits)}</text>
                ))}
                {strip.lines.map((line) => (
                  <g key={line.key}>
                    <path d={linePath(points, line.key, x, y, !!strip.sparse)} fill="none" stroke={line.color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" strokeDasharray={line.dash} />
                    {strip.sparse && points.map((p, i) => (p[line.key] !== null ? <circle key={i} cx={x(i)} cy={y(p[line.key] as number)} r={3.5} fill={line.color} stroke={CHART.surface} strokeWidth={2} /> : null))}
                    {line.label && lastMeasured(points, line.key) !== null && (
                      <text x={LEFT + plotW + 8} y={y(lastMeasured(points, line.key) as number) + 4} fill={CHART.muted} fontSize={11}>{line.label}</text>
                    )}
                  </g>
                ))}
              </g>
            );
          })}

          {/* Làn điểm bất thường 0–1, đường ngưỡng τ_anomaly */}
          <text x={0} y={laneTop + 14} fill={CHART.muted} fontFamily="var(--font-mono)" fontSize={11} letterSpacing={1}>BẤT THƯỜNG</text>
          <text x={0} y={laneTop + 36} fill={CHART.ink} fontFamily="var(--font-mono)" fontSize={18} fontWeight={600}>{vn(points[n - 1].anomaly_score, 3)}</text>
          {points.map((p, i) =>
            p.anomaly_score === null ? null : (
              <rect key={i} x={x(i) - Math.max(1, step - 3) / 2} width={Math.max(1, step - 3)} y={laneTop + LANE_H - p.anomaly_score * LANE_H} height={p.anomaly_score * LANE_H} fill={p.is_anomaly ? CHART.anomaly : CHART.neutralBar} />
            ),
          )}
          <line x1={LEFT} x2={LEFT + plotW} y1={laneTop + LANE_H - tauAnomaly * LANE_H} y2={laneTop + LANE_H - tauAnomaly * LANE_H} stroke={CHART.anomaly} strokeDasharray="3 3" />
          <text x={LEFT + plotW + 8} y={laneTop + LANE_H - tauAnomaly * LANE_H + 4} fill={CHART.muted} fontSize={11}>τ {vn(tauAnomaly, 2)}</text>

          {/* Rủi ro dự báo mỗi giờ */}
          <text x={0} y={bandTop + 13} fill={CHART.muted} fontFamily="var(--font-mono)" fontSize={11} letterSpacing={1}>RỦI RO 4 GIỜ TỚI</text>
          {points.map((p, i) => (
            <rect key={i} x={x(i) - step / 2 + 1} width={Math.max(1, step - 2)} y={bandTop} height={BAND_H} fill={CHART.risk[p.risk_level]} fillOpacity={0.8}>
              <title>{`Giờ ${p.hour_index}: ${RISK_META[p.risk_level].label}`}</title>
            </rect>
          ))}

          {points.map((p, i) =>
            i % tickEvery === 0 || i === n - 1 ? (
              <text key={i} x={x(i)} y={axisTop + 8} fill={CHART.axis} fontFamily="var(--font-mono)" fontSize={10.5} textAnchor="middle">{p.hour_index}</text>
            ) : null,
          )}
          <text x={LEFT + plotW} y={axisTop + 26} fill={CHART.muted} fontSize={11} textAnchor="end">giờ dữ liệu kể từ khi vào ICU</text>

          {hover !== null && <line x1={x(hover)} x2={x(hover)} y1={4} y2={axisTop - 6} stroke={CHART.ink} strokeOpacity={0.55} />}
        </svg>
      )}
      {hovered && hover !== null && (
        <div
          className="pointer-events-none absolute top-9 flex w-[220px] flex-col gap-1.5 border border-border bg-popover px-3.5 py-3 text-[12.5px] shadow-[0_12px_32px_rgba(0,0,0,.45)]"
          style={{ left: x(hover) > width / 2 ? x(hover) - 236 : x(hover) + 16 }}
          role="status"
        >
          <span className="mono text-[11px] text-muted-foreground">GIỜ {hovered.hour_index} · {clock(hovered.recorded_at)}</span>
          <TooltipRow label="Nhịp tim" value={hovered.heart_rate} unit="bpm" />
          <TooltipRow label="SpO₂" value={hovered.spo2} unit="%" />
          <TooltipRow label="Nhịp thở" value={hovered.respiratory_rate} unit="/phút" />
          <div className="flex justify-between gap-4">
            <span className="text-muted-foreground">Huyết áp</span>
            <span className="mono font-semibold">{vn(hovered.systolic_bp, 0)}/{vn(hovered.diastolic_bp, 0)}</span>
          </div>
          <TooltipRow label="Nhiệt độ" value={hovered.temperature} unit="°C" digits={1} />
          <div className="my-0.5 h-px bg-border" />
          <RiskBadge level={hovered.risk_level} score={hovered.risk_score} />
          <div className="flex justify-between gap-4">
            <span className="text-muted-foreground">NEWS2</span>
            <span className="mono font-semibold">{hovered.news2_score ?? '—'}</span>
          </div>
          <div className="flex justify-between gap-4">
            <span className="text-muted-foreground">Bất thường</span>
            <span className="mono font-semibold">{vn(hovered.anomaly_score, 3)}</span>
          </div>
        </div>
      )}
    </div>
  );
}

function TooltipRow({ label, value, unit, digits = 0 }: { label: string; value: number | null; unit: string; digits?: number }) {
  return (
    <div className="flex justify-between gap-4">
      <span className="text-muted-foreground">{label}</span>
      <span className="mono font-semibold">{value === null ? 'không đo' : `${vn(value, digits)} ${unit}`}</span>
    </div>
  );
}
