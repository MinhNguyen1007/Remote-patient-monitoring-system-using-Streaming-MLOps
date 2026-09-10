# 2.6. Biểu đồ luồng dữ liệu (DFD) & Database Diagram

## 2.6.1. DFD mức ngữ cảnh (Context Diagram - Level 0)

```mermaid
flowchart LR
    Streaming([Nguồn dữ liệu vitals<br/>Streaming Source])
    Dataset([Bộ dữ liệu MIMIC-III<br/>đã tiền xử lý])
    Staff([Bác sĩ / Điều dưỡng])
    Admin([Admin])
    EmailSrv([Email Server])

    Streaming -- vitals theo giờ --> SYS((Hệ thống Giám sát<br/>Bệnh nhân Từ xa))
    Dataset -- dữ liệu huấn luyện --> SYS
    Staff -- đăng nhập, xác nhận/xử lý cảnh báo --> SYS
    SYS -- token, vitals, risk, alert realtime --> Staff
    Admin -- đăng nhập, quản trị, phân công, cấu hình, yêu cầu retrain --> SYS
    SYS -- token, drift report, trạng thái model --> Admin
    SYS -- nội dung cảnh báo / thông báo drift --> EmailSrv
    EmailSrv -- email cảnh báo --> Staff
    EmailSrv -- email thông báo drift --> Admin
```

## 2.6.2. DFD mức 1 (Level 1)

```mermaid
flowchart TB
    Streaming([Nguồn vitals<br/>Kafka producer replay])
    Dataset([Bộ dữ liệu MIMIC-III<br/>đã tiền xử lý])
    Staff([Bác sĩ / Điều dưỡng])
    Admin([Admin])
    EmailSrv([Email Server])

    P1[1.0 Thu thập &<br/>tính đặc trưng streaming]
    P2[2.0 Suy luận mô hình<br/>Risk + Anomaly]
    P3[3.0 Quản lý cảnh báo]
    P4[4.0 Xác thực & phân quyền]
    P5[5.0 Gửi thông báo]
    P6[6.0 Truy vấn dữ liệu bệnh nhân]
    P7[7.0 Phát hiện drift]
    P8[8.0 Huấn luyện lại - Airflow]
    P9[9.0 Quản trị hệ thống]

    D1[(D1: vital_records)]
    D2[(D2: predictions)]
    D3[(D3: model_versions)]
    D4[(D4: alerts)]
    D5[(D5: users)]
    D6[(D6: drift_reports)]
    D7[(D7: patients +<br/>patient_assignments)]
    D8[(D8: alert_settings)]
    D9[(D9: notification_logs)]
    D10[(D10: MLflow Registry<br/>model + reference_stats)]

    Streaming -- vitals theo giờ --> P1
    P1 -- bản ghi vitals --> D1
    P1 -- feature --> P2
    D10 -- model champion --> P2
    P2 -- kết quả dự đoán --> D2
    P2 -- prediction --> P3
    P2 -- prediction realtime --> P5

    D8 -- ngưỡng, cooldown --> P3
    D4 -- alert đang mở --> P3
    Staff -- xác nhận / xử lý cảnh báo --> P3
    P3 -- alert mới, trạng thái --> D4
    P3 -- alert mới --> P5

    D7 -- người được phân công --> P5
    D5 -- email người nhận --> P5
    P5 -- nội dung email --> EmailSrv
    P5 -- WebSocket vitals, risk, alert --> Staff
    P5 -- log gửi --> D9

    Staff -- thông tin đăng nhập --> P4
    Admin -- thông tin đăng nhập --> P4
    D5 -- tài khoản, role --> P4
    P4 -- JWT token --> Staff
    P4 -- JWT token --> Admin

    Staff -- yêu cầu xem --> P6
    D1 -- vitals --> P6
    D2 -- risk, anomaly --> P6
    D4 -- lịch sử cảnh báo --> P6
    D7 -- phạm vi phân công --> P6
    P6 -- danh sách, chi tiết, lịch sử --> Staff

    Admin -- tài khoản, phân công, ngưỡng --> P9
    P9 -- tài khoản --> D5
    P9 -- phân công --> D7
    P9 -- ngưỡng --> D8
    D3 -- phiên bản model --> P9
    D6 -- báo cáo drift --> P9
    P9 -- trạng thái model, drift report --> Admin

    D1 -- dữ liệu streaming gần nhất --> P7
    D10 -- reference_stats --> P7
    P7 -- báo cáo drift --> D6
    P7 -- thông báo drift --> P5
    P7 -- phát hiện drift --> P8
    Admin -- yêu cầu retrain --> P8
    Dataset -- train / validation / test --> P8
    D1 -- dữ liệu stream đã có nhãn --> P8
    P8 -- model version mới, alias --> D10
    P8 -- metadata, kết quả gate --> D3
```

**Kiểm tra cân bằng với mức 0**: mọi luồng vào/ra của hệ thống ở mức 0 đều có tiến trình tương ứng ở mức 1:

| Luồng ở mức 0 | Tiến trình ở mức 1 |
|---|---|
| vitals | 1.0 |
| dữ liệu huấn luyện | 8.0 |
| đăng nhập | 4.0 |
| xác nhận/xử lý cảnh báo | 3.0 |
| vitals/risk/alert realtime | 5.0, 6.0 |
| quản trị/phân công/cấu hình | 9.0 |
| yêu cầu retrain | 8.0 |
| drift report/trạng thái model | 9.0 |
| email | 5.0 |

Mọi kho dữ liệu đều có ít nhất một luồng ghi và một luồng đọc; riêng D9 là log kiểm toán, chỉ ghi.

## 2.6.3. Bảng dữ liệu vật lý (tổng quan)

Chi tiết cardinality/quan hệ trình bày ở mục 2.7 (ERD). Bảng dưới đây liệt kê nhanh các bảng chính tương ứng với data store trong DFD:

| Data store | Bảng | Vai trò |
|---|---|---|
| D1 | `vital_records` | Bản ghi vitals theo giờ của từng bệnh nhân — TimescaleDB hypertable theo `recorded_at` |
| D2 | `predictions` | Kết quả suy luận (NEWS2 hiện tại, risk_level, risk_score, anomaly_score, version 2 model) — TimescaleDB hypertable theo `recorded_at` |
| D3 | `model_versions` | Metadata tham chiếu tới MLflow Model Registry, kết quả quality gate (không lưu trọng số) |
| D4 | `alerts` | Cảnh báo phát sinh khi vượt ngưỡng, có trạng thái xử lý |
| D5 | `users` | Tài khoản, vai trò |
| D6 | `drift_reports` | Kết quả mỗi lần chạy kiểm tra drift |
| D7 | `patients`, `patient_assignments` | Bệnh nhân đang giám sát và phân công bác sĩ/điều dưỡng |
| D8 | `alert_settings` | Ngưỡng cảnh báo và cooldown do Admin cấu hình |
| D9 | `notification_logs` | Log gửi email cảnh báo/thông báo |
| D10 | MLflow Registry (ngoài `rpm_db`) | Model artifact, alias `champion`/`challenger`, `reference_stats.json` |

TimescaleDB được áp dụng cho `vital_records` và `predictions` (dữ liệu time-series). Các bảng nghiệp vụ còn lại dùng bảng PostgreSQL thông thường. MLflow dùng database riêng `mlflow_db` và volume artifact riêng.
