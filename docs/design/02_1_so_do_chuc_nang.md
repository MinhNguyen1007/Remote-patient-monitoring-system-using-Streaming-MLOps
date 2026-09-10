# 2.1. Sơ đồ chức năng tổng quát

Sơ đồ dưới đây chia hệ thống thành 5 nhóm chức năng lớn: **Nguồn dữ liệu & Streaming**, **Xử lý & Suy luận thời gian thực**, **Lưu trữ**, **Dịch vụ ứng dụng (Backend/Frontend)**, và **Vòng lặp MLOps**.

```mermaid
flowchart TB
    subgraph SRC["Nguồn dữ liệu & Streaming"]
        A1[MIMIC-III Demo Dataset]
        A2[Kafka Producer<br/>replay vitals theo bệnh nhân]
        A3[(Kafka Topic: vitals-stream)]
        A1 --> A2 --> A3
    end

    subgraph RT["Xử lý & Suy luận thời gian thực"]
        B1[Kafka Consumer]
        B2[Feature Engineering<br/>tính NEWS2-score, rolling stats]
        B3[Model Risk Classification<br/>XGBoost/RandomForest]
        B4[Model Anomaly Detection<br/>LSTM-Autoencoder]
        B5[Alert Evaluator<br/>so ngưỡng rủi ro]
        A3 --> B1 --> B2 --> B3
        B2 --> B4
        B3 --> B5
        B4 --> B5
    end

    subgraph STORE["Lưu trữ"]
        C1[(PostgreSQL + TimescaleDB)]
    end
    B5 --> C1
    B3 --> C1
    B4 --> C1

    subgraph APP["Dịch vụ ứng dụng"]
        D1[FastAPI Backend<br/>REST + WebSocket + Auth]
        D2[Email Alert Service]
        D3[React Dashboard<br/>realtime, phân quyền theo vai trò]
        C1 <--> D1
        B5 -. rủi ro cao .-> D2
        D1 <--> D3
        D1 -. WebSocket push .-> D3
    end

    subgraph MLOPS["Vòng lặp MLOps"]
        E1[Training Pipeline<br/>offline, từ MIMIC-III]
        E2[MLflow Tracking + Registry]
        E3[Drift Detection Job<br/>PSI/KS-test]
        E4[Airflow Retrain DAG]
        E1 --> E2
        C1 -. dữ liệu streaming thực tế .-> E3
        E3 -->|phát hiện drift| E4
        E4 --> E1
        E2 -->|nạp model mới nhất| B3
        E2 -->|nạp model mới nhất| B4
    end
```

**Giải thích luồng chính**: dữ liệu vitals được phát lại (replay) qua Kafka như một nguồn streaming thật → consumer tính feature và chạy song song 2 mô hình (phân loại rủi ro + phát hiện bất thường) → kết quả được lưu vào DB và đánh giá ngưỡng cảnh báo → nếu vượt ngưỡng, đẩy cảnh báo realtime lên dashboard qua WebSocket và gửi email → toàn bộ dữ liệu thực tế được dùng để giám sát drift, khi phát hiện lệch sẽ kích hoạt Airflow chạy lại pipeline huấn luyện, đăng ký phiên bản model mới vào MLflow Registry để hệ thống suy luận nạp lại.
