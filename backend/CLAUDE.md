# CLAUDE.md — backend/

FastAPI (REST + WebSocket + JWT). Xem kiến trúc tổng thể ở `../CLAUDE.md` và thiết kế chi tiết ở `../docs/design/`.

## Cấu trúc

```
app/
  main.py         App factory, CORS, lifespan (seed Admin, EventDispatcher, Kafka listener), /health, /metrics
  core/           config.py (pydantic-settings, đọc .env), security.py (bcrypt + JWT)
  api/deps.py     get_current_user, require_role / require_admin / require_staff / require_doctor, get_assigned_patient
  api/routers/    auth, users (UC03), patients (UC04–05), alerts (UC06–07), admin (UC08–10, UC13), ws (WebSocket)
  db/             models.py (khớp ERD), session.py, url.py, queries.py (truy vấn đọc dùng chung)
  events/         dispatcher.py (đẩy WS tới người được phân công + email), listener.py (Kafka → dispatcher, thread nền)
  services/       notification (email + notification_logs), ws_manager, airflow_client, mlflow_client (τ của champion)
  schemas/        Pydantic response/request (không trả thẳng SQLAlchemy model)
  seed.py         Admin đầu tiên (tự động lúc khởi động) + `python -m app.seed --demo`
  alembic/        Migration (0001: toàn bộ schema + hypertable)
tests/            pytest trên DB `rpm_test` thật (TimescaleDB), 30 test
Dockerfile        Chạy `alembic upgrade head` rồi uvicorn (build context = gốc repo)
```

Backend **không chạy model và không chạy job định kỳ**: suy luận nằm trong `../streaming/`, drift/retrain nằm trong Airflow DAG.

## API (cho frontend Giai đoạn F)

| Method + path | Role | Ghi chú |
|---|---|---|
| `POST /auth/login` `{email, password}` | — | → `{access_token, token_type, expires_in, user}`; sai thông tin/khóa → 401 |
| `GET /auth/me` | mọi role | UC02 đăng xuất = client xóa token (JWT không lưu phía server) |
| `GET/POST /users`, `GET/PATCH /users/{id}` | ADMIN | UC03; khóa bằng `is_active`, không xóa cứng; tự khóa/tự bỏ quyền → 409 |
| `GET /patients` | DOCTOR, NURSE | UC04: chỉ bệnh nhân được phân công, kèm `latest` (vitals **sau forward-fill** có giới hạn), `open_alerts`, `recent_risk_levels` (12 giờ), sắp theo rủi ro |
| `GET /patients/{id}`, `/timeline?hours=48`, `/alerts` | DOCTOR, NURSE | UC05–06; chi tiết kèm `news2_components` (tính bằng `rpm_common.news2`); `timeline` giữ vitals đo gốc; không được phân công → 403 |
| `GET /alerts?status=&type=&patient_id=`, `GET /alerts/open-count` | DOCTOR, NURSE | UC06, badge sidebar |
| `POST /alerts/{id}/acknowledge`, `POST /alerts/{id}/resolve {note}` | DOCTOR | UC07: OPEN → ACKNOWLEDGED → RESOLVED, sai thứ tự → 409 |
| `GET /admin/patients`, `POST /admin/assignments`, `DELETE /admin/assignments/{id}` | ADMIN | UC13; chỉ gán cho DOCTOR/NURSE (422), trùng → 409 |
| `GET/PUT /admin/alert-settings` | ADMIN | UC08; trả thêm `champion_tau_critical`, `effective_risk_threshold`; mỗi lần PUT thêm 1 bản ghi |
| `GET /admin/models`, `GET /admin/drift-reports` | ADMIN | UC09 |
| `POST /admin/models/retrain` → 202, `GET /admin/models/retrain/{dag_run_id}` | ADMIN | UC10; Airflow lỗi → 502 |
| `WS /ws?token=<JWT>` | mọi role | Sự kiện `{type, data}`: `connected`, `prediction`, `alert`, `alert_update`; token sai → đóng 1008; gửi `ping` nhận `pong` |

## Quy ước

