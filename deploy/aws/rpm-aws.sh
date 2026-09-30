#!/usr/bin/env bash
# Điều khiển bản deploy AWS từ máy phát triển (Git Bash / Linux / macOS) — xem deploy/aws/README.md.
#   deploy/aws/rpm-aws.sh <lệnh>
# Dùng AWS CLI với profile $AWS_PROFILE (mặc định "rpm" = IAM user riêng, KHÔNG dùng key root).
set -euo pipefail

export AWS_PROFILE="${AWS_PROFILE:-rpm}"
export AWS_REGION="${AWS_REGION:-ap-southeast-1}"
NAME=rpm-server
INSTANCE_TYPE="${INSTANCE_TYPE:-m7i-flex.large}"   # 2 vCPU, 8 GB — thuộc nhóm được dùng credit Free plan
DISK_GB="${DISK_GB:-60}"                           # image ~20 GB + cache build + swap
KEY_NAME=rpm-server-key
KEY_FILE="${KEY_FILE:-$HOME/.ssh/rpm-aws.pem}"
REPO_URL="${REPO_URL:-https://github.com/MinhNguyen1007/Remote-patient-monitoring-system-using-Streaming-MLOps.git}"
REPO_DIR=rpm
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

log() { printf '\033[1;32m==> %s\033[0m\n' "$*" >&2; }
die() { printf '\033[1;31m%s\033[0m\n' "$*" >&2; exit 1; }
q() { aws "$@" --output text | tr -d '\r'; }   # aws.exe trên Windows in CRLF
winpath() { if command -v cygpath >/dev/null; then cygpath -m "$1"; else echo "$1"; fi; }

instance_id() {
  q ec2 describe-instances --filters "Name=tag:Name,Values=$NAME" \
    "Name=instance-state-name,Values=pending,running,stopping,stopped" --query 'Reservations[0].Instances[0].InstanceId' \
    | sed 's/^None$//'
}
need_instance() { ID=$(instance_id); [ -n "$ID" ] || die "Chưa có máy $NAME — chạy: $0 provision"; }
eip_ip() { q ec2 describe-addresses --filters "Name=tag:Name,Values=$NAME" --query 'Addresses[0].PublicIp' | sed 's/^None$//'; }
site() { echo "$(eip_ip | tr . -).sslip.io"; }
state() { q ec2 describe-instances --instance-ids "$1" --query 'Reservations[0].Instances[0].State.Name'; }
sg_id() { q ec2 describe-security-groups --filters "Name=group-name,Values=$NAME-sg" --query 'SecurityGroups[0].GroupId' | sed 's/^None$//'; }

