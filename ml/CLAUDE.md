# CLAUDE.md — ml/

Xem thiết kế giải thuật chi tiết ở `../docs/design/02_9_thiet_ke_giai_thuat.md` — mọi thay đổi kiến trúc model phải đối chiếu/cập nhật tài liệu đó. Mapping itemid, quy tắc làm sạch và đặc điểm dataset: `README.md` mục 4 và 6.

## Cấu trúc

```
src/rpm_ml/                 Package cài bằng `pip install -e ml` (chạy mọi script dạng `python -m rpm_ml.<...>`)
  paths.py                  Mọi đường dẫn dữ liệu/kết quả (data/raw, data/processed, splits, reports, .env)
  data/
    preprocess.py           MIMIC-III Demo → rpm_common (làm sạch, lưới 1 giờ, NEWS2, đặc trưng, baseline) → nhãn h=1/h=4,
                            nhóm chia dữ liệu → hourly.parquet, stream_replay.parquet
    split.py                Chia 4 nhóm theo subject_id (phân tầng theo tử vong tại viện), đọc/ghi file cố định
    stream_data.py          vital_records (DB) → bảng theo giờ giống hourly.parquet + nhãn đã "chín" (drift, retrain)
  models/
    risk.py                 Ứng viên LogisticRegression/RandomForest/XGBoost, trọng số lớp, GroupKFold (+ xác suất OOF)
    anomaly.py              Kiến trúc LSTM-AE + wrapper MLflow pyfunc (cửa sổ z-score gốc → anomaly_score)
  training/
    train_risk.py           Mô hình rủi ro: CV chọn họ mô hình, τ_critical trên out-of-fold, gate, đăng ký `risk_classifier`
                            (+ reference_stats.json, drift_thresholds.json); `train_risk_model` dùng chung cho retrain
    train_anomaly.py        LSTM-AE: train trên cửa sổ NORMAL, gate AUROC, đăng ký `anomaly_detector`; `train_anomaly_model`
    repackage_anomaly.py    Đóng gói lại 1 version với code wrapper mới, giữ nguyên trọng số
  evaluation/
    metrics.py              Metric phân loại, chọn τ_critical, metric bất thường
    gate.py                 Quality gate cho cả 2 mô hình (ngưỡng — không đổi khi chưa hỏi người dùng)
    injection.py            Tiêm bất thường spike / level shift / drift, σ theo kênh từ nhóm train
    report.py               Bảng/hình báo cáo 3.4/3.5 → reports/ (chỉ đọc champion + metric đã log)
  drift/
    stats.py                reference_stats, PSI, KS, cửa sổ 24 nhịp, ngưỡng hiệu chỉnh (`calibrate_thresholds`), `decide_drift`
    detect.py               Các bước DAG drift_check: `detect`, `publish`, `backfill-thresholds`
  pipelines/
    retrain.py              Các bước DAG retrain_pipeline: build / risk / anomaly / publish
    policy.py               Chỉ thư viện chuẩn (file DAG import trực tiếp): chống vòng lặp 1 giờ, nhánh task, quy tắc email
  storage/
    db.py                   SQL vào drift_reports, model_versions (schema do Alembic ở services/backend quản lý)
    events.py               Publish sự kiện lên Kafka topic mlops-events (backend gửi email/WebSocket cho Admin)
tests/                      pytest (61 test), import theo `rpm_ml.<...>`
data/raw/                   Dataset MIMIC-III Demo gốc (không nằm trong git — tải theo README.md)
data/processed/             Đầu ra của preprocess (không nằm trong git)
splits/                     Danh sách subject_id của 4 nhóm train/validation/test/stream (commit vào git)
reports/                    Đầu ra của evaluation/report.py (evaluation.md, evaluation_summary.json, fig_*.png) — commit vào
                            git; chạy lại mỗi khi champion đổi
notebooks/                  EDA, thử nghiệm trước khi đưa vào src/
```

