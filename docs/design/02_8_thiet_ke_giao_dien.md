# 2.8. Thiết kế giao diện

## 2.8.1. Định hướng thiết kế

Giao diện áp dụng design system nền tảng dark-theme lấy cảm hứng từ giao diện mở hộp CS:GO (`csgo-case-opening-design`): nền tối, token màu OKLCH, component polish chuẩn SaaS, chuyển động mượt dựa trên `requestAnimationFrame`. Đây là lựa chọn thẩm mỹ có chủ đích nhằm tạo phong cách khác biệt cho dashboard, được tùy biến thêm lớp màu ngữ nghĩa lâm sàng để đảm bảo vẫn đọc được mức độ nguy hiểm ngay từ giao diện:

| Token | Giá trị/Ý nghĩa |
|---|---|
| `--bg-base` | Nền tối chủ đạo (kế thừa từ design system CS:GO) |
| `--accent-neon` | Màu nhấn chính (giữ nguyên tinh thần neon của theme gốc), dùng cho nút hành động chính, trạng thái active |
| `--risk-normal` | Xanh lá — bệnh nhân ổn định |
| `--risk-warning` | Vàng/cam — cần theo dõi sát |
| `--risk-critical` | Đỏ — nguy kịch, có hiệu ứng nhấp nháy nhẹ khi có alert mới |
| `--anomaly-flag` | Màu phụ (tím/xanh dương) đánh dấu điểm bất thường trên biểu đồ, tách biệt khỏi màu risk-level |

Bỏ hoàn toàn cơ chế "mở case"/spin reel ngẫu nhiên của theme gốc — chỉ giữ lại chất lượng polish, token màu, và motion cho các thao tác có ý nghĩa thật (cập nhật realtime, chuyển trạng thái alert).

Mức rủi ro **không chỉ được thể hiện bằng màu**: mọi badge luôn kèm nhãn chữ (`Bình thường` / `Cảnh báo` / `Nguy kịch`) và icon riêng, để người mù màu đỏ–xanh vẫn đọc được.

## 2.8.2. Danh sách màn hình chính (ánh xạ theo Use Case ở mục 2.2)

### Màn hình Đăng nhập (UC01)
- Form email/mật khẩu giữa màn hình trên nền dark theme, logo hệ thống, nút "Đăng nhập" dùng accent-neon.
- Thông báo lỗi hiển thị dạng toast góc trên khi sai thông tin.

### Dashboard danh sách bệnh nhân (UC04) — Bác sĩ, Điều dưỡng
- Layout: sidebar điều hướng trái (Dashboard, Cảnh báo, Quản trị — hiện theo role) + khu vực chính dạng bảng/thẻ.
- Chỉ hiển thị **bệnh nhân được phân công** cho người đang đăng nhập.
- Mỗi bệnh nhân là 1 dòng/thẻ:
  - tên hiển thị, mã bệnh nhân;
  - badge **rủi ro dự báo 4 giờ tới**, cập nhật qua WebSocket, có transition khi đổi mức;
  - điểm **NEWS2 hiện tại**;
  - vitals mới nhất rút gọn (HR, SpO2);
  - thời gian cập nhật cuối.
- Thanh lọc theo mức rủi ro (tất cả/warning/critical), sắp xếp theo rủi ro cao nhất lên đầu.
- Badge số lượng cảnh báo đang mở trên sidebar mục "Cảnh báo".

### Chi tiết bệnh nhân (UC05, UC06, UC07)
- Header: thông tin bệnh nhân, badge lớn **rủi ro dự báo 4 giờ tới** kèm xác suất nguy kịch (`risk_score`), điểm **NEWS2 hiện tại**.
- Biểu đồ vitals theo thời gian thực: line chart 5 loại chỉ số (huyết áp vẽ 2 đường tâm thu/tâm trương), có thể chọn hiển thị từng chỉ số. Điểm bất thường được đánh dấu bằng `--anomaly-flag` (theo skill `dataviz`). 16 giờ đầu chưa có điểm bất thường: baseline cần 6 giờ, cộng thêm cửa sổ 12 giờ (mục 2.9.3).
- Biểu đồ risk-timeline: dải màu theo thời gian thể hiện risk_level đổi qua các mốc.
- Danh sách lịch sử cảnh báo của bệnh nhân. Mỗi cảnh báo có 2 thao tác (chỉ Bác sĩ):
  - **"Xác nhận"**: `OPEN → ACKNOWLEDGED`;
  - **"Đã xử lý"**: `→ RESOLVED`, kèm ghi chú xử lý.

### Panel/Trung tâm cảnh báo (UC06, UC07)
- Danh sách cảnh báo của **các bệnh nhân được phân công**, realtime, có filter theo trạng thái (Mở/Đã xác nhận/Đã xử lý) và theo loại (Risk/Anomaly).
- Cảnh báo mới xuất hiện có hiệu ứng nhấn mạnh tạm thời (motion, không phải nhấp nháy liên tục gây khó chịu).
- Email cảnh báo (UC11) không có màn hình riêng. Nội dung email có đường dẫn mở thẳng trang chi tiết bệnh nhân.

### Trang quản trị (UC03, UC08, UC09, UC10, UC13) — chỉ Admin
- Tab **Người dùng** (UC03): CRUD tài khoản, gán role, khóa/mở tài khoản.
- Tab **Phân công** (UC13): chọn bệnh nhân → gán/bỏ gán bác sĩ và điều dưỡng phụ trách (nhiều người cho 1 bệnh nhân).
- Tab **Cấu hình ngưỡng** (UC08) — xem mục 2.9.6:
  - `τ_critical`: để trống = dùng ngưỡng khuyến nghị của model champion;
  - `τ_anomaly`;
  - thời gian cooldown cảnh báo.
- Tab **Giám sát mô hình** (UC09, UC10):
  - Danh sách `model_versions`: version nào đang là champion, các challenger bị từ chối kèm lý do, metric so với champion và baseline persistence.
  - Biểu đồ Drift Report theo thời gian: max PSI mỗi lần chạy, xem chi tiết PSI/KS từng đặc trưng (theo skill `dataviz`).
  - Nút "Kích hoạt huấn luyện lại": gọi API → nhận `dag_run_id` → hiển thị trạng thái chạy cập nhật định kỳ cho tới khi có kết quả promote/từ chối.

## 2.8.3. Ghi chú hiện thực

- Mockup trực quan (wireframe hình ảnh) sẽ được dựng riêng bằng skill `design` (Claude Design canvas) trước khi code React thật, dùng làm tài liệu tham chiếu khi lập trình frontend ở Giai đoạn F.
- Toàn bộ biểu đồ trong ứng dụng tuân theo hướng dẫn của skill `dataviz` để đảm bảo màu sắc/trục/tooltip nhất quán giữa các màn hình.