allow_my_ip() {  # mở SSH (22) cho IP hiện tại của máy này; IP cũ vẫn giữ — dọn bằng lệnh `ssh-rules`
  local ip; ip=$(curl -s https://checkip.amazonaws.com | tr -d '[:space:]')
  aws ec2 authorize-security-group-ingress --group-id "$(sg_id)" --protocol tcp --port 22 --cidr "$ip/32" \
    >/dev/null 2>&1 && log "Mở SSH cho $ip/32" || true
}
SSH_OPTS=(-i "$KEY_FILE" -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=30)
remote() { ssh "${SSH_OPTS[@]}" "ubuntu@$(eip_ip)" "$@"; }
wait_ssh() {
  log "Chờ SSH"
  for _ in $(seq 1 60); do remote -o ConnectTimeout=5 true 2>/dev/null && return; sleep 5; done
  die "Không SSH được vào $(eip_ip)"
}

cmd_provision() {
  [ -z "$(instance_id)" ] || die "Máy $NAME đã tồn tại ($(instance_id))"
  q sts get-caller-identity --query Arn | grep -q ':root$' && die "Profile $AWS_PROFILE đang là root — dùng IAM user"

  if [ ! -f "$KEY_FILE" ]; then
    log "Tạo key pair $KEY_NAME → $KEY_FILE"
    mkdir -p "$(dirname "$KEY_FILE")"
    q ec2 create-key-pair --key-name "$KEY_NAME" --key-type ed25519 --query KeyMaterial > "$KEY_FILE"
    chmod 600 "$KEY_FILE"
  fi

  if [ -z "$(sg_id)" ]; then
    log "Tạo security group $NAME-sg (80/443 công khai, 22 chỉ IP của bạn)"
    local vpc; vpc=$(q ec2 describe-vpcs --filters Name=is-default,Values=true --query 'Vpcs[0].VpcId')
    aws ec2 create-security-group --group-name "$NAME-sg" --description "RPM demo: HTTP/HTTPS public, SSH restricted" \
      --vpc-id "$vpc" --tag-specifications "ResourceType=security-group,Tags=[{Key=Name,Value=$NAME}]" >/dev/null
    for port in 80 443; do
      aws ec2 authorize-security-group-ingress --group-id "$(sg_id)" --protocol tcp --port $port --cidr 0.0.0.0/0 >/dev/null
    done
  fi
  allow_my_ip

  local ami
  ami=$(q ec2 describe-images --owners 099720109477 \
    --filters 'Name=name,Values=ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*' Name=state,Values=available \
    --query 'sort_by(Images,&CreationDate)[-1].ImageId')
  log "Tạo máy $INSTANCE_TYPE, Ubuntu 24.04 ($ami), ổ ${DISK_GB} GB gp3"
  ID=$(q ec2 run-instances --image-id "$ami" --instance-type "$INSTANCE_TYPE" --key-name "$KEY_NAME" \
    --security-group-ids "$(sg_id)" --user-data "file://$(winpath "$ROOT/deploy/aws/cloud-init.sh")" \
    --block-device-mappings "DeviceName=/dev/sda1,Ebs={VolumeSize=$DISK_GB,VolumeType=gp3,Encrypted=true,DeleteOnTermination=true}" \
    --metadata-options HttpTokens=required,HttpEndpoint=enabled \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$NAME}]" "ResourceType=volume,Tags=[{Key=Name,Value=$NAME}]" \
    --query 'Instances[0].InstanceId')
  aws ec2 wait instance-running --instance-ids "$ID"

  if [ -z "$(eip_ip)" ]; then
    log "Cấp Elastic IP (địa chỉ cố định qua các lần bật/tắt)"
    aws ec2 allocate-address --domain vpc --tag-specifications "ResourceType=elastic-ip,Tags=[{Key=Name,Value=$NAME}]" >/dev/null
  fi
  local alloc; alloc=$(q ec2 describe-addresses --filters "Name=tag:Name,Values=$NAME" --query 'Addresses[0].AllocationId')
  aws ec2 associate-address --instance-id "$ID" --allocation-id "$alloc" >/dev/null
  log "Máy $ID chạy ở $(eip_ip) → https://$(site). Tiếp theo: $0 setup"
}

cmd_setup() {
  need_instance; allow_my_ip; wait_ssh
  log "Chờ cloud-init cài Docker xong"
  remote 'cloud-init status --wait >/dev/null; docker version --format "Docker {{.Server.Version}}"'
  log "Lấy code từ GitHub"
  remote "if [ -d $REPO_DIR/.git ]; then git -C $REPO_DIR pull --ff-only; else git clone --depth 1 $REPO_URL $REPO_DIR; fi"
  log "Chép dữ liệu đã tiền xử lý (MIMIC-III Demo, không nằm trong git)"
  remote "mkdir -p $REPO_DIR/ml/data/processed"
  scp "${SSH_OPTS[@]}" "$ROOT"/ml/data/processed/{hourly.parquet,stream_replay.parquet,summary.json} \
    "ubuntu@$(eip_ip):$REPO_DIR/ml/data/processed/"
  remote "cd $REPO_DIR && bash deploy/aws/server-setup.sh $(site)"
}

cmd_update() {  # sau khi push code mới lên GitHub
  need_instance; allow_my_ip
  remote "cd $REPO_DIR && git pull --ff-only && docker compose build && docker builder prune -af >/dev/null && docker compose up -d"
}

cmd_start() {
  need_instance; log "Bật $ID"
  aws ec2 start-instances --instance-ids "$ID" >/dev/null
  aws ec2 wait instance-running --instance-ids "$ID"
  allow_my_ip; wait_ssh
  log "Chờ backend sẵn sàng (container tự bật lại theo restart: unless-stopped)"
  remote 'until curl -sf http://127.0.0.1:8000/health >/dev/null; do sleep 3; done'
  log "Sẵn sàng: https://$(site)  — muốn dữ liệu chạy lại từ đầu: $0 replay"
}

cmd_stop() {
  need_instance; log "Tắt $ID (không tính tiền giờ chạy; vẫn tính ổ đĩa + Elastic IP ≈ \$0,3/ngày)"
  aws ec2 stop-instances --instance-ids "$ID" >/dev/null
  aws ec2 wait instance-stopped --instance-ids "$ID"
  log "Đã tắt"
}

