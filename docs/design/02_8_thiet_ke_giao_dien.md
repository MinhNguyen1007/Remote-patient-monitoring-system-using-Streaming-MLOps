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

## 2.8.2. Danh sách màn hình chính (ánh xạ theo Use Case ở mục 2.2)

### Màn hình Đăng nhập (UC01)
- Form email/mật khẩu giữa màn hình trên nền dark theme, logo hệ thống, nút "Đăng nhập" dùng accent-neon.
- Thông báo lỗi hiển thị dạng toast góc trên khi sai thông tin.

### Dashboard danh sách bệnh nhân (UC04)
- Layout: sidebar điều hướng trái (Dashboard, Cảnh báo, Quản trị — hiện theo role) + khu vực chính dạng bảng/thẻ.
- Mỗi bệnh nhân là 1 dòng/thẻ: tên, mã bệnh nhân, badge màu risk-level realtime (cập nhật qua WebSocket, có hiệu ứng transition khi đổi màu), chỉ số vitals mới nhất rút gọn (HR, SpO2), thời gian cập nhật cuối.
- Thanh lọc theo mức rủi ro (tất cả/warning/critical), sắp xếp theo rủi ro cao nhất lên đầu.
- Badge số lượng cảnh báo chưa xử lý (unread) trên sidebar mục "Cảnh báo".

### Chi tiết bệnh nhân (UC05, UC06, UC07)
- Header: thông tin bệnh nhân + risk-level hiện tại (badge lớn).
- Biểu đồ vitals theo thời gian thực (line chart 5 chỉ số, có thể chọn hiển thị từng chỉ số), điểm bất thường được đánh dấu bằng `--anomaly-flag` trên biểu đồ (theo skill `dataviz`).
- Biểu đồ risk-timeline: dải màu theo thời gian thể hiện risk_level đổi qua các mốc.
- Danh sách lịch sử cảnh báo của bệnh nhân, mỗi cảnh báo có nút "Xác nhận đã xử lý" (chỉ Bác sĩ).

### Panel/Trung tâm cảnh báo (UC06, UC07, UC11)
- Danh sách toàn bộ cảnh báo toàn hệ thống, realtime, có filter theo trạng thái (Mở/Đã xác nhận/Đã xử lý) và theo loại (Risk/Anomaly).
- Cảnh báo mới xuất hiện có hiệu ứng nhấn mạnh tạm thời (motion, không phải nhấp nháy liên tục gây khó chịu).

### Trang quản trị (UC03, UC08, UC09, UC10) — chỉ Admin
- Tab **Người dùng**: CRUD tài khoản, gán bác sĩ phụ trách bệnh nhân.
- Tab **Cấu hình ngưỡng**: chỉnh ngưỡng risk_score/anomaly_score để tạo alert.
- Tab **Giám sát mô hình**: danh sách `model_versions` (từ MLflow), biểu đồ Drift Report theo thời gian (theo skill `dataviz`), nút "Kích hoạt huấn luyện lại" (trigger Airflow DAG qua UC10) kèm trạng thái chạy realtime.

## 2.8.3. Ghi chú hiện thực

- Mockup trực quan (wireframe hình ảnh) sẽ được dựng riêng bằng skill `design` (Claude Design canvas) trước khi code React thật, dùng làm tài liệu tham chiếu khi lập trình frontend ở Giai đoạn F.
- Toàn bộ biểu đồ trong ứng dụng tuân theo hướng dẫn của skill `dataviz` để đảm bảo màu sắc/trục/tooltip nhất quán giữa các màn hình.
