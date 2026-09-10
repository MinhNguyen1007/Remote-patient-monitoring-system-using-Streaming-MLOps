# 2.6. Biểu đồ luồng dữ liệu (DFD) & Database Diagram

## 2.6.1. DFD mức ngữ cảnh (Context Diagram - Level 0)

```mermaid
flowchart LR
    Streaming([Nguồn dữ liệu vitals<br/>Streaming Source])
    Staff([Bác sĩ / Điều dưỡng])
    Admin([Admin])
    EmailSrv([Email Server])

    Streaming -- vitals raw --> SYS((Hệ thống Giám sát<br/>Bệnh nhân Từ xa))
    SYS -- vitals + risk + alert --> Staff
    Staff -- xác nhận cảnh báo --> SYS
    Admin -- quản trị/cấu hình --> SYS
    SYS -- drift report/model status --> Admin
    SYS -- nội dung cảnh báo --> EmailSrv
    EmailSrv -- email đã gửi --> Staff
```

## 2.6.2. DFD mức 1 (Level 1)

```mermaid
flowchart TB
    Streaming([Nguồn vitals]) --> P1[1.0 Thu thập & tiền xử lý streaming]
    P1 --> D1[(D1: vital_records)]
    P1 --> P2[2.0 Suy luận mô hình<br/>Risk + Anomaly]
    D3[(D3: model_versions<br/>MLflow metadata)] --> P2
    P2 --> D2[(D2: predictions)]
    P2 --> P3[3.0 Quản lý cảnh báo]
    P3 --> D4[(D4: alerts)]
    P3 --> P5[5.0 Gửi thông báo]
    P5 --> EmailSrv([Email Server])
    P5 --> Staff([Bác sĩ/Điều dưỡng])

    Staff --> P4[4.0 Xác thực & phân quyền]
    Admin([Admin]) --> P4
    D5[(D5: users)] --> P4
    P4 --> D5

    Staff --> P6[6.0 Truy vấn xem dữ liệu]
    D1 --> P6
    D2 --> P6
    D4 --> P6
    P6 --> Staff

    D1 --> P7[7.0 Drift Detection]
    P7 --> D6[(D6: drift_reports)]
    P7 -->|phát hiện drift| P8[8.0 Retrain Pipeline - Airflow]
    P8 --> D3
    Admin --> P8
```

## 2.6.3. Bảng dữ liệu vật lý (tổng quan)

Chi tiết cardinality/quan hệ trình bày ở mục 2.7 (ERD). Bảng dưới đây liệt kê nhanh các bảng chính tương ứng với data store trong DFD:

| Data store | Bảng | Vai trò |
|---|---|---|
| D1 | `vital_records` | Lưu bản ghi vitals thô theo bệnh nhân, dùng TimescaleDB hypertable theo `recorded_at` |
| D2 | `predictions` | Kết quả suy luận (risk_level, risk_score, anomaly_score) gắn với `vital_records` |
| D3 | `model_versions` | Metadata tham chiếu tới MLflow Model Registry (không lưu trọng số) |
| D4 | `alerts` | Cảnh báo phát sinh khi vượt ngưỡng, có trạng thái xử lý |
| D5 | `users` | Tài khoản, vai trò |
| D6 | `drift_reports` | Kết quả phát hiện drift theo từng lần chạy job |

TimescaleDB được áp dụng cho `vital_records` và `predictions` (dữ liệu time-series tần suất cao), trong khi `users`, `alerts`, `model_versions`, `drift_reports` dùng bảng PostgreSQL thông thường.
