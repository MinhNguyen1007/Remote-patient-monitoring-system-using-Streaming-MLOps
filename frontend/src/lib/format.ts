/** Số thập phân kiểu Việt Nam (dấu phẩy), khớp tài liệu và báo cáo. */
export function vn(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return value.toFixed(digits).replace('.', ',');
}

export function vitalText(value: number | null | undefined, digits = 0): string {
  return value === null || value === undefined ? '—' : vn(value, digits);
}

export function bloodPressure(sbp: number | null, dbp: number | null): string {
  if (sbp === null && dbp === null) return '—';
  return `${sbp === null ? '—' : Math.round(sbp)}/${dbp === null ? '—' : Math.round(dbp)}`;
}

export function clock(iso: string | null | undefined): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export function dateTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
}

/** "5 giây trước", "3 phút trước" — tính theo đồng hồ thật, dữ liệu phát lại mỗi giờ dữ liệu vài giây. */
export function timeAgo(iso: string | null | undefined, now: number = Date.now()): string {
  if (!iso) return '—';
  const seconds = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  if (seconds < 60) return `${seconds} giây trước`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} phút trước`;
  return `${Math.round(minutes / 60)} giờ trước`;
}

export function initials(name: string): string {
  return name
    .replace(/\./g, '')
    .split(/\s+/)
    .filter(Boolean)
    .slice(-2)
    .map((word) => word[0])
    .join('')
    .toUpperCase();
}