Code tính đặc trưng (NEWS2, cửa sổ, baseline, mapping itemid) **không đặt trong `ml/`**. Nó nằm ở package dùng chung `../packages/common` (`rpm_common`), được import bởi cả `ml/` và `services/streaming`, để lúc train và lúc suy luận realtime tính giống hệt nhau.

## Quy ước bắt buộc

- **Chia dữ liệu theo `subject_id`** (không phải `icustay_id`/`hadm_id` — 19 bệnh nhân có nhiều đợt ICU). Có 4 nhóm cố định (48/15/15/20 trên 98 bệnh nhân có vitals) lưu ở `splits/subject_split.json` — không tạo lại file này.
  - Nhóm `test` chỉ dùng cho quality gate và báo cáo cuối.
  - Nhóm `stream` chỉ dùng để replay, không dùng cho huấn luyện ban đầu.
- **Nhãn rủi ro là nhãn dự báo**: `y_t` = mức NEWS2 rút gọn cao nhất trong `(t, t+h]`, mặc định h = 4. **Không bao giờ** lấy mức NEWS2 tại chính t làm nhãn, vì nhãn khi đó là hàm tất định của đặc trưng (rò rỉ nhãn).
  - NEWS2 dùng 5 thông số (0–15) kèm quy tắc "một thông số đạt 3 điểm → WARNING".
- **Mọi cửa sổ tính theo giờ dữ liệu**: rolling 6 giờ, LSTM 12 bước, baseline lũy tiến ≤ 24 giờ (≥ 6 giờ mới dùng được). Vitals trong MIMIC đo trung vị 60 phút/lần, nhiệt độ 240 phút/lần.
- **Chỉ forward-fill** (2 giờ với vitals, 6 giờ với nhiệt độ), **không nội suy** — nội suy dùng dữ liệu tương lai mà streaming không có.
- **Luôn báo baseline persistence** (dự báo = mức hiện tại) cạnh model; model phải thắng baseline. Tham chiếu h = 4 trên tập `test`: Macro F1 0,547, Recall CRITICAL 30,8%.
- Đối chiếu nhãn proxy với `hospital_expire_flag` (không dùng "chuyển ICU" — mọi dữ liệu đã là ICU). Ghi kết quả vào báo cáo 3.5, kèm thiên lệch chọn mẫu: cả 100 bệnh nhân Demo đều về sau đã tử vong.
- **LSTM-Autoencoder** chỉ train trên cửa sổ mà cả 12 giờ đều NORMAL, 6 kênh.
  - Cửa sổ được **căn giữa theo từng kênh** (`rpm_common.anomaly.center_windows`) trước khi vào autoencoder; việc này làm bên trong `fit_autoencoder`/`window_mse`/wrapper, nên nơi gọi luôn truyền cửa sổ z-score gốc của `make_windows`.
  - `anomaly_score` = hàm phân phối tích lũy thực nghiệm của MSE trên cửa sổ NORMAL tập validation, nằm trong [0, 1]. Được lưu kèm model (`mse_reference.npy` trong model pyfunc).
