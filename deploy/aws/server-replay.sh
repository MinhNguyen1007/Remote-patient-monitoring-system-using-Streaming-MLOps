#!/usr/bin/env bash
# Chạy TRÊN server: xoá dữ liệu phát lại cũ rồi phát lại 20 bệnh nhân từ đầu (dùng trước mỗi buổi demo).
# Giữ users, model_versions, alert_settings, drift_reports (như rpm_streaming.storage.reset_demo).
#   bash deploy/aws/server-replay.sh [--drift]    --drift: bật drift mô phỏng để demo vòng lặp drift → retrain
set -euo pipefail
cd "$(dirname "$0")/../.."
# Không `source` .env: có giá trị chứa dấu cách (ADMIN_FULL_NAME) — docker compose đọc được, bash thì không
envget() { grep -m1 "^$1=" .env | cut -d= -f2-; }
POSTGRES_USER=$(envget POSTGRES_USER); POSTGRES_DB=$(envget POSTGRES_DB)
PRODUCER=rpm_stream_producer_run

until curl -sf http://127.0.0.1:8000/health >/dev/null; do sleep 3; done   # backend đã chạy xong alembic
docker rm -f "$PRODUCER" >/dev/null 2>&1 || true
docker compose stop stream-consumer
docker compose run --rm --no-deps --entrypoint python stream-consumer -m rpm_streaming.storage.reset_demo --yes
docker compose up -d stream-consumer
docker compose run -d --no-deps --name "$PRODUCER" stream-producer "$@" >/dev/null

# reset_demo xoá cả phân công: đợi đủ 20 bệnh nhân rồi phân công lại cho tài khoản demo
for _ in $(seq 1 120); do
  n=$(docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "select count(*) from patients")
  [ "$n" -ge 20 ] && break
  sleep 5
done
docker compose exec -T backend python -m app.seed --demo
echo "Đang phát lại (~30 phút cho đủ 365 nhịp). Theo dõi: docker logs -f $PRODUCER"
