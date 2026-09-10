# Hệ thống giám sát bệnh nhân từ xa bằng Streaming + MLOps

Đồ án môn học: hệ thống giám sát bệnh nhân realtime kết hợp Apache Kafka (streaming), FastAPI + React (ứng dụng), và vòng lặp MLOps đầy đủ (MLflow tracking/registry, drift detection, Apache Airflow retrain).

Tài liệu thiết kế đầy đủ (mục 1-2 theo khung báo cáo): xem [`docs/design/`](docs/design/).

## Trạng thái hiện tại

- ✅ Giai đoạn A — Thiết kế (toàn bộ sơ đồ UML/DFD/ERD, thiết kế giải thuật, thiết kế test)
- ✅ Giai đoạn B — Khung repo & hạ tầng nền (đang thực hiện)
- ⬜ Giai đoạn C — Dữ liệu & huấn luyện model
- ⬜ Giai đoạn D — Streaming (Kafka producer/consumer)
- ⬜ Giai đoạn E — Backend (FastAPI)
- ⬜ Giai đoạn F — Frontend (React)
- ⬜ Giai đoạn G — MLOps vận hành (drift + Airflow)
- ⬜ Giai đoạn H — Testing
- ⬜ Giai đoạn I — Viết báo cáo hoàn chỉnh

## Cấu trúc thư mục

```
backend/        FastAPI app (API, DB models, ML inference wrapper, scheduler)
frontend/       React dashboard
ml/             Notebook EDA, script train/evaluate model, log MLflow
streaming/      Kafka producer (replay dataset) & consumer (inference realtime)
infra/          Docker, Prometheus/Grafana, Airflow DAGs, Postgres init scripts
docs/design/    Toàn bộ tài liệu thiết kế (mục 1-2 báo cáo), sơ đồ Mermaid
```

## Chạy hạ tầng nền (Giai đoạn B)

```bash
cp .env.example .env   # rồi chỉnh giá trị thật (mật khẩu, SMTP...)
docker compose up -d postgres zookeeper kafka mlflow prometheus grafana
docker compose up -d airflow-init && docker compose up -d airflow-webserver airflow-scheduler
```

- Postgres: `localhost:5432`
- Kafka (từ host): `localhost:29092`
- MLflow UI: http://localhost:5000
- Airflow UI: http://localhost:8080 (user/pass theo `.env`)
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3001

Service `backend`, `frontend`, `kafka-producer`, `kafka-consumer` sẽ được thêm vào `docker-compose.yml` ở các giai đoạn D/E/F khi đã có Dockerfile + code tương ứng.

## Dataset

MIMIC-III Clinical Database Demo (PhysioNet, open license) — xem chi tiết cách tải và tiền xử lý ở `ml/README.md` (sẽ tạo ở Giai đoạn C).
