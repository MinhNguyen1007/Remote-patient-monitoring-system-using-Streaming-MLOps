# 2.1. Sơ đồ chức năng tổng quát

Sơ đồ dưới đây chia hệ thống thành 5 nhóm chức năng lớn:
- **Nguồn dữ liệu & Streaming**
- **Xử lý & Suy luận thời gian thực**
- **Lưu trữ & kênh sự kiện**
- **Dịch vụ ứng dụng (Backend/Frontend)**
- **Vòng lặp MLOps**

```mermaid
flowchart TB
    subgraph SRC["Nguồn dữ liệu & Streaming"]
        A1[MIMIC-III Demo đã tiền xử lý<br/>nhóm bệnh nhân stream]
        A2[Kafka Producer<br/>replay vitals theo giờ]
        A3[(Kafka topic vitals-stream)]
        A1 --> A2 --> A3
    end

    subgraph RT["Xử lý & Suy luận thời gian thực - Stream Consumer"]
        B1[Kafka Consumer<br/>giữ state theo bệnh nhân]
        B2[Feature Engineering<br/>NEWS2 rút gọn, cửa sổ 6h và 12h]
        B3[Model dự báo rủi ro<br/>XGBoost/RandomForest]
        B4[Model phát hiện bất thường<br/>LSTM-Autoencoder]
        B5[Alert Evaluator<br/>ngưỡng + chống cảnh báo trùng]
        A3 --> B1 --> B2 --> B3
        B2 --> B4
        B3 --> B5
        B4 --> B5
    end

    subgraph STORE["Lưu trữ & kênh sự kiện"]
        C1[(PostgreSQL + TimescaleDB)]
        C2[(Kafka topic predictions-stream<br/>và alerts-stream)]
    end
    B5 --> C1
    B5 --> C2

    subgraph APP["Dịch vụ ứng dụng"]
        D1[FastAPI Backend<br/>REST + WebSocket + JWT]
        D2[Notification Service<br/>email tới người được phân công]
        D3[React Dashboard<br/>realtime, phân quyền theo vai trò]
        C1 <--> D1
        C2 --> D1
        D1 --> D2
        D1 <--> D3
        D1 -. WebSocket push .-> D3
    end

    subgraph MLOPS["Vòng lặp MLOps"]
        E1[Training Pipeline<br/>huấn luyện + quality gate]
        E2[MLflow Tracking + Registry<br/>alias champion / challenger]
        E3[Airflow DAG drift_check<br/>PSI / KS]
        E4[Airflow DAG retrain_pipeline]
        C1 -. dữ liệu streaming .-> E3
        E3 -->|phát hiện drift - tự động| E4
        D1 -->|Admin kích hoạt thủ công| E4
        E4 --> E1 --> E2
        E2 -->|nạp model champion| B3
        E2 -->|nạp model champion| B4
    end
```

**Giải thích luồng chính**:
1. **Replay.** Dữ liệu vitals đã tiền xử lý của nhóm bệnh nhân `stream` được phát lại theo từng giờ qua Kafka như một nguồn streaming thật.
2. **Suy luận.** Consumer giữ state theo từng bệnh nhân, tính đặc trưng bằng cùng thư viện đã dùng khi huấn luyện, rồi chạy 2 mô hình:
   - dự báo rủi ro trong 4 giờ tới;
   - phát hiện bất thường so với baseline của chính bệnh nhân.
3. **Lưu và phát sự kiện.** Kết quả được lưu vào DB và publish lên topic `predictions-stream`. Cảnh báo chỉ được tạo khi vượt ngưỡng và không trùng cảnh báo đang mở; khi đó nó được lưu vào DB và publish lên `alerts-stream`.
4. **Thông báo.** Backend consume 2 topic này để đẩy WebSocket lên dashboard và gửi email. Người nhận là bác sĩ/điều dưỡng được phân công cho bệnh nhân.
5. **Vòng lặp MLOps.**
   - DAG `drift_check` định kỳ so sánh phân phối dữ liệu streaming với phân phối huấn luyện của model champion.
   - Khi lệch đáng kể, nó tự động kích hoạt DAG `retrain_pipeline`. Admin cũng có thể kích hoạt thủ công.
   - Model mới chỉ nhận alias `champion` khi qua quality gate. Consumer phát hiện alias đổi và nạp model mới.
