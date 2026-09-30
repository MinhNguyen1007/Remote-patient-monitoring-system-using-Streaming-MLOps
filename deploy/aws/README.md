# Deploy lên AWS (một máy EC2 + Docker Compose)

Toàn bộ hệ thống — Kafka, TimescaleDB, stream consumer, backend, frontend, MLflow, Airflow, Prometheus/Grafana — chạy
bằng chính `docker-compose.yml` của repo trên **một máy EC2 `m7i-flex.large` (2 vCPU, 8 GB)**, thêm Caddy làm cổng
HTTPS. Không dùng dịch vụ có quản lý: RDS không hỗ trợ extension TimescaleDB, còn MSK (Kafka) vượt xa credit của tài
khoản Free plan.

```
Internet ──443──► Caddy (HTTPS, Let's Encrypt, <ip>.sslip.io) ──► frontend (nginx) ──/api──► backend
                                                                           (REST + WebSocket)
SSH tunnel (chỉ IP của bạn) ──► Airflow :8080 · MLflow :5000 · Grafana :3001 · Prometheus :9090
```

| Tệp | Vai trò |
|---|---|
| `rpm-aws.sh` | Chạy trên máy bạn: tạo hạ tầng, cài đặt, bật/tắt, tunnel, phát lại dữ liệu |
| `cloud-init.sh` | User data của EC2: Docker Engine + Compose plugin, swap 4 GB, giới hạn log |
| `server-setup.sh` | Chạy trên server, 2 pha: `prepare` (sinh `.env` mật khẩu ngẫu nhiên, build image, bật hạ tầng) và `start` (bật toàn bộ + phát lại) |
| `server-replay.sh` | Chạy trên server: xoá dữ liệu phát lại cũ, phát lại 20 bệnh nhân, phân công lại tài khoản demo |
| `docker-compose.aws.yml` | Ghi đè compose: chỉ Caddy mở 80/443, mọi cổng khác chỉ nghe `127.0.0.1`; MLflow 2 worker |
| `Caddyfile` | Reverse proxy HTTPS tới frontend |

## Chi phí (region Singapore, giá on-demand 2026-09)

| Khoản | Giá | Ghi chú |
|---|---|---|
| EC2 `m7i-flex.large` | $0,1197/giờ | **Chỉ tính khi máy bật** |
| Ổ gp3 60 GB | ≈ $5,8/tháng | Tính cả khi máy tắt |
| Elastic IP | $0,005/giờ ≈ $3,6/tháng | Tính cả khi máy tắt; đổi lại địa chỉ HTTPS không đổi |

Máy tắt: ≈ $0,3/ngày. Mỗi giờ demo: ≈ $0,13. Chạy 24/7 cả tháng: ≈ $97.

> ⚠️ Tài khoản **Free plan** hết hạn **2026-11-10**. Sau ngày đó AWS đóng tài khoản (tài nguyên bị xoá) nếu không nâng
> lên gói trả phí. Credit còn lại: `rpm-aws.sh status`.

## Lần đầu

### 1. Tạo IAM user để deploy (không dùng access key root)

1. AWS Console → **IAM → Users → Create user**, tên `rpm-deployer`, *không* cần quyền truy cập Console.
2. **Attach policies directly** → chọn `AmazonEC2FullAccess` → Create user.
   Tuỳ chọn, để `rpm-aws.sh status` hiện được credit còn lại: thêm inline policy chỉ đọc
   `{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["freetier:GetAccountPlanState","freetier:GetFreeTierUsage"],"Resource":"*"}]}`.
3. Mở user vừa tạo → **Security credentials → Create access key** → *Command Line Interface (CLI)* → lưu Access key ID
   và Secret access key.
4. Trên máy mình, trong terminal (không dán key vào chat):
   ```bash
   aws configure --profile rpm        # nhập 2 key vừa tạo, region ap-southeast-1, output json
   aws sts get-caller-identity --profile rpm   # Arn phải là ...:user/rpm-deployer, không phải :root
   ```
5. **Xoá access key root**: Console → tên tài khoản (góc phải) → Security credentials → Access keys → Delete. Sau đó
   xoá mục `[default]` chứa key root trong `~/.aws/credentials`.

### 2. Tạo máy và cài đặt (Git Bash, từ gốc repo)

