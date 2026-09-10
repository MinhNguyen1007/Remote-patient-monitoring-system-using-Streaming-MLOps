# CLAUDE.md — frontend/

React + Vite. Xem kiến trúc tổng thể ở `../CLAUDE.md` và thiết kế giao diện chi tiết ở `../docs/design/02_8_thiet_ke_giao_dien.md`.

## Design system (đã chốt, không tự đổi)

Nền tảng: skill `csgo-case-opening-design` (dark theme, token màu OKLCH, component polish, motion mượt) — **có chủ đích, đã xác nhận với người dùng dù không phải theme y tế truyền thống**. Tùy biến bắt buộc giữ:
- Bỏ cơ chế mở case/spin reel ngẫu nhiên.
- Thêm token màu ngữ nghĩa lâm sàng: `--risk-normal` (xanh), `--risk-warning` (vàng/cam), `--risk-critical` (đỏ), `--anomaly-flag` (tím/xanh dương, dùng riêng cho điểm bất thường trên chart, không trùng màu risk-level).
- Mức rủi ro luôn hiển thị **màu + nhãn chữ + icon**, không chỉ màu.
- Badge chính là **rủi ro dự báo 4 giờ tới** (model). Hiển thị kèm **NEWS2 hiện tại** (luật) — không gộp 2 khái niệm này làm một.

## Cấu trúc

```
src/
  api/          Client gọi FastAPI backend (REST + WebSocket)
  components/   UI components dùng chung (badge risk-level, chart, alert item...)
  context/      WebSocketContext (kết nối realtime), AuthContext
  hooks/        usePatients, useAlerts, useWebSocket...
  pages/        Login, Dashboard, PatientDetail, AlertsCenter, Admin
  types/        TypeScript types khớp với response schema backend
```

## Quy ước

- Mọi màn hình phải khớp danh sách ở `docs/design/02_8_thiet_ke_giao_dien.md` mục 2.8.2 — không tự thêm màn hình ngoài Use Case đã thiết kế (`docs/design/02_2_usecase.md`) mà không cập nhật tài liệu trước.
- Mọi biểu đồ (vitals chart, risk timeline, drift chart) phải tuân theo skill `dataviz` — load skill đó trước khi viết code chart, không tự chọn màu tùy tiện.
- Route/trang phải gate theo role (Admin/Bác sĩ/Điều dưỡng) đúng bảng phân quyền ở `docs/design/02_2_usecase.md`.
- Bác sĩ/Điều dưỡng chỉ thấy bệnh nhân được phân công (backend đã lọc; frontend không tự lọc thay backend). Trang Admin có tab Phân công (UC13).
- Thao tác retrain: gọi API nhận `dag_run_id`, rồi hỏi trạng thái định kỳ — không chờ một request dài.
- Mockup hình ảnh (khi được dựng bằng skill `design`) là tài liệu tham chiếu bắt buộc đọc trước khi code UI — không code UI trước khi có mockup nếu mockup đã được yêu cầu dựng.

## Lệnh

```bash
npm install
npm run dev
npm run build
npm run test   # nếu có cấu hình Vitest
```
