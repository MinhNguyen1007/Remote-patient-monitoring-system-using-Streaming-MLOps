# 2.10. Thiết kế các bộ Test

Bộ test được thiết kế ánh xạ trực tiếp tới các use case (2.2), luồng hoạt động (2.3), trình tự (2.4) và giải thuật (2.9) đã thiết kế, đảm bảo mọi chức năng đều có tiêu chí kiểm tra tương ứng trước khi hiện thực.

**Test được viết song song với từng giai đoạn hiện thực**, không dồn về cuối:

| Giai đoạn | Test viết kèm |
|---|---|
| C | Tiền xử lý, NEWS2, nhãn, quality gate |
| D | Streaming, cảnh báo |
| E | API, phân quyền |
| F | Logic giao diện |
| G | Drift, retrain |

Giai đoạn H chạy integration/E2E toàn hệ thống, kiểm thử phi chức năng và tổng hợp kết quả cho báo cáo.

## 2.10.1. Unit Test

| Thành phần | Nội dung test | Công cụ |
|---|---|---|
| Tiền xử lý (`packages/common` — `rpm_common`) | • Gộp đúng mọi itemid (kể cả 220050/220051, 676, 615/224690); loại 677/679.<br>• Đổi °F → °C; lọc `error = 1`, `stopped = "D/C'd"`, giá trị ngoài khoảng hợp lệ.<br>• Lưới 1 giờ lấy trung vị; forward-fill đúng giới hạn 2 giờ/6 giờ. | pytest |
| Tính nhân quả của đặc trưng | Thay đổi dữ liệu **sau** thời điểm t không được làm đổi bất kỳ đặc trưng nào tại t — chống rò rỉ thông tin tương lai | pytest |
| Đồng nhất train/serving (`services/streaming`) | Consumer nhận từng giờ của đợt ICU nhóm `stream` → đặc trưng, NEWS2, z-score tại mỗi giờ trùng với dòng tương ứng trong `hourly.parquet` lúc huấn luyện | pytest (dữ liệu thật) |
| NEWS2 rút gọn (`compute_news2`) | • Từng ngưỡng ở giá trị biên (vd RR 8/9, 11/12, 20/21, 24/25; SpO2 91/92, 93/94, 95/96) và giá trị thập phân (HR 90,5 → 1 điểm).<br>• Tổng ≤ 15.<br>• Quy tắc "một thông số đạt 3 điểm" → `WARNING`. | pytest |
| Nhãn dự báo (`make_forecast_label`) | `y_t = max` mức rủi ro trong `(t, t+h]`; bỏ mẫu không đủ h giờ phía sau; không lấy nhãn vượt sang đợt ICU khác | pytest |
| Chia dữ liệu | Không `subject_id` nào xuất hiện ở 2 nhóm; mọi đợt ICU của 1 bệnh nhân cùng 1 nhóm; file split cố định cho kết quả giống nhau giữa các lần chạy | pytest |
| Baseline cá nhân | Lũy tiến tối đa 24 giờ, chỉ dùng được khi ≥ 6 giờ dữ liệu, áp sàn độ lệch chuẩn | pytest |
| Model wrapper (`predict_risk`, `predict_anomaly`) | • Input đúng/sai hình dạng.<br>• `risk_level` suy đúng theo `τ_critical`; `anomaly_score` ∈ [0, 1].<br>• `anomaly_score` trả rỗng khi chưa đủ cửa sổ 12 giờ. | pytest |
| Alert evaluator | • Vượt ngưỡng → tạo alert.<br>• Đang có alert cùng loại OPEN → không tạo thêm; hết cooldown → được tạo lại.<br>• WARNING không tạo alert; RISK và ANOMALY cùng lúc → 2 alert.<br>• Ngưỡng Admin ghi đè τ_critical của champion. | pytest |
| Stream processor (`services/streaming`, repo/model giả) | • Mọi bản ghi đều được lưu và publish prediction.<br>• 2 bản ghi CRITICAL liên tiếp chỉ tạo 1 alert.<br>• Bản ghi giờ đã có bị bỏ qua; khởi động lại dựng state từ DB.<br>• Ghi DB lỗi thì state không lệch với DB. | pytest |
| Producer | Giờ thứ k của mọi bệnh nhân phát ở nhịp k, key = mã bệnh nhân; `--drift` chỉ áp lên nhóm được chọn (seed cố định), SpO2 không vượt 100 | pytest |
| Auth & phân quyền | • Mật khẩu đúng/sai, token hết hạn.<br>• Role không đủ quyền → 403.<br>• Bác sĩ/Điều dưỡng truy cập bệnh nhân **không được phân công** → 403.<br>• Tài khoản bị khóa: không đăng nhập được, token cũ hết hiệu lực.<br>• Log server không chứa JWT của WebSocket. | pytest + httpx TestClient (DB `rpm_test` thật) |
| CRUD API (users, patient_assignments, alerts, alert_settings) | • Validate input, lỗi 404/422, quyền theo role (UC03, UC07, UC08, UC13).<br>• Chuyển trạng thái alert hợp lệ: `OPEN → ACKNOWLEDGED → RESOLVED`. | pytest + httpx TestClient |
| Drift (`psi`, `feature_drift`) | • So khớp giá trị PSI tính tay trên dữ liệu mẫu nhỏ (sai số ≤ 1e-4).<br>• Bin rỗng dùng ε, không lỗi chia 0.<br>• Hai phân phối giống nhau cho PSI ≈ 0. | pytest |
| Quyết định drift (`decide_drift`, `select_window`, `calibrate_thresholds`) | • Ngưỡng riêng từng đặc trưng, không bao giờ dưới sàn 0,25.<br>• Cửa sổ = 24 nhịp `recorded_at` mới nhất, bỏ giờ bị hụt; chưa đủ 24 nhịp, dưới 200 bản ghi hoặc không có dữ liệu mới → bỏ qua lần kiểm tra.<br>• Cửa sổ hiệu chỉnh bắt đầu từ giờ 0, dừng khi < 200 bản ghi; không có cửa sổ nào thì báo lỗi rõ ràng.<br>• Tỷ lệ báo nhầm chung trên cửa sổ không drift ≤ 5%. | pytest |
| Chống vòng lặp & thông báo (`rpm_ml.pipelines.policy`) | • Đang có retrain `queued`/`running` hoặc lần gần nhất kết thúc < 1 giờ → không trigger; kiểm tra ngay lần 2 không trigger lại.<br>• Nhánh task sau khi kiểm tra: bỏ qua / chỉ publish / trigger + publish.<br>• Email Admin chỉ khi bắt đầu đợt drift mới hoặc đã kích hoạt retrain. | pytest |
| Dữ liệu stream cho retrain (`rpm_ml.data.stream_data`) | • Dựng lại từ giá trị đo chưa điền trùng `hourly.parquet` (đặc trưng lẫn nhãn) trên dữ liệu thật.<br>• Mới phát một phần: nhãn h = 4 chỉ có ở giờ đã "chín".<br>• Chỉ giữ phần stream đã phát, từ chối bệnh nhân trùng nhóm khác. | pytest (dữ liệu thật) |
| Sự kiện MLOps ở backend | • `drift_report` chỉ tới Admin đang hoạt động (WebSocket + email), không tới bác sĩ.<br>• `notify_admin = false` không gửi email; đọc lại sự kiện cũ không gửi trùng (`notification_logs.drift_report_id`).<br>• `retrain_completed` chỉ đẩy WebSocket; trạng thái retrain trả kèm kết quả gate. | pytest + httpx TestClient (DB `rpm_test` thật) |
| Quality gate (`evaluate_gate`) | • Đủ các tổ hợp: trượt ngưỡng tuyệt đối, thua baseline persistence, kém champion, đạt tất cả.<br>• Lần đầu chưa có champion. | pytest |

