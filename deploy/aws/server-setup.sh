#!/usr/bin/env bash
# Chạy TRÊN server EC2, trong thư mục repo (~/rpm), do `deploy/aws/rpm-aws.sh setup` gọi qua SSH. Hai pha:
#   bash deploy/aws/server-setup.sh prepare <SITE_ADDRESS>   .env, build image, bật PostgreSQL/Kafka/MLflow
#   bash deploy/aws/server-setup.sh start                    cần champion trên MLflow → bật toàn bộ + phát lại dữ liệu
# Giữa hai pha, rpm-aws.sh promote chuyển đúng artifact champion từ MLflow máy phát triển lên (không train lại ở
# đây — xem ml/src/rpm_ml/pipelines/promote.py). Idempotent: chạy lại không sinh lại mật khẩu.
set -euo pipefail
PHASE="${1:?cần pha: prepare <SITE_ADDRESS> | start}"
cd "$(dirname "$0")/../.."

log() { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }
rand() { openssl rand -hex "${1:-24}"; }
set_env() {  # set_env KEY VALUE — ghi đè nếu đã có, thêm nếu chưa
  if grep -q "^$1=" .env; then sed -i "s|^$1=.*|$1=$2|" .env; else echo "$1=$2" >> .env; fi
}
# Không `source` .env: có giá trị chứa dấu cách (ADMIN_FULL_NAME) — docker compose đọc được, bash thì không
envget() { grep -m1 "^$1=" .env | cut -d= -f2-; }
champion_exists() {
  curl -sf "http://127.0.0.1:5000/api/2.0/mlflow/registered-models/alias?name=$1&alias=champion" >/dev/null
}

prepare() {
  local site="${1:?cần SITE_ADDRESS, vd 13-212-1-2.sslip.io}"
  test -f ml/data/processed/stream_replay.parquet -a -f ml/data/processed/hourly.parquet \
    || { echo "thiếu ml/data/processed/*.parquet — rpm-aws.sh setup phải chép lên trước"; exit 1; }

  if [ ! -f .env ]; then
    log "Tạo .env với mật khẩu ngẫu nhiên (chỉ lần đầu)"
    cp .env.example .env
    set_env POSTGRES_PASSWORD "$(rand)"
    set_env BACKEND_SECRET_KEY "$(rand 32)"
    set_env AIRFLOW_WWW_PASSWORD "$(rand 12)"
    set_env GRAFANA_ADMIN_PASSWORD "$(rand 12)"
    set_env ADMIN_PASSWORD "$(rand 12)"
    set_env ADMIN_EMAIL "admin@rpm.local"
  fi
  set_env COMPOSE_FILE "docker-compose.yml:deploy/aws/docker-compose.aws.yml"
  set_env COMPOSE_PROFILES "app"
  set_env SITE_ADDRESS "$site"
  set_env BACKEND_CORS_ORIGINS "https://$site"
  set_env FRONTEND_BASE_URL "https://$site"

  log "Build image (lần đầu ~25 phút trên m7i-flex.large)"
  docker compose build
  docker image prune -f >/dev/null  # giữ cache build: lần sau chỉ build lại phần đổi

  log "Hạ tầng nền"
  docker compose up -d --wait postgres
  docker compose up -d zookeeper kafka mlflow
  until curl -sf http://127.0.0.1:5000/health >/dev/null; do sleep 3; done
}

start() {
  for model in risk_classifier anomaly_detector; do
    champion_exists "$model" || { echo "MLflow chưa có $model@champion — chạy rpm-aws.sh promote trước"; exit 3; }
  done
  log "Khởi động toàn bộ (backend tự chạy alembic upgrade head)"
  docker compose up -d

  log "Phát lại dữ liệu + tạo tài khoản demo"
  bash deploy/aws/server-replay.sh

  log "Xong: https://$(envget SITE_ADDRESS)"
  echo "Mật khẩu Admin / Airflow / Grafana: rpm-aws.sh secrets"
}

case "$PHASE" in
  prepare) prepare "${2:-}" ;;
  start) start ;;
  *) echo "pha không hợp lệ: $PHASE"; exit 2 ;;
esac
