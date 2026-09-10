# 2.9. Thiết kế giải thuật

## 2.9.1. Feature Engineering

Từ 5 vitals thô (HR, SpO2, huyết áp tâm thu/tâm trương, nhiệt độ, nhịp thở) tại mỗi thời điểm, tính các nhóm đặc trưng:

1. **Điểm thành phần kiểu NEWS2** cho từng vital — mỗi vital được lượng hóa thành điểm 0-3 theo bảng ngưỡng lâm sàng chuẩn (NEWS2), tổng điểm là `news2_score` (0-20). Đây vừa là đặc trưng đầu vào, vừa là cơ sở để **suy ra nhãn huấn luyện proxy** (xem 2.9.2) do MIMIC-III Demo không có nhãn "risk_level" trực tiếp cho từng thời điểm.
2. **Rolling statistics** theo cửa sổ trượt (mặc định 1 giờ): trung bình, độ lệch chuẩn, độ dốc (slope) tuyến tính của từng vital trong cửa sổ — bắt xu hướng thay đổi thay vì chỉ giá trị tức thời.
3. **Độ lệch so với baseline cá nhân**: `(giá_trị_hiện_tại − trung_bình_24h_đầu_của_bệnh_nhân) / độ_lệch_chuẩn_24h_đầu` — chuẩn hóa theo từng bệnh nhân, dùng riêng cho mô hình anomaly detection (2.9.4).

## 2.9.2. Mô hình Phân loại rủi ro (Risk Classification)

- **Bài toán**: phân loại đa lớp `risk_level ∈ {NORMAL, WARNING, CRITICAL}` tại mỗi thời điểm có vitals mới.
- **Nhãn huấn luyện**: vì MIMIC-III Demo không gán sẵn nhãn theo thời điểm, nhãn được suy ra bằng quy tắc ngưỡng trên `news2_score` (NORMAL: 0-4, WARNING: 5-6, CRITICAL: ≥7 — theo hướng dẫn lâm sàng NEWS2 gốc), sau đó **đối chiếu chéo** với outcome thật có trong MIMIC (tử vong/chuyển ICU) trên tập validation để xác nhận độ tin cậy của nhãn proxy. Giới hạn này được nêu rõ ở mục 3.5.
- **Đặc trưng đầu vào**: 5 vitals thô + rolling mean/std/slope (mục 2.9.1) + điểm thành phần NEWS2 từng vital.
- **Mô hình**:
  - Baseline: Logistic Regression (multinomial, có regularization L2).
  - Mô hình chính: **XGBoost** multi-class classifier (`objective=multi:softprob`), so sánh thêm với Random Forest để chọn mô hình tốt nhất theo thực nghiệm.
- **Chia tập dữ liệu**: chia theo **patient-level** (không theo record-level) để tránh rò rỉ dữ liệu — vitals của cùng 1 bệnh nhân không được xuất hiện đồng thời ở cả train và test.
- **Đánh giá**: Accuracy, Macro F1, **Recall riêng cho lớp CRITICAL** (ưu tiên lâm sàng: bỏ sót ca nguy kịch nghiêm trọng hơn báo động giả), AUROC one-vs-rest, ma trận nhầm lẫn.
- **Giải thích mô hình**: SHAP values để xác định vital nào đóng góp nhiều nhất vào từng dự đoán — phục vụ mục 3.4/3.5 khi thảo luận kết quả.

## 2.9.3. Mô hình Phát hiện bất thường (Anomaly Detection — Deep Learning)

- **Kiến trúc**: LSTM-Autoencoder.
  - Encoder: `LSTM(64, return_sequences=True) → LSTM(32, return_sequences=False)` → vector ẩn (latent).
  - Decoder: `RepeatVector(window_length) → LSTM(32, return_sequences=True) → LSTM(64, return_sequences=True) → TimeDistributed(Dense(n_features=5))`.
  - Hàm mất mát: MSE giữa chuỗi đầu vào và chuỗi tái tạo. Optimizer: Adam.
- **Cửa sổ đầu vào**: chuỗi `window_length` bước thời gian liên tiếp (mặc định tương đương ~1 giờ dữ liệu), 5 kênh (5 vitals), đã chuẩn hóa theo baseline cá nhân (mục 2.9.1, mục 3).
- **Huấn luyện**: chỉ dùng các cửa sổ được gắn nhãn proxy NORMAL (từ 2.9.2) để mô hình học đúng "hình dạng bình thường" của tín hiệu sinh tồn.
- **Suy luận**: `anomaly_score = reconstruction_error (MSE)` của cửa sổ hiện tại; nếu `anomaly_score > ngưỡng` → gắn cờ bất thường. Ngưỡng xác định bằng percentile (mặc định 95th percentile của reconstruction error trên tập validation NORMAL).
- **Đánh giá**: do MIMIC-III Demo không có nhãn "bất thường" tường minh, áp dụng phương pháp **tiêm bất thường tổng hợp** (synthetic anomaly injection: spike đột ngột, dropout tín hiệu, drift dần) vào chuỗi validation bình thường để đo Precision/Recall/F1 của mô hình phát hiện — nêu rõ đây là đánh giá bán thực nghiệm ở mục 3.5.

## 2.9.4. Drift Detection

- **Phương pháp**: Population Stability Index (PSI) cho từng feature:

  `PSI = Σ (actual_pct_i − expected_pct_i) × ln(actual_pct_i / expected_pct_i)` (tính theo các bin phân phối, `expected` là phân phối lúc train, `actual` là phân phối cửa sổ dữ liệu streaming gần nhất).

  Bổ sung kiểm định Kolmogorov–Smirnov (KS-test) làm kiểm chứng chéo cho biến liên tục.
- **Ngưỡng quyết định**: PSI < 0.1 → không đáng kể; 0.1 ≤ PSI < 0.25 → lệch trung bình (ghi log, chưa cảnh báo); PSI ≥ 0.25 → lệch đáng kể → tạo `DriftReport` và cảnh báo Admin (theo hoạt động 2.3.3).
- **Tần suất chạy**: job định kỳ (mặc định hàng ngày) trên cửa sổ dữ liệu streaming tích lũy, có thể chạy thủ công theo yêu cầu Admin.

## 2.9.5. Chiến lược Retrain (Champion–Challenger)

Khi drift được xác nhận (tự động hoặc Admin xác nhận thủ công): Airflow chạy lại toàn bộ pipeline huấn luyện trên dữ liệu cập nhật, tạo ra model "challenger". Model challenger chỉ được đăng ký thay thế model "champion" (Production hiện tại trên MLflow Registry) khi đạt **đồng thời**:

1. Macro F1 (risk classification) ≥ model hiện tại.
2. Recall lớp CRITICAL ≥ model hiện tại (không được đánh đổi giảm khả năng phát hiện ca nguy kịch để đổi lấy accuracy tổng thể cao hơn).

Nếu không đạt, model mới bị từ chối, giữ nguyên model cũ và ghi log lý do — tránh tình trạng tự động hạ cấp chất lượng hệ thống khi retrain trên dữ liệu nhiễu.
