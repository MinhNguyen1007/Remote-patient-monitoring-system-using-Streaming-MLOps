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
alembic revision --autogenerate -m "..."
alembic upgrade head
```