cmd_status() {
  local id; id=$(instance_id)
  [ -n "$id" ] || { echo "Chưa có máy $NAME"; return; }
  echo "Máy:      $id ($INSTANCE_TYPE) — $(state "$id")"
  echo "Địa chỉ:  https://$(site)  ($(eip_ip))"
  aws freetier get-account-plan-state \
    --query '[accountPlanType, accountPlanRemainingCredits.amount, accountPlanExpirationDate]' --output text 2>/dev/null \
    | awk '{printf "Tài khoản: gói %s, còn $%s credit, hết hạn %s\n", $1, $2, substr($3,1,10)}' || true
}

cmd_replay() { need_instance; remote "cd $REPO_DIR && bash deploy/aws/server-replay.sh $*"; }

cmd_tunnel() {
  need_instance; allow_my_ip
  log "Airflow http://localhost:8080 · MLflow http://localhost:5000 · Grafana http://localhost:3001 · Prometheus http://localhost:9090 (Ctrl+C để đóng)"
  ssh "${SSH_OPTS[@]}" -N -L 8080:127.0.0.1:8080 -L 5000:127.0.0.1:5000 -L 3001:127.0.0.1:3001 -L 9090:127.0.0.1:9090 \
    "ubuntu@$(eip_ip)"
}

cmd_secrets() {
  need_instance
  remote "grep -E '^(ADMIN_EMAIL|ADMIN_PASSWORD|AIRFLOW_WWW_USER|AIRFLOW_WWW_PASSWORD|GRAFANA_ADMIN_PASSWORD)=' $REPO_DIR/.env"
}

cmd_ssh() { need_instance; allow_my_ip; ssh "${SSH_OPTS[@]}" "ubuntu@$(eip_ip)" "$@"; }

cmd_ssh_rules() {  # liệt kê / thu hồi các IP được SSH: rpm-aws.sh ssh-rules [revoke <cidr>]
  if [ "${1:-}" = revoke ]; then
    aws ec2 revoke-security-group-ingress --group-id "$(sg_id)" --protocol tcp --port 22 --cidr "$2"
  else
    q ec2 describe-security-groups --group-ids "$(sg_id)" \
      --query 'SecurityGroups[0].IpPermissions[?FromPort==`22`].IpRanges[].CidrIp'
  fi
}

cmd_destroy() {
  local id; id=$(instance_id)
  echo "Sẽ XOÁ VĨNH VIỄN: máy ${id:-(không có)} + ổ đĩa (DB, MLflow registry), Elastic IP, security group, key pair."
  read -r -p "Gõ tên máy ($NAME) để xác nhận: " answer
  [ "$answer" = "$NAME" ] || die "Huỷ"
  if [ -n "$id" ]; then aws ec2 terminate-instances --instance-ids "$id" >/dev/null; aws ec2 wait instance-terminated --instance-ids "$id"; fi
  local alloc; alloc=$(q ec2 describe-addresses --filters "Name=tag:Name,Values=$NAME" --query 'Addresses[0].AllocationId' | sed 's/^None$//')
  [ -z "$alloc" ] || aws ec2 release-address --allocation-id "$alloc"
  [ -z "$(sg_id)" ] || aws ec2 delete-security-group --group-id "$(sg_id)"
  aws ec2 delete-key-pair --key-name "$KEY_NAME" >/dev/null 2>&1 || true
  log "Đã xoá. Khoá SSH cục bộ vẫn ở $KEY_FILE"
}

usage() {
  cat <<EOF
Cách dùng: $0 <lệnh>   (AWS_PROFILE=$AWS_PROFILE, region $AWS_REGION)
  provision        tạo key pair, security group, máy EC2, Elastic IP (một lần)
  setup            cài hệ thống lên máy: code, dữ liệu, build image, train model, tài khoản demo (một lần, ~40 phút)
  start | stop     bật / tắt máy (tắt khi không demo để tiết kiệm credit)
  status           trạng thái máy, địa chỉ, credit còn lại
  replay [--drift] phát lại dữ liệu 20 bệnh nhân từ đầu (--drift: demo drift → retrain)
  tunnel           mở Airflow / MLflow / Grafana / Prometheus qua SSH tunnel
  secrets          xem mật khẩu Admin, Airflow, Grafana
  update           git pull + build lại + khởi động lại (sau khi push code mới)
  ssh [lệnh]       SSH vào máy
  ssh-rules        liệt kê IP được SSH; ssh-rules revoke <cidr> để thu hồi
  destroy          xoá toàn bộ tài nguyên (không hoàn tác được)
EOF
}

command="${1:-}"; shift || true
case "$command" in
  provision|setup|update|start|stop|status|replay|tunnel|secrets|ssh|destroy) "cmd_$command" "$@" ;;
  ssh-rules) cmd_ssh_rules "$@" ;;
  *) usage ;;
esac
