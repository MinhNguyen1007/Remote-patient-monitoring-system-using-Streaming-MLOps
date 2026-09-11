# Image dùng chung cho producer và consumer (build context = gốc repo).
#   docker compose --profile app up -d stream-consumer
#   docker compose --profile app run --rm stream-producer --seconds-per-hour 5
FROM python:3.11-slim

# Giữ đúng bố cục thư mục như trong repo: config tìm ml/data/processed tương đối với /app
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8 TF_CPP_MIN_LOG_LEVEL=2 \
    PYTHONPATH=/app/services/streaming/src

COPY services/streaming/requirements.txt services/streaming/requirements.txt
RUN pip install --no-cache-dir -r services/streaming/requirements.txt

# Package đặc trưng dùng chung: cùng code với lúc train (không copy logic sang streaming)
COPY packages/common packages/common
RUN pip install --no-cache-dir ./packages/common

COPY services/streaming/src services/streaming/src
ENTRYPOINT ["python", "-m"]
CMD ["rpm_streaming.consumer"]
