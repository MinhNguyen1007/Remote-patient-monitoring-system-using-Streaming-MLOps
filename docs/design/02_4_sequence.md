# 2.4. Biểu đồ trình tự (Sequence Diagram)

## 2.4.1. Dự đoán realtime & phát cảnh báo

```mermaid
sequenceDiagram
    participant P as Kafka Producer
    participant KV as Topic vitals-stream
    participant C as Stream Consumer<br/>(feature + Model Service)
    participant DB as PostgreSQL/TimescaleDB
    participant KE as Topic predictions-stream<br/>/ alerts-stream
    participant BE as FastAPI Backend<br/>(Event Listener)
    participant FE as React Dashboard
    participant Mail as SMTP Server

    P->>KV: publish(bản ghi giờ, key = mã bệnh nhân)
    KV->>C: consume
    C->>C: cập nhật state bệnh nhân, tính feature + NEWS2
    C->>C: predict_risk() → risk_score, risk_level
    opt baseline dùng được và đủ cửa sổ 12 giờ
        C->>C: predict_anomaly() → anomaly_score
    end
    C->>DB: INSERT vital_record + prediction
    C->>KE: publish(prediction)
    KE->>BE: consume(prediction)
    BE->>FE: WebSocket push (chỉ tới người được phân công)
    alt vượt ngưỡng VÀ không có alert cùng loại đang mở/còn cooldown
        C->>DB: INSERT alert (status = OPEN)
        C->>KE: publish(alert)
        KE->>BE: consume(alert)
        BE->>FE: WebSocket push alert
        BE->>DB: SELECT người được phân công (patient_assignments)
        BE-)Mail: gửi email (bất đồng bộ, không chặn luồng xử lý)
        BE->>DB: INSERT notification_logs
    else không vượt ngưỡng hoặc trùng alert đang mở
        Note over C,DB: chỉ lưu và đẩy prediction, không tạo alert
    end
```

Ghi chú hiện thực:
- **Model Service** là module chạy bên trong consumer, không phải service riêng.
  - Khi khởi động, nó nạp `models:/risk_classifier@champion` và `models:/anomaly_detector@champion` từ MLflow.
  - Sau đó định kỳ kiểm tra alias để nạp lại khi có model mới (mục 2.4.3).
- **Consumer giữ state theo từng bệnh nhân**: cửa sổ 6 giờ, baseline, cửa sổ 12 giờ. Khi khởi động lại, state được dựng lại từ 24 bản ghi gần nhất của mỗi bệnh nhân trong DB.
- **Consumer không gọi trực tiếp backend**. Nó publish kết quả lên Kafka và backend tự consume. Hai tiến trình tách rời nhau: backend dừng thì consumer vẫn chạy, chỉ trễ phần đẩy thông báo.
- **Backend là nơi duy nhất gửi email và đẩy WebSocket.**
- Topic `vitals-stream` dùng key = mã bệnh nhân, nên các bản ghi của cùng 1 bệnh nhân luôn nằm cùng partition và đúng thứ tự.

## 2.4.2. Đăng nhập hệ thống và mở kết nối realtime

```mermaid
sequenceDiagram
    participant U as Người dùng (browser)
    participant FE as React App
    participant BE as FastAPI Backend
    participant DB as PostgreSQL

    U->>FE: nhập email/mật khẩu, nhấn Đăng nhập
    FE->>BE: POST /auth/login
    BE->>DB: SELECT user WHERE email=?
    DB-->>BE: user record (password hash, role)
    BE->>BE: verify password hash
    alt hợp lệ
        BE->>BE: tạo JWT (sub=user_id, role)
        BE-->>FE: 200 OK {access_token, role}
        FE->>FE: lưu token, điều hướng theo role
        FE->>BE: mở WebSocket /ws kèm access_token
        BE->>BE: xác thực JWT
        BE->>DB: SELECT bệnh nhân được phân công cho user
        BE-->>FE: kết nối được chấp nhận, chỉ nhận sự kiện của bệnh nhân được phân công
    else không hợp lệ
        BE-->>FE: 401 Unauthorized
        FE->>U: hiển thị lỗi đăng nhập
    end
```

## 2.4.3. Kích hoạt huấn luyện lại mô hình (thủ công bởi Admin — UC10)

```mermaid
sequenceDiagram
    participant A as Admin (Dashboard)
    participant BE as FastAPI Backend
    participant AF as Airflow
    participant TR as Task huấn luyện/đánh giá
    participant MLF as MLflow Tracking + Registry
    participant DB as PostgreSQL
    participant MS as Model Service (trong Consumer)

    A->>BE: POST /admin/models/retrain
    BE->>AF: POST /api/v1/dags/retrain_pipeline/dagRuns (basic auth)
    AF-->>BE: dag_run_id
    BE-->>A: 202 Accepted {dag_run_id}
    par Airflow chạy DAG
        AF->>TR: dựng dữ liệu, train challenger
        TR->>MLF: log params/metrics/artifact, đăng ký version (alias challenger)
        TR->>TR: đánh giá challenger và champion trên cùng tập test cố định
        alt đạt quality gate
            TR->>MLF: chuyển alias champion sang version mới
            TR->>DB: ghi model_versions (promoted)
        else không đạt
            TR->>MLF: gắn tag gate=rejected kèm lý do
            TR->>DB: ghi model_versions (rejected)
        end
    and Admin theo dõi trạng thái
        loop mỗi vài giây cho tới khi DAG kết thúc
            A->>BE: GET /admin/models/retrain/{dag_run_id}
            BE->>AF: GET trạng thái dagRun
            AF-->>BE: running / success / failed
            BE-->>A: trạng thái + kết quả gate
        end
    end
    loop định kỳ (mặc định 60 giây)
        MS->>MLF: đọc version đang giữ alias champion
        MLF-->>MS: version
        MS->>MS: nếu version đổi thì nạp lại model
    end
```

Ghi chú:
- Huấn luyện có thể mất nhiều phút, nên backend trả `202 Accepted` ngay và giao diện theo dõi trạng thái, thay vì giữ request chờ.
- Luồng retrain **tự động** do drift dùng đúng DAG `retrain_pipeline` này, chỉ khác là được DAG `drift_check` kích hoạt (xem 2.3.3).
