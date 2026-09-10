# 2.10. Thiết kế các bộ Test

Bộ test được thiết kế ánh xạ trực tiếp tới các use case (2.2), luồng hoạt động (2.3) và giải thuật (2.9) đã thiết kế, đảm bảo mọi chức năng đều có tiêu chí kiểm tra tương ứng trước khi hiện thực (Giai đoạn H, sau khi code xong sẽ chạy để xác nhận).

## 2.10.1. Unit Test

| Thành phần | Nội dung test | Công cụ |
|---|---|---|
| Feature engineering (`compute_news2_score`, rolling stats, baseline z-score) | Kiểm tra công thức tính điểm đúng theo bảng ngưỡng NEWS2 với các giá trị biên (edge case: giá trị vitals ở đúng ranh giới ngưỡng) | pytest |
| Auth (hash/verify mật khẩu, sinh/giải mã JWT, phân quyền theo role) | Mật khẩu đúng/sai, token hết hạn, role không đủ quyền bị từ chối (403) | pytest |
| CRUD API (patients, users, alerts) | Validate input, lỗi 404/422, quyền truy cập đúng theo role (UC03, UC04) | pytest + httpx TestClient |
| Model wrapper (`predict_risk`, `predict_anomaly`) | Input hình dạng đúng/sai, output đúng kiểu dữ liệu (risk_level enum, anomaly_score float trong [0,1] sau chuẩn hóa) | pytest |
| Drift detection (`compute_psi`) | So sánh với giá trị PSI tính tay trên tập dữ liệu mẫu nhỏ đã biết trước kết quả | pytest |

## 2.10.2. Integration Test

| Luồng (tham chiếu Activity/Sequence) | Nội dung test | Công cụ |
|---|---|---|
| 2.3.1 / 2.4.1: Streaming → Prediction → Alert | Producer đẩy 1 message mẫu → consumer xử lý → kiểm tra bản ghi `predictions` (và `alerts` nếu vượt ngưỡng) xuất hiện đúng trong DB trong thời gian giới hạn | pytest + testcontainers (Kafka, Postgres) |
| 2.4.1: Alert → WebSocket + Email | Giả lập alert vượt ngưỡng → kiểm tra client WebSocket nhận đúng payload; kiểm tra email service được gọi với đúng nội dung (mock SMTP) | pytest-asyncio, `unittest.mock` |
| 2.4.2: Đăng nhập | Đăng nhập đúng/sai thông tin qua API thật, kiểm tra token trả về decode đúng role | pytest + httpx |
| 2.4.3: Retrain trigger | Gọi endpoint `/admin/models/retrain` (mock Airflow API) → kiểm tra DAG được trigger đúng tham số; giả lập kết quả model mới tốt hơn/kém hơn → kiểm tra logic promote/reject đúng như 2.9.5 | pytest + mock HTTP |
| Drift → Retrain (2.3.3) | Đẩy dữ liệu streaming có phân phối lệch chủ đích → kiểm tra `drift_reports` được tạo, và cảnh báo Admin được gửi | pytest + testcontainers |

## 2.10.3. Model Evaluation Test (Quality Gate)

Chạy như một bước kiểm tra tự động trước khi cho phép model mới được đăng ký `Production` trên MLflow (gắn với chiến lược Champion–Challenger ở 2.9.5):

| Mô hình | Tiêu chí đạt (ngưỡng đề xuất, sẽ hiệu chỉnh theo kết quả thực nghiệm ở mục 3.4) |
|---|---|
| Risk Classification | Macro F1 ≥ 0.75; Recall lớp CRITICAL ≥ 0.85 trên tập validation patient-level |
| Anomaly Detection (LSTM-Autoencoder) | Precision ≥ 0.7, Recall ≥ 0.7 trên tập bất thường tổng hợp (synthetic injection, mục 2.9.3) |
| Drift Detection | PSI tính đúng trong khoảng sai số 1e-4 so với công thức tham chiếu trên bộ dữ liệu kiểm thử cố định |

Nếu model mới không đạt ngưỡng, pipeline retrain (Airflow) đánh dấu run là "rejected" và giữ nguyên model cũ.

## 2.10.4. Chiến lược dữ liệu test

- Dùng một tập con nhỏ (5-10 bệnh nhân) trích từ MIMIC-III Demo làm fixture cố định cho unit/integration test — đảm bảo test chạy nhanh, không phụ thuộc tải toàn bộ dataset.
- Chia theo patient-level giống lúc train (mục 2.9.2) để test evaluation phản ánh đúng kịch bản thực tế, tránh rò rỉ dữ liệu giữa fixture train/test nội bộ.
- Test hạ tầng (Kafka, Postgres) chạy bằng container tạm thời (testcontainers), tự dọn dẹp sau mỗi lần chạy CI.
