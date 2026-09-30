# CLAUDE.md — services/frontend/

React + Vite. Xem kiến trúc tổng thể ở `../../CLAUDE.md` và thiết kế giao diện chi tiết ở `../../docs/design/02_8_thiet_ke_giao_dien.md`.

## Design system (đã chốt, không tự đổi)

Nền tảng: **theme "CS:GO classic" của skill `truanayangi-ui`** (người dùng chọn 2026-09-30, thay cho design system `csgo-case-opening-design` kiểu lime trước đó) — **có chủ đích, dù không phải theme y tế truyền thống**. Giá trị gốc: `references/themes.md` của skill ("CS:GO classic (exact values)").
- Kit chép vào `src/truanayangi-ui/` (chỉ phần dùng: `core/{case-audio,sfx-synth,rarity}.ts`, `react/{use-case-audio.ts,WinnerOverlay.tsx}`, `styles/{core,theme-csgo}.css`); `data-tn-theme="csgo"` trên `<html>` (`index.html`).
- **CSS của kit import vào `layer(components)`** (`app/globals.css`). Để ngoài layer thì phần reset `:where(button){background:none}` của kit thắng mọi class Tailwind (utilities là layer) — lỗi đã gặp: nút mất nền, tiêu đề mất cỡ chữ.
- Lớp riêng của ứng dụng (`.app-*`, `.page-*`, `.card`, `.field`, `.segmented`, `.patient-card`, `.toast`, `.alert-art`) để ngoài layer trong `globals.css`; token ghi đè bằng `:root[data-tn-theme='csgo']` (0,2,0) để thắng `:is([data-tn-theme="csgo"])` của theme.
- Bỏ cơ chế mở hòm/spin reel ngẫu nhiên. Dùng lại màn "NEW ITEM" (`WinnerOverlay`) cho **cảnh báo rủi ro nguy kịch mới** và âm báo tổng hợp (`useCaseAudio({ mode: 'synth' })`, không dùng tệp âm thanh có bản quyền; chạy `node <skill>/scripts/check-licensed.mjs services/frontend` sau khi chép thêm gì từ kit).
- Không có ảnh nền nhà kho (không được dùng trong repo công khai): chỉ gradient dự phòng của theme.
- Font Arial (theme gốc), không tải web font.
- **Góc vuông** (người dùng yêu cầu 2026-09-11): `--radius: 0`, không bo góc thẻ/nút/badge/input/tooltip/hộp thoại. Ngoại lệ duy nhất: nút radio giữ hình tròn.
- Thêm token màu ngữ nghĩa lâm sàng: `--risk-normal` (xanh), `--risk-warning` (vàng/cam), `--risk-critical` (đỏ), `--anomaly-flag` (tím/xanh dương, dùng riêng cho điểm bất thường trên chart, không trùng màu risk-level).
- Mức rủi ro luôn hiển thị **màu + nhãn chữ + icon**, không chỉ màu.
- Badge chính là **rủi ro dự báo 4 giờ tới** (model). Hiển thị kèm **NEWS2 hiện tại** (luật) — không gộp 2 khái niệm này làm một.

## Cấu trúc (Vite 8 + React 19 + TypeScript 7 + Tailwind v4 + Base UI/CVA, từ template của skill)

