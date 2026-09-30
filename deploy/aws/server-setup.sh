#!/usr/bin/env bash
# Chạy TRÊN server EC2, trong thư mục repo (~/rpm), do `deploy/aws/rpm-aws.sh setup` gọi qua SSH.
# Idempotent: chạy lại chỉ build/khởi động lại, không sinh lại mật khẩu, không train lại model đã có.
#   bash deploy/aws/server-setup.sh <SITE_ADDRESS>     vd 13-212-1-2.sslip.io
set -euo pipefail
SITE_ADDRESS="${1:?cần SITE_ADDRESS, vd 13-212-1-2.sslip.io}"
cd "$(dirname "$0")/../.."

log() { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }
rand() { openssl rand -hex "${1:-24}"; }
set_env() {  # set_env KEY VALUE — ghi đè nếu đã có, thêm nếu chưa
  if grep -q "^$1=" .env; then sed -i "s|^$1=.*|$1=$2|" .env; else echo "$1=$2" >> .env; fi
}

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
set_env SITE_ADDRESS "$SITE_ADDRESS"
set_env BACKEND_CORS_ORIGINS "https://$SITE_ADDRESS"
set_env FRONTEND_BASE_URL "https://$SITE_ADDRESS"
set -a; . ./.env; set +a

log "Build image (lần đầu ~25 phút trên m7i-flex.large)"
docker compose build
docker builder prune -af >/dev/null

log "Hạ tầng nền"
docker compose up -d --wait postgres
docker compose up -d zookeeper kafka mlflow
until curl -sf http://127.0.0.1:5000/health >/dev/null; do sleep 3; done

champion_exists() {
  curl -sf "http://127.0.0.1:5000/api/2.0/mlflow/registered-models/alias?name=$1&alias=champion" >/dev/null
}
train() {  # train <module> — chạy trong image Airflow (venv /opt/rpm-venv có đủ thư viện ML, dữ liệu mount sẵn)
  docker compose run --rm --no-deps --entrypoint /opt/rpm-venv/bin/python airflow-scheduler -m "rpm_ml.training.$1" \
    | tail -n 25
}
champion_exists risk_classifier || { log "Train mô hình rủi ro"; train train_risk; }
champion_exists anomaly_detector || { log "Train LSTM-Autoencoder (~10 phút)"; train train_anomaly; }

log "Khởi động toàn bộ (backend tự chạy alembic upgrade head)"
docker compose up -d

log "Phát lại dữ liệu + tạo tài khoản demo"
bash deploy/aws/server-replay.sh

log "Xong: https://$SITE_ADDRESS"
echo "Admin: $ADMIN_EMAIL / $ADMIN_PASSWORD   (xem lại: rpm-aws.sh secrets)"
