# Test tích hợp & phi chức năng (Giai đoạn H)

Bộ test chạy trên **hệ thống thật**, phủ mục 2.10.2 (integration) và 2.10.4 (phi chức năng) của
[`docs/design/02_10_thiet_ke_test.md`](../../docs/design/02_10_thiet_ke_test.md). Khác với unit test của từng
service (`packages/common`, `ml`, `services/*`), ở đây không có mock: Kafka, PostgreSQL/TimescaleDB và MLflow chạy
bằng docker compose, còn stream consumer và backend do chính bộ test khởi động dưới dạng tiến trình con — nhờ vậy
test giết và bật lại được chúng để kiểm tra khả năng chịu lỗi.

## Chuẩn bị

```bash
docker compose up -d postgres zookeeper kafka mlflow          # từ gốc repo
```

Ngoài ra cần: `.venv` đã cài 3 package nội bộ, `ml/data/processed/stream_replay.parquet`, và trên MLflow phải có
`risk_classifier@champion` (có thì `anomaly_detector@champion` càng tốt). Thiếu thứ nào, bộ test tự bỏ qua kèm
hướng dẫn thay vì báo lỗi khó hiểu.

## Chạy

```bash
cd tests/e2e && ../../.venv/Scripts/python -m pytest -q
```

> ⚠ **Bộ test xóa dữ liệu phát lại trong `rpm_db`** khi bắt đầu (đúng những bảng mà
> `python -m rpm_streaming.storage.reset_demo` xóa: patients, vital_records, predictions, alerts,
> notification_logs, patient_assignments). Giữ nguyên users, model_versions, alert_settings, drift_reports.
> Đừng chạy khi đang muốn giữ dữ liệu của một lần demo.

Toàn bộ mất khoảng 7 phút, phần lớn là phép đo độ trễ (phát lại ở tốc độ thật) và việc khởi động lại consumer
(mỗi lần nạp TensorFlow + 2 model mất ~15 giây).

## Các module (chạy đúng theo thứ tự số)

Thứ tự có ý nghĩa: con trỏ giờ phát lại dùng chung cả phiên, và `test_5_latency` dọn sạch DB để đo lại từ đầu.

| Module | Dòng trong 02_10 | Nội dung |
|---|---|---|
| `test_1_streaming_pipeline.py` | 2.10.2 dòng 1 | vitals → vital_record + prediction + `predictions-stream`; nhiều giờ CRITICAL liên tiếp chỉ 1 cảnh báo + `alerts-stream`; giờ trùng bị bỏ qua |
| `test_2_realtime_events.py` | 2.10.2 dòng 2, 3 | prediction/alert chỉ tới WebSocket của người được phân công; `notification_logs` đúng người nhận; đăng nhập sai → 401, token sai → WebSocket đóng; `alert_update` khi xác nhận/xử lý |
| `test_3_model_reload.py` | 2.10.2 dòng 6 | đổi alias `champion` trên MLflow → consumer nạp version mới, prediction ghi đúng version, cờ champion trong `model_versions` đi theo |
| `test_4_fault_tolerance.py` | 2.10.4 dòng 2, 3 | giết cứng consumer giữa chừng; tắt backend lúc đang replay rồi bật lại |
| `test_5_latency.py` | 2.10.4 dòng 1 | độ trễ đầu–cuối producer → WebSocket, 20 bệnh nhân, tốc độ mặc định; ngưỡng p95 < 2 giây |

Các dòng còn lại của 2.10.2 đã được phủ ở chỗ khác: retrain thủ công (dòng 4) trong `services/backend/tests`
(mock Airflow REST), drift → retrain tự động (dòng 5) chạy thật trên Docker Compose ở Giai đoạn G — số liệu ghi ở
[`docs/report/ghi_chu_bao_cao.md`](../../docs/report/ghi_chu_bao_cao.md).

## Kết quả sinh ra

- `reports/latency.md` + `.json` — bảng độ trễ cho báo cáo mục 3.4 (commit vào git).
- `.logs/` — log của consumer và backend từng lần chạy, xóa đầu mỗi phiên (không nằm trong git); đây là chỗ xem
  đầu tiên khi một test thất bại.

## Lưu ý khi sửa bộ test

- Mỗi module lấy một khoảng bệnh nhân riêng bằng `replay.take(n, offset=...)`; nhóm `stream` chỉ có 20 bệnh nhân
  và người ít nhất chỉ có **12 giờ** dữ liệu, nên đừng phát quá tay.
- Test nào cần thấy một cảnh báo **mới** đều phải đi qua fixture `alert_slate`: consumer chỉ tạo cảnh báo khi
  không còn cảnh báo OPEN cùng loại và đã qua cooldown (tính bằng giờ dữ liệu).
- Group Kafka mang hậu tố riêng cho từng phiên; riêng stream consumer (dùng `auto.offset.reset=earliest`) được
  commit sẵn offset cuối topic để không đọc lại lịch sử của những phiên trước.
- Khẳng định dựa trên log phải dùng `log_since_last_start()`, không dùng `log_text()`.