- Mọi model SQLAlchemy trong `db/models.py` phải khớp đúng entity/attribute trong `docs/design/02_5_class.md` và `02_7_erd.md` — nếu cần thêm cột, cập nhật ERD trước.
  - `vital_records`/`predictions` là hypertable: khóa chính phải chứa `recorded_at`.
  - Tham chiếu vào hypertable là tham chiếu logic, không tạo FK constraint.
  - Consumer (`../streaming/`) ghi trực tiếp bằng SQL vào patients, vital_records, predictions, alerts, model_versions và seed alert_settings — đổi tên cột phải sửa cả `streaming/src/repository.py`.
- `alembic.ini` phải giữ **chỉ ký tự ASCII** (Alembic đọc bằng encoding của hệ điều hành, cp1252 trên Windows). `alembic check` bỏ qua 2 index TimescaleDB tự tạo (`app/alembic/env.py`).
- Mọi endpoint phải khai báo rõ role được phép (`Depends(require_...)`) theo `docs/design/02_2_usecase.md`. Admin **không** xem bệnh nhân qua `/patients` (chỉ quản lý phân công qua `/admin/patients`).
- **Phân quyền theo phân công**: Bác sĩ/Điều dưỡng chỉ đọc bệnh nhân trong `patient_assignments` của mình (khác → 403, không tồn tại → 404). WebSocket cũng chỉ đẩy sự kiện của bệnh nhân được phân công (`EventDispatcher.assigned_staff`, đọc lại mỗi sự kiện nên phân công mới có hiệu lực ngay).
- `FFILL_LIMIT_HOURS` trong `db/queries.py` phải trùng `rpm_common.grid` (có test); NEWS2 từng thông số gọi `rpm_common.news2.score_parameter`, không cài lại bảng ngưỡng.
- Email dùng kiểu `Email` riêng (`schemas/users.py`), không dùng `EmailStr`: email-validator từ chối tên miền `.local` của hệ thống nội bộ/tài khoản demo.
- JWT của WebSocket nằm trong query string → `RedactTokenFilter` (main.py) che `token=` trong log uvicorn. Không bỏ bộ lọc này.
- **Backend là nơi duy nhất gửi email.** `EMAIL_DELIVERY=log` (mặc định) chỉ ghi log; `smtp` mới gửi thật. Email gửi trong thread riêng; đã có `notification_logs` SENT cho (alert, người nhận) thì không gửi lại.
- Kafka listener: group `rpm-backend`, commit sau khi xử lý, lần đầu bắt đầu từ `latest` (không gửi email cho cảnh báo cũ); tắt bằng `KAFKA_LISTENER_ENABLED=false` (test).
- Endpoint đồng bộ cần đẩy WebSocket gọi `anyio.from_thread.run(dispatcher.handle, ...)` (xem `alerts.publish_update`).
- Test mới phải map được tới 1 dòng trong bảng test ở `docs/design/02_10_thiet_ke_test.md`; ca mới thì bổ sung bảng trước.

## Lệnh (trên host cần POSTGRES_HOST=localhost, KAFKA_BOOTSTRAP_SERVERS=localhost:29092, MLFLOW_TRACKING_URI=http://localhost:5000)

```bash
cd backend
POSTGRES_HOST=localhost ../.venv/Scripts/python -m alembic upgrade head
POSTGRES_HOST=localhost KAFKA_BOOTSTRAP_SERVERS=localhost:29092 MLFLOW_TRACKING_URI=http://localhost:5000 \
  ../.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000        # docs: http://localhost:8000/docs
POSTGRES_HOST=localhost ../.venv/Scripts/python -m app.seed --demo          # bs.an / bs.binh / dd.cuong @rpm.local, mật khẩu demo12345
../.venv/Scripts/python -m pytest -q                                         # cần docker compose up -d postgres (tự tạo DB rpm_test)
POSTGRES_HOST=localhost ../.venv/Scripts/python -m alembic revision --autogenerate -m "..."
POSTGRES_HOST=localhost ../.venv/Scripts/python -m alembic check

# Docker (profile app)
docker compose --profile app up -d backend
```