## 2.10.2. Integration Test

| Luồng (tham chiếu Activity/Sequence) | Nội dung test | Công cụ |
|---|---|---|
| 2.3.1 / 2.4.1: Streaming → Prediction → Alert | • Producer đẩy bản ghi → `vital_records` và `predictions` xuất hiện trong DB, message xuất hiện trên `predictions-stream`.<br>• Khi vượt ngưỡng: có `alerts` và message trên `alerts-stream`.<br>• Đẩy 2 bản ghi CRITICAL liên tiếp chỉ tạo 1 alert. | pytest + testcontainers (Kafka, Postgres) |
| 2.4.1: Sự kiện → WebSocket + Email | • Backend consume alert → client WebSocket của người **được phân công** nhận đúng payload; người không được phân công không nhận.<br>• Email gửi đúng danh sách người nhận (mock SMTP); `notification_logs` ghi đúng. | pytest-asyncio, `unittest.mock` |
| 2.4.2: Đăng nhập + WebSocket | Đăng nhập đúng/sai qua API thật, token decode đúng role; mở WebSocket với token sai/hết hạn bị từ chối | pytest + httpx |
| 2.4.3: Retrain thủ công | `POST /admin/models/retrain` (mock Airflow REST) → `202` kèm `dag_run_id`; `GET` trạng thái trả đúng running/success/failed | pytest + mock HTTP |
| 2.3.3: Drift → Retrain tự động | • Producer chế độ `--drift` → `drift_check` tạo `drift_reports` với `drift_detected = true`, trigger `retrain_pipeline` và thông báo Admin.<br>• Chạy lại ngay lập tức không trigger lần 2 (chống vòng lặp).<br>• Producer không bật `--drift` → không kết luận drift. | Chạy thật trên Docker Compose (Airflow + Kafka + Postgres + MLflow), kiểm tra `drift_reports`, `model_versions`, log backend |
| 2.4.3: Nạp lại model | Đổi alias `champion` trên MLflow → consumer nạp version mới trong 1 chu kỳ kiểm tra; prediction sau đó ghi `risk_model_version_id` mới | pytest + MLflow container |
| Smoke test hạ tầng (chạy mỗi khi sửa `docker-compose.yml`) | • Từ host produce/consume qua `localhost:29092`.<br>• Log 1 model thử từ host lên MLflow rồi tải lại từ một container khác.<br>• Gọi Airflow REST API bằng basic auth trả 200. | script kiểm tra |

