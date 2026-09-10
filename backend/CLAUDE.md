# CLAUDE.md — backend/

FastAPI. Xem kiến trúc tổng thể ở `../CLAUDE.md` và thiết kế chi tiết ở `../docs/design/`.

## Cấu trúc

```
app/
  api/          Routers (patients, predictions, alerts, auth, admin/models)
  db/           SQLAlchemy models + CRUD, khớp với docs/design/02_7_erd.md
  ml/           Wrapper load model từ MLflow Registry + hàm predict_risk/predict_anomaly
  streaming/    Consumer logic dùng chung với service streaming/ (feature engineering)
  scheduler/    Job định kỳ (drift check trigger) chạy trong tiến trình backend
  alembic/      Database migration
tests/          pytest (unit + integration), xem docs/design/02_10_thiet_ke_test.md
```

## Quy ước

- Mọi model SQLAlchemy trong `db/models.py` phải khớp đúng entity/attribute trong `docs/design/02_5_class.md` và `02_7_erd.md` — nếu cần thêm cột, cập nhật ERD trước.
- Mọi endpoint mới phải khai báo rõ role được phép truy cập (`Depends(require_role(...))`) theo đúng phân quyền ở `docs/design/02_2_usecase.md`.
- Response model dùng Pydantic schema riêng (không trả thẳng SQLAlchemy model).
- Endpoint tạo alert/gửi email phải theo đúng luồng ở `docs/design/02_3_activity.md` mục 2.3.1 (không tạo alert cho mọi prediction, chỉ khi vượt ngưỡng).
- Test mới thêm phải map được tới 1 dòng trong bảng test ở `docs/design/02_10_thiet_ke_test.md`; nếu là ca test mới chưa có trong bảng, bổ sung vào bảng đó trước.

## Lệnh

```bash
uvicorn app.main:app --reload --port 8000
pytest
alembic revision --autogenerate -m "..."
alembic upgrade head
```
