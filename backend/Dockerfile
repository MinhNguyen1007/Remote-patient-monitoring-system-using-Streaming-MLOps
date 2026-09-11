# Build context = gốc repo:  docker compose --profile app up -d backend
FROM python:3.11-slim

WORKDIR /app/backend
ENV PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8

COPY backend/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/alembic.ini alembic.ini
COPY backend/app app

EXPOSE 8000
# Áp migration trước khi chạy (không làm gì nếu schema đã ở head)
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