```bash
deploy/aws/rpm-aws.sh provision   # ~2 phút: key pair (~/.ssh/rpm-aws.pem), security group, EC2, Elastic IP
deploy/aws/rpm-aws.sh setup       # ~30 phút: build image → promote 2 model → phát lại dữ liệu, tài khoản demo
deploy/aws/rpm-aws.sh secrets     # mật khẩu Admin / Airflow / Grafana (sinh ngẫu nhiên trên server)
```

`setup` lấy code từ GitHub, nên **push code trước**. Dữ liệu `ml/data/processed/*.parquet` (MIMIC-III Demo, không nằm
trong git) được chép từ máy bạn lên.

### Model: promote, không train lại

`setup` **không huấn luyện model trên server**. Bước `promote` mở SSH tunnel tới MLflow server rồi chạy
`python -m rpm_ml.pipelines.promote` trên máy bạn: chép đúng artifact của version mang alias `champion` ở MLflow máy
bạn (cùng params, metric, tag, `reference_stats.json`, `drift_thresholds.json`), so hash từng file, rồi mới gán alias
`champion` ở server. Vì vậy **MLflow + 2 champion trên máy bạn phải đang chạy** (`docker compose up -d postgres mlflow`).

Lý do (đúng thông lệ "build once, deploy many"): model chạy production phải là model đã được đánh giá. Train lại trên
EC2 đã được thử ngày 2026-09-30 và cho `risk_classifier` τ 0,23 thay vì 0,22 (Macro F1 0,629 / Recall CRITICAL 0,768
thay vì 0,623 / 0,790): `GroupKFold` của sklearn 1.3.2 sắp nhóm bằng phép sắp xếp không ổn định, kết quả đổi theo tập
lệnh SIMD của CPU. Retrain trên server vẫn diễn ra qua Airflow (drift hoặc Admin bấm) và vẫn phải qua quality gate.

Khi champion trên máy bạn đổi (train/retrain mới): `deploy/aws/rpm-aws.sh promote` — chạy lại an toàn, version đã
chuyển thì bỏ qua.

## Dùng hằng ngày

```bash
deploy/aws/rpm-aws.sh start       # bật máy (~2 phút), container tự khởi động lại
deploy/aws/rpm-aws.sh replay      # dữ liệu chạy lại từ đầu cho buổi demo (~30 phút cho đủ 365 nhịp)
deploy/aws/rpm-aws.sh replay --drift   # demo drift → Airflow tự retrain → quality gate
deploy/aws/rpm-aws.sh tunnel      # Airflow / MLflow / Grafana ở localhost (Ctrl+C để đóng)
deploy/aws/rpm-aws.sh stop        # TẮT sau khi demo xong
deploy/aws/rpm-aws.sh status
deploy/aws/rpm-aws.sh update      # sau khi push code mới: git pull + build lại + khởi động lại
```

Tài khoản demo (bác sĩ `bs.an@rpm.local`, `bs.binh@rpm.local`, điều dưỡng `dd.cuong@rpm.local`) dùng mật khẩu
`demo12345` như bản chạy trên máy — ai có link đều đăng nhập được, dữ liệu là MIMIC-III Demo công khai. Tài khoản
Admin thì có mật khẩu ngẫu nhiên riêng (`secrets`).

## Bảo mật

- Chỉ cổng 80/443 mở cho Internet. SSH (22) chỉ mở cho IP của máy bạn — mỗi lệnh tự thêm IP hiện tại; dọn IP cũ bằng
  `rpm-aws.sh ssh-rules` và `rpm-aws.sh ssh-rules revoke <cidr>`.
- Airflow, MLflow, Grafana, Prometheus, PostgreSQL, Kafka chỉ nghe trên `127.0.0.1` của server → chỉ vào được qua SSH.
- `.env` trên server sinh mật khẩu ngẫu nhiên cho PostgreSQL, JWT secret, Admin, Airflow, Grafana; không bao giờ rời
  khỏi server. Ổ EBS mã hoá; IMDSv2 bắt buộc.
- Caddy không ghi access log (WebSocket mang JWT trong query string).
- Email cảnh báo giữ `EMAIL_DELIVERY=log` (chỉ ghi log): gửi thật cần cấu hình SMTP trong `.env` trên server.

## Gỡ bỏ

```bash
deploy/aws/rpm-aws.sh destroy     # xoá máy + ổ đĩa + Elastic IP + security group + key pair (hỏi xác nhận)
```
