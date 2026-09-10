# 2.3. Biểu đồ hoạt động (Activity Diagram)

## 2.3.1. Luồng xử lý dữ liệu streaming → cảnh báo (UC12, UC11)

```mermaid
flowchart TD
    Start([Bắt đầu]) --> A[Producer đọc bản ghi giờ tiếp theo của bệnh nhân<br/>từ dữ liệu đã tiền xử lý của nhóm stream]
    A --> B[Đẩy message vào topic vitals-stream<br/>key = mã bệnh nhân]
    B --> C[Consumer nhận message]
    C --> D[Cập nhật state của bệnh nhân:<br/>cửa sổ 6 giờ, baseline, cửa sổ 12 giờ]
    D --> E[Tính feature và NEWS2 hiện tại]
    E --> F[Model dự báo rủi ro:<br/>risk_score, risk_level]
    E --> G{Baseline dùng được và<br/>đủ cửa sổ 12 giờ?}
    G -- Có --> H[LSTM-Autoencoder tính anomaly_score]
    G -- Không --> I[anomaly_score để trống]
    F --> J[Lưu vital_record và prediction vào DB]
    H --> J
    I --> J
    J --> K[Publish prediction lên topic predictions-stream]
    K --> K2[Backend đẩy prediction qua WebSocket<br/>tới người được phân công - dashboard realtime]
    K --> L{risk_level = CRITICAL<br/>HOẶC anomaly_score ≥ τ_anomaly?}
    K2 --> End0([Kết thúc])
    L -- Không --> End1([Kết thúc])
    L -- Có --> M{Còn alert cùng loại đang OPEN<br/>hoặc chưa hết cooldown?}
    M -- Có --> End2([Kết thúc - không tạo alert trùng])
    M -- Không --> N[Tạo bản ghi Alert trong DB]
    N --> O[Publish alert lên topic alerts-stream]
    O --> P[Backend đẩy alert qua WebSocket<br/>tới người được phân công]
    O --> Q[Backend gửi email tới bác sĩ/điều dưỡng<br/>được phân công, ghi notification_logs]
    P --> End3([Kết thúc])
    Q --> End3
```

Ghi chú:
- Prediction **luôn** được lưu và đẩy lên dashboard. Cảnh báo chỉ được tạo khi vượt ngưỡng **và** không trùng với cảnh báo đang mở.
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

```mermaid
flowchart TD
    S1([Airflow DAG drift_check chạy theo lịch<br/>hoặc chạy thủ công]) --> A[Lấy 24 giờ dữ liệu streaming gần nhất]
    A --> A1{Đủ tối thiểu 200 bản ghi?}
    A1 -- Không --> E0([Kết thúc - bỏ qua lần kiểm tra])
    A1 -- Có --> B[Tính PSI và KS cho 7 đặc trưng<br/>so với reference_stats của champion]
    B --> C[Ghi DriftReport]
    C --> D{max PSI ≥ 0,25?}
    D -- Không --> E1([Kết thúc])
    D -- Có --> F[Thông báo Admin:<br/>email + tab Giám sát mô hình]
    F --> G{Đang có retrain chạy hoặc<br/>retrain gần nhất kết thúc chưa quá 1 giờ?}
    G -- Có --> E2([Kết thúc - không kích hoạt lặp])
    G -- Không --> R[Trigger DAG retrain_pipeline]
    S2([Admin bấm Kích hoạt huấn luyện lại - UC10]) --> R
    R --> H[Dựng dữ liệu: nhóm train +<br/>dữ liệu stream đã có nhãn]
    H --> I[Huấn luyện challenger cho 2 mô hình,<br/>log MLflow, đăng ký version alias challenger]
    I --> J[Đánh giá challenger và champion<br/>trên cùng tập test cố định]
    J --> K{Đạt quality gate?<br/>áp dụng riêng cho từng mô hình}
    K -- Không --> L[Gắn tag gate=rejected kèm lý do,<br/>giữ nguyên champion]
    L --> E3([Kết thúc])
    K -- Có --> M[Chuyển alias champion sang version mới,<br/>ghi bảng model_versions]
    M --> N[Consumer phát hiện alias đổi,<br/>nạp model mới]
    N --> E4([Kết thúc])
```

Ghi chú:
- Retrain được kích hoạt **tự động** khi có drift. Quality gate (mục 2.9.5) là chốt chặn không cho model kém hơn lên thay. Admin vẫn có thể kích hoạt thủ công (UC10) bất kỳ lúc nào.
- Quality gate gồm 3 điều kiện:
  - Đạt ngưỡng tuyệt đối ở 2.10.3.
  - Mô hình rủi ro phải thắng baseline persistence.
  - Không kém champion trên cùng tập test.
