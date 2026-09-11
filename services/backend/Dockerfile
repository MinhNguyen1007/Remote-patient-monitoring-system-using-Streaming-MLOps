# Build context = gốc repo:  docker compose --profile app up -d backend
FROM python:3.11-slim

# Giữ đúng bố cục thư mục như trong repo (services/backend, packages/common)
WORKDIR /app/services/backend
ENV PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8

COPY services/backend/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# rpm_common: bảng điểm NEWS2 dùng chung với pipeline (không cài lại logic trong backend)
COPY packages/common /app/packages/common
RUN pip install --no-cache-dir /app/packages/common

COPY services/backend/alembic.ini alembic.ini
COPY services/backend/app app

EXPOSE 8000
# Áp migration trước khi chạy (không làm gì nếu schema đã ở head)
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
