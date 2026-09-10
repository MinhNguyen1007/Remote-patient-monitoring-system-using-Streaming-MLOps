# Hệ thống giám sát bệnh nhân từ xa bằng Streaming + MLOps

Đồ án môn học: hệ thống giám sát bệnh nhân realtime kết hợp Apache Kafka (streaming), FastAPI + React (ứng dụng), và vòng lặp MLOps đầy đủ (MLflow tracking/registry, drift detection, Apache Airflow retrain).

Tài liệu thiết kế đầy đủ (mục 1-2 theo khung báo cáo): xem [`docs/design/`](docs/design/).

## Trạng thái hiện tại

> Xem `CLAUDE.md` mục "Trạng thái hiện tại" để biết chi tiết bước tiếp theo cần làm.

- ✅ Giai đoạn A — Thiết kế (toàn bộ sơ đồ UML/DFD/ERD, thiết kế giải thuật, thiết kế test)
- ✅ Giai đoạn B — Khung repo & hạ tầng nền (đã smoke test thật: Kafka từ host, MLflow log/tải model qua proxy artifact, Airflow REST API)
- ✅ Rà soát toàn bộ thiết kế + dữ liệu thật (2026-09-10) — đã sửa thiết kế giải thuật, sơ đồ, ERD, hạ tầng
- 🔶 Giai đoạn C — Dữ liệu & huấn luyện model (dataset và thiết kế đã chốt, chưa viết code `common/rpm_common` + preprocess/train)
- ⬜ Giai đoạn D — Streaming (Kafka producer/consumer)
- ⬜ Giai đoạn E — Backend (FastAPI)
- ⬜ Giai đoạn F — Frontend (React)
- ⬜ Giai đoạn G — MLOps vận hành (drift + Airflow)
- ⬜ Giai đoạn H — Testing
- ⬜ Giai đoạn I — Viết báo cáo hoàn chỉnh

## Cấu trúc thư mục

```
common/         Package Python dùng chung (rpm_common): mapping itemid, làm sạch, NEWS2, feature — import bởi ml/ và streaming/
backend/        FastAPI app (API, DB models, WebSocket, nhận sự kiện Kafka, gửi email, gọi Airflow REST)
frontend/       React dashboard
ml/             Notebook EDA, script preprocess/train/evaluate/retrain, log MLflow
streaming/      Kafka producer (replay dữ liệu đã tiền xử lý) & consumer (feature + suy luận realtime + tạo alert)
infra/          Docker, Prometheus/Grafana, Airflow DAGs (drift_check, retrain_pipeline), Postgres init scripts
docs/design/    Toàn bộ tài liệu thiết kế (mục 1-2 báo cáo), sơ đồ Mermaid
```

Các thư mục `common/`, `streaming/` được tạo khi bắt đầu viết code ở Giai đoạn C/D.

## Chạy hạ tầng nền (Giai đoạn B)

```bash
cp .env.example .env   # rồi chỉnh giá trị thật (mật khẩu, SMTP...)
docker compose up -d postgres zookeeper kafka mlflow prometheus grafana
docker compose up -d airflow-webserver airflow-scheduler   # tự chạy airflow-init (db migrate + tạo user) trước
```

- Postgres: `localhost:5432`
- Kafka (từ host): `localhost:29092` — trong mạng docker dùng `kafka:9092`
- MLflow UI: http://localhost:5000
- Airflow UI: http://localhost:8080 (user/pass theo `.env`)
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3001

Service `backend`, `frontend`, `kafka-producer`, `kafka-consumer` sẽ được thêm vào `docker-compose.yml` ở các giai đoạn D/E/F khi đã có Dockerfile + code tương ứng.

## Dataset

MIMIC-III Clinical Database Demo v1.4 (PhysioNet, open license) — xem mô tả đầy đủ, lý do lựa chọn, mapping itemid vitals và trích dẫn bắt buộc tại [`ml/README.md`](ml/README.md).
