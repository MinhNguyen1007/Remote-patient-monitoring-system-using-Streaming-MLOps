# CLAUDE.md — backend/

FastAPI. Xem kiến trúc tổng thể ở `../CLAUDE.md` và thiết kế chi tiết ở `../docs/design/`.

## Cấu trúc

```
app/
  api/          Routers: auth, patients, alerts, assignments, settings, admin/models, ws (WebSocket)
  db/           SQLAlchemy models + CRUD, khớp với docs/design/02_7_erd.md
  events/       Kafka consumer đọc predictions-stream + alerts-stream → đẩy WebSocket, gọi notification
  services/     notification (gửi email bất đồng bộ + ghi notification_logs), airflow_client (REST API)
  alembic/      Database migration
tests/          pytest (unit + integration), xem docs/design/02_10_thiet_ke_test.md
```

**Đã có từ Giai đoạn D** (vì consumer cần bảng để ghi): `app/db/models.py` (toàn bộ bảng theo ERD), `app/db/url.py`, `alembic.ini`, migration `0001` (tạo hypertable `vital_records`, `predictions`). Phần API, WebSocket, email làm ở Giai đoạn E.
- `alembic.ini` phải giữ **chỉ ký tự ASCII**: Alembic đọc file bằng encoding của hệ điều hành (cp1252 trên Windows).
- `alembic check` bỏ qua 2 index TimescaleDB tự tạo (`*_recorded_at_idx`), cấu hình trong `app/alembic/env.py`.
- Consumer (`../streaming/`) ghi trực tiếp bằng SQL vào patients, vital_records, predictions, alerts, model_versions và seed alert_settings — đổi tên cột phải sửa cả `streaming/src/repository.py`.

Backend **không chạy model và không chạy job định kỳ**:
- Suy luận realtime nằm trong stream consumer (`../streaming/`).
- Kiểm tra drift và retrain nằm trong Airflow DAG.

## Quy ước

- Mọi model SQLAlchemy trong `db/models.py` phải khớp đúng entity/attribute trong `docs/design/02_5_class.md` và `02_7_erd.md` — nếu cần thêm cột, cập nhật ERD trước.
  - `vital_records`/`predictions` là hypertable: khóa chính phải chứa `recorded_at`.
  - Tham chiếu vào hypertable là tham chiếu logic, không tạo FK constraint.
- Mọi endpoint mới phải khai báo rõ role được phép truy cập (`Depends(require_role(...))`) theo đúng phân quyền ở `docs/design/02_2_usecase.md`.
- **Phân quyền theo phân công**: Bác sĩ/Điều dưỡng chỉ đọc được bệnh nhân có trong `patient_assignments` của mình.
  - Truy cập bệnh nhân khác → 403.
  - WebSocket phải xác thực JWT và chỉ đẩy sự kiện của bệnh nhân được phân công.
- Response model dùng Pydantic schema riêng (không trả thẳng SQLAlchemy model).
- Alert do consumer tạo (theo `docs/design/02_3_activity.md` mục 2.3.1, có chống trùng/cooldown).
  - Backend chỉ nhận sự kiện từ Kafka rồi đẩy WebSocket và gửi email tới người được phân công.
  - **Backend là nơi duy nhất gửi email.**
- `POST /admin/models/retrain` gọi Airflow REST API (`AIRFLOW_API_URL`, basic auth), trả `202` kèm `dag_run_id`; trạng thái lấy qua `GET` — không giữ request chờ DAG chạy xong.
- Test mới thêm phải map được tới 1 dòng trong bảng test ở `docs/design/02_10_thiet_ke_test.md`; nếu là ca test mới chưa có trong bảng, bổ sung vào bảng đó trước.

## Lệnh

```bash
uvicorn app.main:app --reload --port 8000
pytest
# Trên host cần POSTGRES_HOST=localhost (mặc định .env là hostname docker "postgres")
POSTGRES_HOST=localhost ../.venv/Scripts/python -m alembic revision --autogenerate -m "..."
POSTGRES_HOST=localhost ../.venv/Scripts/python -m alembic upgrade head
POSTGRES_HOST=localhost ../.venv/Scripts/python -m alembic check
```
