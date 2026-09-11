# Hệ thống giám sát bệnh nhân từ xa bằng Streaming + MLOps

Đồ án môn học. Vitals ICU thật (MIMIC-III Demo) được phát lại qua **Kafka** như bệnh nhân đang nằm viện; mỗi giờ dữ liệu được
dự báo rủi ro 4 giờ tới và chấm điểm bất thường, cảnh báo đẩy realtime tới đúng bác sĩ/điều dưỡng phụ trách. Vòng lặp
**MLOps** tự phát hiện drift, huấn luyện lại và chỉ thay model khi đạt quality gate.

```
MIMIC-III Demo ─► producer ─► Kafka ─► consumer (đặc trưng → 2 model champion → cảnh báo) ─► PostgreSQL/TimescaleDB
                                                                    │
                          React dashboard ◄─ WebSocket ◄─ FastAPI ◄─┘  (email tới người được phân công)
MLflow (tracking + registry) ◄─ Airflow: drift_check (PSI/KS) ─► retrain_pipeline ─► quality gate ─► alias champion
```

## Cấu trúc thư mục

```
services/                 Các service chạy thật (mỗi service có Dockerfile, requirements, test, CLAUDE.md)
  backend/                FastAPI: REST + WebSocket + JWT, email, gọi Airflow           (app/, tests/, alembic)
  frontend/               React dashboard realtime                                    (src/pages, src/components)
  streaming/              Kafka producer phát lại + stream consumer suy luận            (src/rpm_streaming/)
ml/                       Dữ liệu, huấn luyện, đánh giá, drift, retrain                 (src/rpm_ml/)
packages/common/          rpm_common: làm sạch, lưới giờ, NEWS2, đặc trưng — dùng chung cho train và streaming
infra/                    Docker (MLflow, Airflow), Airflow DAG, Prometheus/Grafana, script khởi tạo Postgres
docs/                     Thiết kế (design/, mục 1–2 báo cáo) và ghi chú viết báo cáo (report/)
docker-compose.yml        Toàn bộ hệ thống; service ứng dụng nằm trong profile "app"
```

Bên trong hai package Python chính, code chia theo chức năng:

```
ml/src/rpm_ml/            data/  models/  training/  evaluation/  drift/  pipelines/  storage/  paths.py
services/streaming/src/rpm_streaming/
                          producer/  consumer/  kafka/  storage/  config.py
```

## Chạy nhanh

```bash
cp .env.example .env                                       # rồi đặt mật khẩu thật
docker compose up -d postgres zookeeper kafka mlflow       # hạ tầng nền
docker compose up -d airflow-webserver airflow-scheduler   # DAG drift_check (2 phút/lần), retrain_pipeline
docker compose --profile app up -d                         # backend :8000, frontend :3000, stream-consumer
docker compose --profile app run --rm stream-producer      # phát lại 20 bệnh nhân (thêm --drift để mô phỏng drift)
```

| Giao diện | Địa chỉ |
|---|---|
| Dashboard | http://localhost:3000 |
| API (Swagger) | http://localhost:8000/docs |
| MLflow | http://localhost:5000 |
| Airflow | http://localhost:8080 |
| Grafana / Prometheus | http://localhost:3001 / http://localhost:9090 |

Phát triển trên máy (không Docker): tạo `.venv` rồi `pip install -e packages/common -e ml -e services/streaming`
cùng các `requirements.txt`; lệnh chi tiết ở `CLAUDE.md` gốc và `CLAUDE.md` của từng thư mục.

## Tài liệu

- Thiết kế đầy đủ: [`docs/design/`](docs/design/) — chức năng, use case, activity, sequence, class, DFD, ERD, giao diện, giải thuật, test.
- Dataset (nguồn, giấy phép, mapping itemid, trích dẫn bắt buộc): [`ml/README.md`](ml/README.md), từ điển dữ liệu [`ml/data_dictionary.md`](ml/data_dictionary.md).
- Kết quả mô hình: [`ml/reports/evaluation.md`](ml/reports/evaluation.md); số liệu cho báo cáo: [`docs/report/ghi_chu_bao_cao.md`](docs/report/ghi_chu_bao_cao.md).
- Tiến độ và quyết định đã chốt: mục "Trạng thái hiện tại" trong [`CLAUDE.md`](CLAUDE.md).