```
src/
  app/          App.tsx (routes), routes.tsx (RequireAuth, RequireRole, homeFor), globals.css (token)
  api/          client.ts: request() + api.* (mọi endpoint), tokenStore, websocketUrl — gọi qua tiền tố /api
  context/      AuthContext (JWT trong localStorage, 401 → đăng xuất), WebSocketContext (1 kết nối, tự nối lại, useServerEvents)
  components/   clinical.tsx (RiskBadge, News2Chip, AnomalyChip, AlertStatusPill, AlertTypeLabel), layout.tsx (AppShell với
                header CS:GO, PageHeader, Segmented, RealtimeIndicator), PatientCard (thẻ CS:GO), AlertActions,
                AlertReveal (overlay nguy kịch + toast bất thường/drift/retrain), charts/ (VitalsChart, DriftChart, palette),
                ui/ (button, dialog, select, switch của template, đã đổi màu theo theme)
  hooks/        useAsync (tải + hủy + cập nhật tại chỗ từ sự kiện realtime), useAlertSound (âm báo, mở khoá ở thao tác đầu, nhớ tắt tiếng)
  lib/          format.ts (số dấu phẩy, thời gian), risk.ts (nhãn/màu/icon theo mức), realtime.ts (hàm thuần cập nhật từ sự kiện),
                alertReveal.ts (hàm thuần: sự kiện → overlay/toast, hàng đợi, mức âm), soundPref.ts (lưu lựa chọn tắt tiếng)
  truanayangi-ui/ phần kit đã chép (xem mục Design system)
  pages/        LoginPage, DashboardPage, PatientDetailPage, AlertsPage, admin/ (Users, Assignments, Thresholds, Models, fields.ts)
  types/api.ts  Kiểu khớp schema backend + sự kiện WebSocket
  test/         Vitest + Testing Library (31 test): badge, chip, thẻ bệnh nhân, thao tác cảnh báo, route theo vai trò, realtime,
                cảnh báo mới (overlay, xếp hàng, toast không tự ẩn khi overlay mở, âm báo + lưu lựa chọn)
Dockerfile, nginx.conf  Build → nginx; /api (kể cả WebSocket) proxy tới backend:8000
```

## Quy ước

- Mọi màn hình phải khớp danh sách ở `docs/design/02_8_thiet_ke_giao_dien.md` mục 2.8.2 — không tự thêm màn hình ngoài Use Case đã thiết kế (`docs/design/02_2_usecase.md`) mà không cập nhật tài liệu trước.
- Mọi biểu đồ (vitals chart, risk timeline, drift chart) phải tuân theo skill `dataviz` — load skill đó trước khi viết code chart, không tự chọn màu tùy tiện.
- Route/trang phải gate theo role (Admin/Bác sĩ/Điều dưỡng) đúng bảng phân quyền ở `docs/design/02_2_usecase.md`.
- Bác sĩ/Điều dưỡng chỉ thấy bệnh nhân được phân công (backend đã lọc; frontend không tự lọc thay backend). Trang Admin có tab Phân công (UC13).
- Thao tác retrain: gọi API nhận `dag_run_id`, rồi hỏi trạng thái định kỳ — không chờ một request dài.
- **Gọi backend qua tiền tố `/api`** (proxy Vite khi dev, nginx khi Docker) — không gọi thẳng `localhost:8000` (CORS 127.0.0.1 vs localhost).
- Realtime: mọi cập nhật từ sự kiện WebSocket viết thành **hàm thuần** trong `lib/realtime.ts` rồi test; component chỉ gọi `setData(...)`.
  - `latest` = vitals sau forward-fill (API và `vitals_filled`); biểu đồ dùng vitals đo gốc (`timeline`, `vitals`), giờ không đo để trống.
- Không tự tính NEWS2 hay đặc trưng ở frontend: điểm NEWS2 từng thông số lấy từ `GET /patients/{id}` (`news2_components`, backend tính bằng rpm_common).
- Nhãn và số tiếng Việt: số thập phân dấu phẩy (`vn()`), mọi chữ hiển thị bằng tiếng Việt.
- **Mockup** (https://claude.ai/code/artifact/06619c98-443f-4157-be37-cef16741dc5d, nguồn `../../docs/design/mockups/`) là của giao diện lime trước 2026-09-30: dùng cho **bố cục và cấu tạo component**; màu/chữ theo theme CS:GO ở `docs/design/02_8` mục 2.8.2.
- Kiểm tra trực quan: Chrome headless riêng (`--remote-debugging-port=9333 --user-data-dir=<scratchpad>`) + `node <skill truanayangi-ui>/scripts/shoot.mjs`; trang cần đăng nhập thì lấy JWT qua `POST /api/auth/login` bằng tài khoản demo rồi `--eval "localStorage.setItem('rpm.token', …)"` — không gõ mật khẩu vào trang.

## Lệnh

```bash
npm install
npm run dev        # http://127.0.0.1:5173, proxy /api → http://127.0.0.1:8000 (đổi bằng BACKEND_URL)
npm run typecheck
npm run test       # Vitest (jsdom)
npm run build
docker compose --profile app up -d frontend   # http://localhost:3000 (cần backend)
```
