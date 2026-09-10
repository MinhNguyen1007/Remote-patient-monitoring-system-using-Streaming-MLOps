# Hệ thống giám sát bệnh nhân từ xa bằng Streaming + MLOps

Đồ án môn học: hệ thống giám sát bệnh nhân realtime kết hợp Apache Kafka (streaming), FastAPI + React (ứng dụng), và vòng lặp MLOps đầy đủ (MLflow tracking/registry, drift detection, Apache Airflow retrain).

Tài liệu thiết kế đầy đủ (mục 1-2 theo khung báo cáo): xem [`docs/design/`](docs/design/).

## Trạng thái hiện tại

> Xem `CLAUDE.md` mục "Trạng thái hiện tại" để biết chi tiết bước tiếp theo cần làm.

- ✅ Giai đoạn A — Thiết kế (toàn bộ sơ đồ UML/DFD/ERD, thiết kế giải thuật, thiết kế test)
- ✅ Giai đoạn B — Khung repo & hạ tầng nền (đã test chạy thật: Postgres+TimescaleDB, Kafka, MLflow, Airflow, Prometheus, Grafana)
- 🔶 Giai đoạn C — Dữ liệu & huấn luyện model (dataset MIMIC-III Demo đã tải & verify, chưa viết code preprocess/train)
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

MIMIC-III Clinical Database Demo v1.4 (PhysioNet, open license) — xem mô tả đầy đủ, lý do lựa chọn, mapping itemid vitals và trích dẫn bắt buộc tại [`ml/README.md`](ml/README.md).