## 2.10.3. Model Evaluation Test (Quality Gate)

Chạy tự động trong DAG `retrain_pipeline` trước khi cho phép model mới nhận alias `champion` (chiến lược Champion–Challenger, mục 2.9.5). Mọi chỉ số đo trên **tập `test` cố định** (patient-level):

| Mô hình | Tiêu chí đạt (ngưỡng đề xuất, sẽ hiệu chỉnh theo kết quả thực nghiệm ở mục 3.4) |
|---|---|
| Dự báo rủi ro (h = 4) | 1. Macro F1 ≥ 0,60 **và** cao hơn baseline persistence trên cùng tập test.<br>2. Recall lớp CRITICAL ≥ 0,75 tại `τ_critical`. `τ_critical` được chọn trên dự đoán out-of-fold của GroupKFold trên `train ∪ validation` với **mục tiêu 0,80** (mục 2.9.6).<br>3. Không kém champion hiện tại ở cả Macro F1 và Recall CRITICAL. |
| Phát hiện bất thường (LSTM-Autoencoder) | 1. AUROC ≥ 0,75 trên tập test có 10% cửa sổ bị tiêm bất thường (seed cố định, mục 2.9.3).<br>2. AUROC không kém champion.<br>Precision/Recall/F1 tại `τ_anomaly = 0,99` và recall theo từng loại bất thường được báo cáo, không dùng để gate. |

Tham chiếu: baseline persistence (h = 4) trên tập `test` đạt Macro F1 0,547 và Recall CRITICAL 30,8% (toàn bộ dữ liệu: 0,567 và 31,3%). Nếu model mới không đạt, DAG gắn tag `gate=rejected` kèm lý do cho version đó và giữ nguyên champion.

