// Màu biểu đồ (skill dataviz) trên nền panel CS:GO. Series + bất thường đã chạy validate_palette.js
// (--mode dark --surface #1b2731, 2026-09-30): "#3987e5,#199e70,#9085e9" qua cả 5 kiểm tra. Tâm trương đổi từ
// #86b6ef (trượt dải độ sáng + độ bão hoà) sang aqua #199e70 của bảng tham chiếu; vẫn giữ nét đứt + nhãn trực tiếp.
export const CHART = {
  surface: '#1b2731',
  ink: '#f3f3ef',
  muted: '#abb8c2',
  axis: '#8d99a3',
  grid: '#33414b',
  series: '#3987e5',
  series2: '#199e70',
  anomaly: '#9085e9',
  neutralBar: '#46525c',
  risk: { NORMAL: '#0ca30c', WARNING: '#fab219', CRITICAL: '#d03b3b' },
} as const;