- Đánh giá anomaly bằng synthetic injection: 10% cửa sổ, 3 loại spike / level shift / drift dần, seed cố định, σ theo kênh từ nhóm train — xem 02_9 mục 2.9.3. Gate dùng **AUROC** (02_10 mục 2.10.3); P/R/F1 tại τ = 0,99 chỉ báo cáo.
- Script tạm dùng TensorFlow trên Windows: nếu gặp lỗi DLL `_pywrap_tensorflow_internal`, `import tensorflow` trước sklearn/scipy.
- **Model pyfunc log từ Windows**: MLflow ghi đường dẫn artifact với dấu `\` (`artifactsutoencoder.keras`), container Linux không mở được.
  - Wrapper luôn đọc artifact qua `artifact_path()` (đổi `\` → `/`).
  - Code wrapper được chụp kèm model (`code_paths`), nên sửa `models/anomaly.py` **không** tác động tới version đã đăng ký. Muốn áp dụng cho version cũ thì chạy `training/repackage_anomaly.py`.
  - Wrapper được pickle theo tên module `rpm_ml.models.anomaly`: `serving_code_paths()` chụp kèm đúng khung `rpm_ml/models/anomaly.py`, nên consumer không cần cài `rpm_ml`. Version ≤ v5 mang file `anomaly_model.py` riêng (tên module cũ) và vẫn nạp được.
  - Sau mỗi lần train cần kiểm tra nạp model trong container (`docker compose --profile app up -d stream-consumer`).
- Mọi lần train phải log vào MLflow (params, metrics, artifact, `reference_stats.json` cho drift) — không train "chui" ngoài tracking.
- **Drift** (02_9 mục 2.9.4): quyết định bằng ngưỡng PSI **hiệu chỉnh theo từng đặc trưng** (sàn 0,25), không dùng
  một ngưỡng 0,25 chung — với cửa sổ ~20 bệnh nhân, ngưỡng chung gắn cờ 93% cửa sổ không drift. Model rủi ro nào được
  đăng ký cũng phải log `reference_stats.json` + `drift_thresholds.json` (`training/train_risk.py` tự làm; tốn thêm ~1 phút).
- **Retrain** dùng lại đúng hàm huấn luyện ban đầu với `training_groups=("train", "stream")`; dữ liệu stream chỉ gồm phần
  đã thực sự phát (dựng lại từ DB). σ tiêm bất thường luôn lấy từ nhóm `train` cố định. validation/test không đổi.
- **Promote bằng alias `champion`**, không dùng stage `Production` (đã lỗi thời từ MLflow 2.9). Mỗi challenger đều được đăng ký version; chỉ chuyển alias khi đạt quality gate:
  - ngưỡng tuyệt đối ở 02_10 mục 2.10.3;
  - thắng baseline persistence;
  - không kém champion khi **đánh giá lại cả hai trên cùng tập test cố định**.
  - Không đạt thì gắn tag `gate=rejected` kèm lý do.

## Lệnh

```bash
# Môi trường (từ gốc repo, một lần): venv + các package nội bộ ở chế độ editable
python -m venv .venv
.venv\Scripts\python -m pip install -e packages/common -e ml -r ml/requirements.txt

# Test
cd ml && ..\.venv\Scripts\python -m pytest -q && cd ..

# Tiền xử lý → ml/data/processed/{hourly,stream_replay}.parquet + summary.json
.venv\Scripts\python -m rpm_ml.data.preprocess

# Huấn luyện/đánh giá — chạy trên host cần MLFLOW_TRACKING_URI=http://localhost:5000 (không phải http://mlflow:5000)
.venv\Scripts\python -m rpm_ml.training.train_risk
.venv\Scripts\python -m rpm_ml.training.train_anomaly
.venv\Scripts\python -m rpm_ml.evaluation.report

# Drift/retrain (thường do Airflow chạy trong image rpm-airflow; trên host cần thêm POSTGRES_HOST=localhost
# KAFKA_BOOTSTRAP_SERVERS=localhost:29092)
.venv\Scripts\python -m rpm_ml.drift.detect detect
.venv\Scripts\python -m rpm_ml.drift.detect backfill-thresholds     # champion train trước Giai đoạn G
.venv\Scripts\python -m rpm_ml.pipelines.retrain build --runs-dir <thư mục tạm> --dag-run-id manual__thu
```

Image Airflow (`infra/Dockerfile.airflow`) cài `ml/requirements.txt` trừ `shap`, `pytest` vào venv riêng và cài `rpm_ml` dạng
editable ở `/opt/rpm/ml`: `shap 0.51` khai báo cần numpy ≥ 2, xung đột với numpy 1.26 đã ghim (máy phát triển chạy được nhờ
venv dùng chung site-packages). Sửa code trong `ml/src` hoặc `packages/common` thì phải build lại image
(`docker compose build airflow-scheduler`).

Máy phát triển hiện tại tạo venv bằng `--system-site-packages` để dùng lại thư viện đã cài sẵn (mạng chậm); phiên bản trong
`requirements.txt` là phiên bản đã kiểm chứng trên máy đó. Cài package nội bộ không cần mạng:
`pip install --no-build-isolation --no-deps -e packages/common -e ml -e services/streaming`.
