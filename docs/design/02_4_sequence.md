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
    opt risk_level = CRITICAL hoặc is_anomaly
        C->>DB: SELECT lịch sử cảnh báo của bệnh nhân
        C->>C: alerts_to_create(): bỏ loại còn OPEN<br/>hoặc chưa hết cooldown
    end
    C->>DB: MỘT transaction: INSERT vital_record<br/>+ prediction + alert (nếu có)
    C->>KE: publish(prediction)
    KE->>BE: consume(prediction)
    BE->>FE: WebSocket push (chỉ tới người được phân công)
    alt có alert mới
        C->>KE: publish(alert)
        KE->>BE: consume(alert)
        BE->>FE: WebSocket push alert
        BE->>DB: SELECT người được phân công (patient_assignments)
        BE-)Mail: gửi email (bất đồng bộ, không chặn luồng xử lý)
        BE->>DB: INSERT notification_logs
    else không có alert mới
        Note over C,DB: chỉ lưu và đẩy prediction
    end
    C->>KV: commit offset (sau khi đã ghi DB)
```

Ghi chú hiện thực:
- **Quyết định cảnh báo nằm trước khi ghi DB**, và vital_record + prediction + alert được ghi trong **một transaction duy nhất** (`repository.save_hour`). Sơ đồ trước 2026-09-12 vẽ hai lần ghi DB riêng và đặt bước quyết định sau khi publish prediction — đã sửa cho khớp `services/streaming/src/rpm_streaming/consumer/main.py`.
- **Model Service** là module chạy bên trong consumer, không phải service riêng.
  - Khi khởi động, nó nạp `models:/risk_classifier@champion` và `models:/anomaly_detector@champion` từ MLflow.
  - Sau đó định kỳ kiểm tra alias để nạp lại khi có model mới (mục 2.4.3).
- **Consumer giữ state theo từng bệnh nhân**: toàn bộ giá trị đo theo giờ của đợt ICU đang phát lại (tối đa vài trăm giờ). Mỗi giờ mới, đặc trưng được tính lại bằng đúng hàm của `rpm_common` như lúc huấn luyện, rồi lấy giờ mới nhất.
  - Khi khởi động lại, state được dựng lại từ **toàn bộ** `vital_records` của bệnh nhân trong DB, không chỉ 24 bản ghi gần nhất. Lý do: baseline cá nhân tính trên 24 giờ đầu của đợt (mục 2.9.1f), nên thiếu các giờ đầu thì z-score sai.
  - Offset Kafka chỉ được commit sau khi đã ghi DB (at-least-once). Bản ghi giờ đã có trong DB được bỏ qua khi nhận lại, nên không có bản ghi hay cảnh báo trùng.
  - Kiểm thử thật (2026-09-11): kill cứng consumer giữa lúc phát lại rồi bật lại → đủ 229/229 bản ghi, 0 bản ghi trùng, 0 cảnh báo OPEN trùng.
- **Consumer không gọi trực tiếp backend**. Nó publish kết quả lên Kafka và backend tự consume. Hai tiến trình tách rời nhau: backend dừng thì consumer vẫn chạy, chỉ trễ phần đẩy thông báo.
- **Backend là nơi duy nhất gửi email và đẩy WebSocket.**
  - Event Listener của backend dùng consumer group riêng, commit offset sau khi xử lý: backend tắt rồi bật lại sẽ đọc tiếp từ offset cũ. Lần chạy đầu tiên (chưa có offset) bắt đầu từ sự kiện mới nhất, để không gửi email cho cảnh báo cũ.
  - Email gửi trong thread riêng, không chặn luồng đẩy WebSocket. Nếu `notification_logs` đã có `SENT` cho cặp (cảnh báo, người nhận) thì không gửi lại.
  - Khi bác sĩ xác nhận/xử lý cảnh báo (UC07), backend đẩy sự kiện `alert_update` tới mọi người cùng phụ trách bệnh nhân.
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
        FE->>BE: mở WebSocket /ws?token=access_token
        BE->>BE: xác thực JWT
        BE->>DB: SELECT bệnh nhân được phân công cho user
        BE-->>FE: kết nối được chấp nhận, chỉ nhận sự kiện của bệnh nhân được phân công
    else không hợp lệ
        BE-->>FE: 401 Unauthorized
        FE->>U: hiển thị lỗi đăng nhập
    end
```

Ghi chú hiện thực:
- Trình duyệt không đặt được header `Authorization` cho WebSocket, nên token đi qua query string. Backend che `token=` trong log truy cập để token không lộ ra log.
- Token sai, hết hạn hoặc tài khoản đã bị khóa → server đóng kết nối với mã 1008 (policy violation).

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
  - `GET /admin/models/retrain/{dag_run_id}` trả kèm các dòng `model_versions` có cùng `dag_run_id` (version mới, PROMOTED/REJECTED, lý do gate).
- Luồng retrain **tự động** do drift dùng đúng DAG `retrain_pipeline` này, chỉ khác là được DAG `drift_check` kích hoạt (xem 2.3.3 và 2.4.4).
- Khi DAG kết thúc, bước `publish_result` gửi sự kiện `retrain_completed` lên topic `mlops-events`; backend đẩy WebSocket cho Admin để tab Giám sát mô hình tự làm mới (không gửi email).

## 2.4.4. Phát hiện drift và thông báo Admin (UC09)

```mermaid
sequenceDiagram
    participant AF as Airflow DAG drift_check
    participant DB as PostgreSQL
    participant MLF as MLflow Registry
    participant K as Kafka mlops-events
    participant BE as FastAPI Backend
    participant A as Admin

    AF->>MLF: reference_stats.json + drift_thresholds.json của risk_classifier@champion
    AF->>DB: vital_records + patients (dựng lại đặc trưng bằng rpm_common)
    AF->>AF: 24 nhịp gần nhất, ≥ 200 bản ghi, có dữ liệu mới? → PSI/KS 7 đặc trưng
    AF->>DB: INSERT drift_reports
    alt drift và không bị chống vòng lặp chặn
        AF->>AF: TriggerDagRun retrain_pipeline (conf trigger=DRIFT, drift_report_id)
        AF->>DB: UPDATE drift_reports SET triggered_retrain, dag_run_id
    end
    AF->>K: drift_report {drift_detected, drifted_features, triggered_retrain, notify_admin}
    K-->>BE: Kafka listener (group rpm-backend)
    BE-->>A: WebSocket drift_report (mọi Admin đang hoạt động)
    opt notify_admin (bắt đầu đợt drift mới hoặc đã kích hoạt retrain)
        BE->>A: Email thông báo drift (thread riêng)
        BE->>DB: INSERT notification_logs (drift_report_id)
    end
```

Ghi chú:
- Airflow không gửi email trực tiếp: backend là nơi duy nhất gửi email và đẩy WebSocket, giống luồng cảnh báo ở 2.4.1.
- Drift kéo dài (lần kiểm tra trước cũng có drift) mà không kích hoạt thêm retrain thì `notify_admin = false`: vẫn ghi báo cáo và đẩy WebSocket, không gửi email lặp mỗi 2 phút.
