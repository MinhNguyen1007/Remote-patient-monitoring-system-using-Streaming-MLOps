# CLAUDE.md — services/streaming/

Kafka producer (phát lại nhóm `stream`) và stream consumer (đặc trưng → 2 mô hình → DB + Kafka). Thiết kế: `../../docs/design/02_3_activity.md` mục 2.3.1, `02_4_sequence.md` mục 2.4.1/2.4.3, `02_9_thiet_ke_giai_thuat.md` mục 2.9.1(g), 2.9.6.

## Cấu trúc

```
src/rpm_streaming/          Package cài bằng `pip install -e services/streaming` (chạy dạng `python -m rpm_streaming.<...>`)
  config.py                 Cấu hình từ biến môi trường (.env.example); biến shell ưu tiên hơn .env
  kafka/
    topics.py               Tạo 3 topic nếu chưa có (3 partition, key = mã bệnh nhân giữ thứ tự)
    messages.py             Định dạng JSON của vitals-stream / predictions-stream / alerts-stream
  producer/
    replay.py               Replay stream_replay.parquet theo nhịp REPLAY_SECONDS_PER_DATA_HOUR, chế độ --drift
  consumer/
    main.py                 Vòng lặp Kafka + StreamProcessor (xử lý 1 message, kiểm thử được với repo/model giả)
    patient_state.py        Lịch sử giá trị đo của đợt ICU → đặc trưng bằng rpm_common (fill_forward + build_hourly_features)
    model_service.py        Nạp risk_classifier/anomaly_detector @champion theo số version, kiểm tra alias định kỳ
    alerting.py             Quyết định tạo cảnh báo: vượt ngưỡng + không có OPEN cùng loại + hết cooldown (giờ dữ liệu)
  storage/
    repository.py           SQL (psycopg2) vào schema do Alembic ở services/backend quản lý
    reset_demo.py           Xóa dữ liệu một lần phát lại (cần --yes), giữ users/model_versions/alert_settings/drift_reports
tests/                      pytest: alerting, messages, producer, model service, stream processor, đồng nhất train/serving
Dockerfile                  Image dùng chung producer/consumer (build context = gốc repo, giữ bố cục thư mục như repo)
```

## Quy ước bắt buộc

- **Không tự tính đặc trưng trong streaming**: mọi đặc trưng đi qua `rpm_common` với đúng thứ tự như `rpm_ml.data.preprocess` (lưới giờ `_obs` → `fill_forward` → `build_hourly_features`). Test `test_online_features_match_training_features_hour_by_hour` phải luôn qua.
- Producer gửi **giá trị đo chưa điền**; `vital_records` cũng lưu giá trị chưa điền. State consumer giữ cả đợt ICU và dựng lại từ toàn bộ `vital_records` khi khởi động (baseline cần 24 giờ đầu).
- Thứ tự xử lý 1 message: state → dự báo → quyết định cảnh báo → **một transaction** DB (vital_record + prediction + alert) → publish → commit offset. Không đảo thứ tự: commit offset trước khi ghi DB sẽ mất bản ghi khi consumer chết.
- `τ_critical` = `alert_settings.risk_critical_threshold` nếu Admin đặt, ngược lại tag `tau_critical` của champion. `τ_anomaly`, cooldown đọc từ `alert_settings` (đọc lại mỗi `ALERT_SETTINGS_REFRESH_SECONDS`).
- Cooldown tính bằng **giờ dữ liệu** (`hour_index`), không phải giờ đồng hồ.
- Consumer không gửi email, không đẩy WebSocket (việc của backend).
- Mô hình rủi ro suy luận 1 dòng/lần: ép `n_jobs=1` (`single_threaded`), nhanh hơn ~3 lần so với pool luồng.
- Đồng bộ champion vào `model_versions` chỉ bật cờ champion và **gộp** metric: version do DAG retrain_pipeline tạo đã có
  sẵn `trigger`, `drift_report_id`, `gate_reasons`, metric champion cũ — không ghi đè (`rpm_ml/storage/db.py` dùng chung khóa).
- `vital_records` là nguồn dữ liệu của drift_check và retrain (`rpm_ml/data/stream_data.py` dựng lại đặc trưng từ đó); mỗi
  nhịp phát lại mang cùng `recorded_at` cho mọi bệnh nhân — cửa sổ drift dựa vào điều này.
- `config.REPO_ROOT` tính từ vị trí file (4 cấp trên `config.py`); Dockerfile giữ đúng bố cục `services/streaming/src` dưới
  `/app` để tìm `ml/data/processed` như trên máy.

## Lệnh (từ gốc repo, trên host)

```bash
# Hạ tầng + schema DB
docker compose up -d postgres zookeeper kafka mlflow
cd services/backend && POSTGRES_HOST=localhost ../../.venv/Scripts/python -m alembic upgrade head && cd ../..

# Consumer và producer (host dùng localhost thay cho hostname docker)
export KAFKA_BOOTSTRAP_SERVERS=localhost:29092 MLFLOW_TRACKING_URI=http://localhost:5000 POSTGRES_HOST=localhost
.venv/Scripts/python -m rpm_streaming.consumer
.venv/Scripts/python -m rpm_streaming.producer                       # 5 giây/giờ dữ liệu (REPLAY_SECONDS_PER_DATA_HOUR)
.venv/Scripts/python -m rpm_streaming.producer --seconds-per-hour 0.3 --limit-patients 5 --max-hours 80
.venv/Scripts/python -m rpm_streaming.producer --drift --drift-fraction 0.5
.venv/Scripts/python -m rpm_streaming.storage.reset_demo --yes       # dừng consumer trước

# Docker (profile app)
docker compose --profile app up -d stream-consumer
docker compose --profile app run --rm stream-producer --seconds-per-hour 5

# Test
cd services/streaming && ../../.venv/Scripts/python -m pytest -q && cd ../..
```
