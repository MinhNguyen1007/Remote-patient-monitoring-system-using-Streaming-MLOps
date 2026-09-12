# 2.3. Biểu đồ hoạt động (Activity Diagram)

Hai luồng dài (2.3.1 và 2.3.3) được tách thành hai phần a/b. Lý do: mỗi luồng vẽ liền một mạch cho tỉ lệ khung hình khoảng 0,35 — cao gấp ba lần khung một trang A4 dọc, không đưa được vào bản in mà vẫn đọc được chữ (xem `docs/report/README.md`). Điểm tách trùng với ranh giới nghiệp vụ thật, nên hai phần đọc độc lập được.

## 2.3.1. Luồng xử lý dữ liệu streaming → cảnh báo (UC12, UC11)

### a) Từ message tới bản ghi đã lưu và sự kiện đã phát

```mermaid
flowchart TD
    Start([Bắt đầu]) --> A[Producer đọc bản ghi giờ tiếp theo<br/>của bệnh nhân nhóm stream]
    A --> B[Đẩy message vào topic vitals-stream<br/>key = mã bệnh nhân]
    B --> C[Consumer nhận message]
    C --> C1{Giờ này đã có trong state?}
    C1 -- Có --> End4([Kết thúc - bỏ qua bản ghi trùng])
    C1 -- Không --> D[Cập nhật state của bệnh nhân:<br/>cửa sổ 6 giờ, baseline, cửa sổ 12 giờ]
    D --> E[Tính feature và NEWS2 hiện tại]
    E --> F[Model dự báo rủi ro:<br/>risk_score, risk_level]
    E --> G{Baseline dùng được và<br/>đủ cửa sổ 12 giờ?}
    G -- Có --> H[LSTM-Autoencoder tính anomaly_score]
    G -- Không --> I[anomaly_score để trống]
    F --> DEC[Quyết định cảnh báo - xem phần b]
    H --> DEC
    I --> DEC
    DEC --> J[Một transaction DB:<br/>vital_record + prediction<br/>+ alert nếu có]
    J --> K[Publish prediction lên predictions-stream]
    K --> K1{Có alert mới?}
    K1 -- Có --> O[Publish alert lên alerts-stream]
    K1 -- Không --> CM[Commit offset Kafka]
    O --> CM
    CM --> End0([Kết thúc])
```

### b) Quyết định cảnh báo và thông báo người được phân công

```mermaid
flowchart TD
    Start([Đã có risk_level và anomaly_score<br/>của giờ hiện tại]) --> L{risk_level = CRITICAL<br/>HOẶC anomaly_score ≥ τ_anomaly?}
    L -- Không --> End1([Không tạo cảnh báo])
    L -- Có --> M{Còn alert cùng loại đang OPEN<br/>hoặc chưa hết cooldown?}
    M -- Có --> End2([Không tạo alert trùng])
    M -- Không --> N[Đưa alert vào cùng transaction<br/>với vital_record và prediction]
    N --> O[Consumer publish alert lên alerts-stream]
    O --> P[Backend đẩy alert qua WebSocket<br/>tới người được phân công]
    O --> Q[Backend gửi email tới bác sĩ/điều dưỡng<br/>được phân công, ghi notification_logs]
    P --> End3([Kết thúc])
    Q --> End3
```

Ghi chú:
- Prediction **luôn** được lưu và đẩy lên dashboard. Cảnh báo chỉ được tạo khi vượt ngưỡng **và** không trùng với cảnh báo đang mở.
- **Thứ tự ghi DB rồi mới commit offset là bắt buộc**: commit offset trước khi ghi DB sẽ làm mất bản ghi nếu consumer chết đúng giữa hai bước. Với thứ tự trên, sự cố chỉ dẫn tới việc xử lý lại message, và bản ghi trùng bị chặn ở nhánh `C1`.
- Quyết định cảnh báo nằm **trước** khi ghi DB, và alert được ghi trong **cùng một transaction** với vital_record + prediction — không phải hai lần ghi riêng. (Sơ đồ trước 2026-09-12 vẽ sai chỗ này: nó tách thành hai lần ghi và đặt bước quyết định sau khi publish prediction. Đã sửa cho khớp `services/streaming/src/rpm_streaming/consumer/main.py`.)
- Ngưỡng `τ_critical`, `τ_anomaly` và thời gian cooldown được mô tả ở mục 2.9.6.
- Mức WARNING chỉ đổi màu badge, không tạo cảnh báo.

