# Image dùng chung cho producer và consumer (build context = gốc repo).
#   docker compose --profile app up -d stream-consumer
#   docker compose --profile app run --rm stream-producer --seconds-per-hour 5
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8 TF_CPP_MIN_LOG_LEVEL=2

COPY streaming/requirements.txt streaming/requirements.txt
RUN pip install --no-cache-dir -r streaming/requirements.txt

# Package đặc trưng dùng chung: cùng code với lúc train (không copy logic sang streaming/)
COPY common common
RUN pip install --no-cache-dir ./common

COPY streaming/src streaming/src
WORKDIR /app/streaming/src
ENTRYPOINT ["python"]
CMD ["consumer.py"]