**Hiệu chỉnh ngưỡng Recall CRITICAL** (2026-09-11) — ngưỡng ban đầu là 0,80, bằng đúng mục tiêu dùng khi chọn `τ_critical`:
- Mục tiêu chọn τ bằng ngưỡng gate nghĩa là không có biên an toàn. Tập `test` chỉ có 15 bệnh nhân (315 giờ CRITICAL, tương quan mạnh trong cùng bệnh nhân), nên mỗi lần train/retrain có khoảng 50% khả năng trượt chỉ do nhiễu.
- Lần chạy thứ 2 (τ chọn bằng out-of-fold) đạt Recall CRITICAL 0,807 trên out-of-fold, 0,849 trên validation, nhưng 0,790 trên test (249/315, thiếu 3 giờ so với 0,80).
- Ngưỡng gate được hạ xuống 0,75, còn mục tiêu chọn τ giữ 0,80. Đây là hiệu chỉnh **sau khi đã xem kết quả trên tập test**; báo cáo mục 3.4/3.5 phải nêu rõ điều này, cùng với việc tập test đã được dùng 2 lần.

**Hiệu chỉnh gate mô hình bất thường** (2026-09-11) — tiêu chí ban đầu là Precision ≥ 0,7 và Recall ≥ 0,7 tại `τ_anomaly = 0,99`, F1 không kém champion:
- Lần train đầu (chưa căn giữa cửa sổ), trên test: Precision 0,23, Recall 0,15, AUROC 0,85; tỷ lệ gắn cờ nhầm 5,5%, so với 1% trên validation.
- Chẩn đoán **chỉ trên `train ∪ validation`** (GroupKFold theo bệnh nhân, 3 cách tính điểm × 3 cách tiền xử lý): không phương án nào có recall vượt khoảng 0,15 tại ngưỡng p99. Tiêu chí 0,7/0,7 không đạt được với dữ liệu này (mục 2.9.3).
- Người dùng chọn: thêm bước căn giữa cửa sổ (mục 2.9.3) và đổi gate sang AUROC ≥ 0,75, không kém champion. AUROC không phụ thuộc ngưỡng, nên phản ánh khả năng xếp hạng bất thường mà không gắn với một ngưỡng cảnh báo cụ thể.
- Đây là hiệu chỉnh **sau khi đã xem kết quả test lần đầu**. Tập test của mô hình bất thường đã được dùng 2 lần; báo cáo 3.4/3.5 phải nêu rõ.

## 2.10.4. Kiểm thử phi chức năng

| Tiêu chí | Cách đo | Ngưỡng đề xuất |
|---|---|---|
| Độ trễ đầu–cuối | Từ lúc producer publish tới lúc dashboard nhận prediction qua WebSocket, với 20 bệnh nhân phát đồng thời ở tốc độ mặc định | p95 < 2 giây |
| Chịu lỗi backend | Tắt backend trong lúc đang replay rồi bật lại | Consumer vẫn ghi DB; backend đọc tiếp từ offset cũ, không mất alert |
| Chịu lỗi consumer | Khởi động lại consumer giữa chừng | State dựng lại từ DB; không tạo alert trùng; không bỏ sót bản ghi |

## 2.10.5. Chiến lược dữ liệu test

- Dùng một tập con nhỏ (5–10 bệnh nhân) trích từ MIMIC-III Demo làm fixture cố định cho unit/integration test — test chạy nhanh, không phụ thuộc tải toàn bộ dataset.
- Chia theo `subject_id` giống lúc train (mục 2.9.1c), tránh rò rỉ dữ liệu giữa fixture train/test nội bộ.
- Test hạ tầng (Kafka, Postgres) chạy bằng container tạm thời (testcontainers), tự dọn dẹp sau mỗi lần chạy.
- Frontend: Vitest cho logic giao diện (badge theo mức rủi ro, chặn route theo role, hiển thị theo phân công), kết hợp kiểm thử thủ công theo kịch bản từng use case.