## 2.3.2. Luồng đăng nhập (UC01)

```mermaid
flowchart TD
    Start([Bắt đầu]) --> A[Người dùng nhập email/mật khẩu]
    A --> B[Backend kiểm tra thông tin đăng nhập]
    B --> C{Hợp lệ?}
    C -- Không --> D[Trả lỗi, yêu cầu nhập lại]
    D --> A
    C -- Có --> E[Sinh JWT token kèm role]
    E --> F[Trả token về client, lưu phiên đăng nhập]
    F --> G[Điều hướng vào Dashboard theo đúng quyền của role]
    G --> End([Kết thúc])
```

## 2.3.3. Luồng phát hiện drift → huấn luyện lại (UC09, UC10)

### a) DAG `drift_check`: phát hiện drift và quyết định kích hoạt

```mermaid
flowchart TD
    S1([Airflow DAG drift_check chạy mỗi 2 phút<br/>hoặc chạy thủ công]) --> A[Lấy 24 nhịp dữ liệu streaming gần nhất]
    A --> A1{Có champion, đủ 24 nhịp, có dữ liệu mới<br/>và đủ tối thiểu 200 bản ghi?}
    A1 -- Không --> E0([Kết thúc - bỏ qua lần kiểm tra])
    A1 -- Có --> B[Tính PSI và KS cho 7 đặc trưng<br/>so với reference_stats của champion]
    B --> C[Ghi DriftReport]
    C --> D{Có đặc trưng PSI ≥ ngưỡng<br/>hiệu chỉnh của nó?}
    D -- Không --> P[Publish sự kiện drift_report:<br/>WebSocket tab Giám sát mô hình;<br/>email Admin nếu đợt drift mới<br/>hoặc đã kích hoạt retrain]
    D -- Có --> G{Đang có retrain chạy hoặc<br/>retrain gần nhất kết thúc chưa quá 1 giờ?}
    G -- Có --> P
    G -- Không --> R[Trigger DAG retrain_pipeline<br/>- xem phần b]
    R --> P
    P --> E1([Kết thúc])
```

### b) DAG `retrain_pipeline`: huấn luyện lại và quality gate

```mermaid
flowchart TD
    S2([Kích hoạt: tự động từ drift_check<br/>hoặc Admin bấm Kích hoạt huấn luyện lại - UC10]) --> H[Dựng dữ liệu: nhóm train +<br/>dữ liệu stream đã có nhãn]
    H --> I[Huấn luyện challenger cho 2 mô hình,<br/>log MLflow, đăng ký version alias challenger]
    I --> J[Đánh giá challenger VÀ champion<br/>trên cùng tập test cố định]
    J --> K{Đạt quality gate?<br/>áp dụng riêng cho từng mô hình}
    K -- Không --> L[Gắn tag gate=rejected kèm lý do,<br/>giữ nguyên champion]
    K -- Có --> M[Chuyển alias champion sang version mới]
    L --> W[Ghi model_versions kèm lý do gate]
    M --> W
    W --> N[Publish retrain_completed; consumer phát hiện<br/>alias đổi và nạp model mới]
    N --> E4([Kết thúc])
```

Ghi chú:
- Retrain được kích hoạt **tự động** khi có drift. Quality gate (mục 2.9.5) là chốt chặn không cho model kém hơn lên thay. Admin vẫn có thể kích hoạt thủ công (UC10) bất kỳ lúc nào.
- Quyết định drift dùng ngưỡng PSI **hiệu chỉnh theo từng đặc trưng** (luôn ≥ 0,25), không dùng một ngưỡng 0,25 chung — lý do ở mục 2.9.4.
- Thông báo Admin đứng sau bước chống vòng lặp để nội dung email nói rõ đã kích hoạt retrain hay chưa (và vì sao không).
- Ở bước đánh giá, **cả challenger lẫn champion đều được chấm lại** trên tập test cố định ngay tại thời điểm đó, không lấy metric đã log từ lần trước (có thể đo trên dữ liệu khác).
- Quality gate gồm 3 điều kiện:
  - Đạt ngưỡng tuyệt đối ở 2.10.3.
  - Mô hình rủi ro phải thắng baseline persistence.
  - Không kém champion trên cùng tập test.
