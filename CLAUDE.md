# CLAUDE.md — Hệ thống giám sát bệnh nhân từ xa bằng Streaming + MLOps

Đồ án môn học. Kế hoạch tổng thể và các quyết định kiến trúc đã chốt nằm trong lịch sử hội thoại lúc lập plan; tài liệu thiết kế đầy đủ nằm ở `docs/design/` (đọc `docs/design/01_gioi_thieu.md` và `02_0_quy_trinh_thiet_ke.md` trước khi code bất kỳ phần nào).

## ⚠️ Trạng thái hiện tại (đọc mục này trước tiên)

> **Quy tắc**: mỗi khi hoàn thành xong 1 giai đoạn hoặc 1 mốc quan trọng, PHẢI cập nhật lại mục này (đặc biệt dòng "Đang ở đâu" và "Việc tiếp theo") trước khi kết thúc phiên làm việc — đây là cách duy nhất để phiên chat sau không bị mất ngữ cảnh.

- **Đang ở đâu**:
  - Giai đoạn A (thiết kế, mục 2) và Giai đoạn B (khung repo + hạ tầng Docker) đã xong, nhánh `master`.
  - 2026-09-10: **rà soát toàn bộ** thiết kế + hạ tầng + dữ liệu thật và sửa lại (commit `d25a37b`).
  - **Giai đoạn C — Dữ liệu & Model: XONG (2026-09-11).** Cả 2 mô hình có `champion` (`risk_classifier` v2, `anomaly_detector` **v3** = v2 đóng gói lại, cùng trọng số); bảng/hình cho báo cáo ở `ml/reports/evaluation.md`.
    - `common/rpm_common`: mapping itemid, làm sạch, lưới 1 giờ, forward-fill, NEWS2 rút gọn, feature cửa sổ 6 giờ, baseline z-score, nhãn dự báo, hàm ghép `build_hourly_features`, cửa sổ 12 giờ + điểm bất thường (`anomaly.py`). 99 unit test qua, gồm test tính nhân quả (feature tại t không phụ thuộc dữ liệu sau t).
    - `ml/src/preprocess.py` + `ml/src/split.py`, 7 test qua. Đã chạy trên dữ liệu thật và sinh ra (trong `ml/data/processed/`, không nằm trong git):
      - `hourly.parquet`: 132 đợt ICU, 14.138 giờ;
      - `stream_replay.parquet`: 20 bệnh nhân, 1.834 giờ;
      - `summary.json`.
    - File chia nhóm cố định `ml/splits/subject_split.json`: 48/15/15/20 bệnh nhân có vitals, seed 42 — **không tạo lại**.
    - Môi trường: `.venv` ở gốc repo (tạo bằng `--system-site-packages`, đã cài `-e common`).
  - **Mô hình dự báo rủi ro (h = 4): xong, `risk_classifier` v2 là `champion`**:
    - Code: `ml/src/train.py` + `risk_models.py`, `metrics.py`, `gate.py`, `drift.py`; `rpm_common/risk.py`. 41 test ở `ml/` (cả 2 mô hình).
    - `τ_critical` chọn trên dự đoán out-of-fold GroupKFold của train ∪ validation (63 bệnh nhân), mục tiêu Recall CRITICAL 0,80 (`TARGET_RECALL_CRITICAL`); model cuối fit trên train.
    - CV Macro F1: Random Forest 0,622 (được chọn), Logistic Regression 0,618, XGBoost 0,608, persistence 0,565.
    - Lần chạy 1 (`τ_critical = 0,25` chọn trên validation), trên test: Macro F1 0,639, Recall CRITICAL 0,730, AUROC 0,836 (persistence: 0,547 và 0,308). **Gate từ chối** vì Recall CRITICAL < 0,80 → `risk_classifier` v1, tag `gate=rejected`.
    - Lần chạy 2, 2026-09-11 (τ chọn trên dự đoán out-of-fold GroupKFold của train ∪ validation, `τ_critical = 0,22`; run `383ec65516e44846b8f872dc267e2fe6`):

      | Tập | Macro F1 | Recall CRITICAL | Precision CRITICAL |
      |---|---|---|---|
      | Out-of-fold (63 BN) | 0,591 | 0,807 | 0,395 |
      | Validation | 0,623 | 0,849 | 0,498 |
      | Test | 0,623 | **0,790** (249/315, cần 252) | 0,391 |

      Persistence trên test: Macro F1 0,547, Recall CRITICAL 0,308. Với gate cũ (0,80) run này bị từ chối, chỉ vì thiếu 3 giờ CRITICAL.
    - **Người dùng chọn ngày 2026-09-11**: hạ ngưỡng gate Recall CRITICAL xuống **0,75** (`MIN_RECALL_CRITICAL`), còn mục tiêu chọn τ giữ 0,80. Lý do: nếu mục tiêu chọn τ bằng ngưỡng gate thì không có biên an toàn, và mỗi lần retrain có khoảng 50% khả năng trượt chỉ do nhiễu (test chỉ 15 bệnh nhân).
      - Đã áp lại gate lên metric test **đã log** của v2 (không dự đoán lại trên test) → đạt.
      - v2 mang alias `champion` + `challenger`, tag `gate=passed`, `gate_note` ghi lý do hiệu chỉnh, `tau_critical=0.22`. v1 giữ `gate=rejected`.
    - **Ghi chú bắt buộc cho báo cáo mục 3.4/3.5**:
      - tập test đã được dùng 2 lần;
      - ngưỡng gate 0,75 được hiệu chỉnh **sau khi xem kết quả test** (chi tiết ở `02_10` mục 2.10.3).
  - **Mô hình bất thường (LSTM-AE): xong, `anomaly_detector` v2 là `champion`** (2026-09-11):
    - Code: `ml/src/train_anomaly.py`, `anomaly_model.py` (kiến trúc + wrapper pyfunc: cửa sổ z-score gốc (n, 12, 6) → `anomaly_score`), `injection.py`; `rpm_common/anomaly.py` (`make_windows`, `latest_window`, `center_windows`, ECDF).
    - Cửa sổ NORMAL: train 1.146, validation 334, test 485.
    - v1 (chưa căn giữa): test Precision 0,23, Recall 0,15, AUROC 0,850, gắn cờ nhầm 5,5% → trượt gate cũ (P, R ≥ 0,7) → tag `gate=rejected`.
    - Chẩn đoán **chỉ trên train ∪ validation** (GroupKFold): tiêu chí 0,7/0,7 tại τ = 0,99 không đạt được với dữ liệu này, vì bất thường tiêm nằm trong độ biến thiên tự nhiên. Căn giữa cửa sổ làm ngưỡng ổn định hơn nhiều giữa các bệnh nhân.
    - **Người dùng chọn**: căn giữa cửa sổ theo kênh + gate **AUROC ≥ 0,75** và không kém champion (`MIN_AUROC_ANOMALY`). P/R/F1 chỉ báo cáo.
    - v2 (run `b96c9105a15f4f0a84466277e91eb1f1`), trên test: **AUROC 0,864**, Precision 0,727, Recall 0,167, F1 0,271, gắn cờ nhầm 0,7%. Recall theo loại: spike 0,25, level shift 0,19, drift 0,06.
    - **Ghi chú bắt buộc cho báo cáo 3.4/3.5**: test của mô hình bất thường đã dùng 2 lần; gate đổi sau khi xem kết quả test lần đầu; recall thấp ở τ = 0,99 (chi tiết `02_9` mục 2.9.3, `02_10` mục 2.10.3).
  - **Đánh giá cho báo cáo** (`ml/src/evaluate.py` → `ml/reports/`, commit vào git; chạy lại khi champion đổi):
    - h = 1 (run log riêng, không đăng ký): model Macro F1 0,578 < persistence 0,621, dù Recall CRITICAL 0,784 so với 0,486. Ở tầm 1 giờ, persistence rất khó thắng vì vitals tự tương quan mạnh → lý do chọn h = 4.
    - SHAP lớp CRITICAL: `news2_max_6h`, `news2_score`, `respiratory_rate_mean_6h`, `heart_rate` đứng đầu.
    - Nhãn proxy: tỷ lệ giờ CRITICAL 19,1% ở đợt ICU tử vong tại viện so với 3,6% ở đợt sống sót; AUROC mức đợt 0,718.
    - Anomaly trên dữ liệu thật (không tiêm), cửa sổ test theo mức NEWS2 cao nhất trong 12 giờ: tỷ lệ gắn cờ NORMAL 0,6%, WARNING 17,4%, CRITICAL 34,8%. AUROC CRITICAL so với NORMAL 0,837 — bằng chứng thực nghiệm cho mô hình bất thường ngoài phần tiêm tổng hợp.
  - **Giai đoạn D — Streaming: XONG (2026-09-11)**. Quy ước và lệnh ở `streaming/CLAUDE.md`.
    - Schema DB: `backend/app/db/models.py` + Alembic migration `0001` (hypertable `vital_records`, `predictions`), đã `upgrade head` trên `rpm_db`.
    - `streaming/`: producer (replay + `--drift`), consumer (state → `rpm_common` → 2 champion → alert chống trùng → 1 transaction DB → publish), `reset_demo.py`. 27 test, gồm test đồng nhất train/serving từng giờ trên dữ liệu thật.
    - E2E thật trên host: 20 bệnh nhân / 1.834 giờ → đủ 1.834 vital_records + predictions, 1.834 message predictions-stream.
      - Chỉ 28 cảnh báo (19 RISK, 9 ANOMALY) cho 507 giờ dự báo CRITICAL (chống bão cảnh báo); 0 cảnh báo OPEN trùng.
      - Xử lý khoảng 130–190 ms/message: đặc trưng ~45 ms, Random Forest ~12 ms (sau khi ép `n_jobs=1`), LSTM-AE ~64 ms.
    - Chịu lỗi: kill cứng consumer giữa chừng rồi bật lại → 229/229 bản ghi, 0 trùng.
    - Tinh chỉnh thiết kế đã ghi vào docs:
      - `vital_records` lưu giá trị đo chưa điền;
      - state dựng lại từ toàn bộ đợt ICU (02_4);
      - `model_versions` unique `(model_name, mlflow_version)`, consumer tự đồng bộ champion (02_7);
      - `anomaly_score` sớm nhất ở `hour_index` 16, không phải giờ 12 (02_8, 02_9);
      - `DEFAULT_RISK_CRITICAL_THRESHOLD` để trống = dùng τ của champion.
    - Docker: `streaming/Dockerfile` + service `stream-consumer`/`stream-producer` (profile `app`), `.dockerignore`. Image `rpm-streaming:latest` 4,09 GB đã build. Smoke test trong Docker đạt: 74/74 bản ghi, nạp 2 champion qua `http://mlflow:5000`.
    - **Lỗi thật tìm ra khi smoke test Docker**: `anomaly_detector` v2 log từ Windows lưu đường dẫn artifact dạng `artifactsutoencoder.keras`, Linux không mở được.
      - Đã sửa wrapper (`artifact_path`) và đóng gói lại thành **v3** bằng `ml/src/repackage_anomaly.py`: cùng trọng số, điểm trùng khít v2 trên tập test, qua gate → champion.
      - Consumer tự chuyển cờ champion v2 → v3 trong `model_versions`.
  - **Giai đoạn E — Backend FastAPI: XONG (2026-09-11)**. API, quy ước và lệnh ở `backend/CLAUDE.md`.
    - 25 route theo UC01–UC13:
      - JWT 3 role, phân quyền theo phân công (403);
      - chuyển trạng thái cảnh báo OPEN → ACKNOWLEDGED → RESOLVED (409 nếu sai thứ tự);
      - `alert-settings` hiển thị τ của champion đọc từ MLflow;
      - retrain gọi Airflow (202, lỗi → 502).
    - Realtime:
      - Kafka listener (group `rpm-backend`) → WebSocket chỉ tới người được phân công;
      - email trong thread riêng, không gửi trùng nhờ `notification_logs`; `EMAIL_DELIVERY=log` mặc định;
      - `alert_update` khi bác sĩ đổi trạng thái cảnh báo.
    - 27 test trên DB `rpm_test` thật (TimescaleDB, migration Alembic).
    - Tích hợp thật với streaming (4 bệnh nhân, 3 tài khoản demo):
      - mỗi người chỉ nhận WebSocket của bệnh nhân mình phụ trách;
      - email tới đúng bác sĩ + điều dưỡng được phân công;
      - xác nhận/xử lý cảnh báo đẩy `alert_update` tức thì.
    - Sửa trong lúc làm:
      - JWT lộ trong log uvicorn (`/ws?token=`) → `RedactTokenFilter`;
      - `EmailStr` từ chối tên miền `.local` → kiểu `Email` riêng.
    - Docker: `backend/Dockerfile` (tự chạy `alembic upgrade head`), service `backend` (profile `app`, cổng 8000), Prometheus scrape `backend:8000/metrics`. Smoke test container đạt.
    - Tài khoản demo (`python -m app.seed --demo`, mật khẩu `demo12345`):
      - bs.an, bs.binh — mỗi người phụ trách nửa số bệnh nhân;
      - dd.cuong — phụ trách tất cả.
      - Admin mặc định `admin@rpm.local` / `admin12345` khi `.env` chưa có `ADMIN_*` — đổi khi triển khai.
- **Giai đoạn F — Frontend: đang làm.** Bước 1 xong (2026-09-11): mockup Claude Design canvas https://claude.ai/code/artifact/06619c98-443f-4157-be37-cef16741dc5d, nguồn `docs/design/mockups/` (8 màn hình + bảng thành phần + ghi chú phân tích). Đã soát bằng trình duyệt và sửa lỗi bố cục, số liệu khớp giữa các màn hình.
  - Người dùng yêu cầu **góc vuông** → `--radius: 0` (đã áp dụng lên canvas bản 2).
  - Tài liệu `02_8` đã viết lại có cấu trúc (design system, kiến trúc điều hướng, phân tích từng màn hình) kèm 9 ảnh `docs/design/mockups/png/*.png`, dùng được cho báo cáo Word.
  - **Chờ người dùng góp ý mockup trước khi code React.**
- **Việc tiếp theo**: **Giai đoạn F — Frontend React** (bám `frontend/CLAUDE.md`, `02_8_thiet_ke_giao_dien.md`, skill `csgo-case-opening-design` + `dataviz`):
  1. ~~Dựng mockup~~ (xong). Áp dụng góp ý của người dùng lên mockup nếu có (sửa `docs/design/mockups/build_mockups.py`, ghép lại canvas, cập nhật cùng URL).
  2. Màn hình theo 02_8.2:
     - đăng nhập;
     - dashboard bệnh nhân (badge rủi ro 4 giờ tới + NEWS2, realtime qua WebSocket);
     - chi tiết bệnh nhân (biểu đồ vitals + điểm bất thường, risk-timeline, cảnh báo + xác nhận/xử lý);
     - trung tâm cảnh báo;
     - trang quản trị gồm các tab người dùng, phân công, ngưỡng, giám sát mô hình.
  3. Test Vitest theo `02_10` mục 2.10.5 (badge theo mức rủi ro, chặn route theo role, hiển thị theo phân công).
  4. Chạy cùng: hạ tầng + consumer + producer + backend (hoặc `docker compose --profile app up -d`), rồi `python -m app.seed --demo`.
- **Quyết định đã chốt sau rà soát 2026-09-10** (người dùng đã duyệt):
  - Model rủi ro là **dự báo** mức NEWS2 cao nhất trong 4 giờ tới, không phân loại tức thời. Phân loại tức thời bị rò rỉ nhãn vì nhãn là hàm tất định của đặc trưng. Model phải thắng baseline persistence.
  - Drift với PSI ≥ 0,25 → **tự động** kích hoạt retrain; quality gate chặn model kém; Admin vẫn retrain thủ công được.
  - **Điều dưỡng được phân công như bác sĩ** (bảng `patient_assignments` nhiều–nhiều). Bác sĩ/điều dưỡng chỉ xem và nhận cảnh báo của bệnh nhân được phân công; Admin quản lý phân công (UC13).
- **Dataset**: đã tải MIMIC-III Clinical Database Demo v1.4 tại `mimic-iii-clinical-database-demo-1.4_data/` (thư mục gốc repo, đã bị `.gitignore` loại, KHÔNG nằm trong git). Mô tả đầy đủ dataset + lý do chọn: [`ml/README.md`](ml/README.md). Mô tả chi tiết ý nghĩa toàn bộ 26 file CSV và từng cột: [`ml/data_dictionary.md`](ml/data_dictionary.md). Thư mục dataset có thể chưa tồn tại trên máy khác/session khác — nếu không thấy, người dùng cần tải lại từ PhysioNet theo hướng dẫn trong `ml/README.md`.
- **Hạ tầng Docker**: đã sửa và **smoke test thật** ngày 2026-09-10, rồi `docker compose down` (volume vẫn giữ):
  - Kafka: produce/consume từ host qua `localhost:29092`.
  - MLflow 3.11.1: log model từ host → artifact nằm trong volume qua proxy `mlflow-artifacts:/`; đăng ký + alias `champion`; container khác tải được model qua `http://mlflow:5000` (cần `--allowed-hosts`).
  - Airflow: `airflow-init` chạy xong trước webserver/scheduler; REST API với basic auth → 200; không còn DAG ví dụ.
  - Đã nâng schema `mlflow_db` lên 3.x và sửa `artifact_location` của experiment `Default`. **Khi đổi phiên bản MLflow phải chạy `mlflow db upgrade`** trên `mlflow_db` trước khi khởi động server.
  - File `.env` trên máy chưa có các biến mới của `.env.example` (topic predictions/alerts, `REPLAY_*`, `DEFAULT_*`, `AIRFLOW_API_URL`) — bổ sung khi bắt đầu code Giai đoạn D/E.
- **Còn phụ thuộc người dùng**: file mẫu báo cáo Word (.docx) của trường — chưa có, chỉ chặn bước cuối cùng (mục 6), không chặn code.

## Kiến trúc tổng quan

```
MIMIC-III Demo → preprocess (common/rpm_common, lưới 1 giờ) → Kafka producer (replay nhóm stream) → topic vitals-stream
  → Stream consumer: feature (common/rpm_common) → [Dự báo rủi ro 4h tới | LSTM-AE anomaly] + alert (chống trùng)
  → PostgreSQL+TimescaleDB  +  topic predictions-stream / alerts-stream
  → FastAPI backend (REST + WebSocket + JWT, gửi email tới người được phân công) → React dashboard (realtime)
Song song: MLflow (tracking + registry, alias champion/challenger) ← training pipeline
           Airflow DAG drift_check (PSI/KS) → tự động trigger DAG retrain_pipeline → quality gate → chuyển alias champion
```

Chi tiết từng sơ đồ: `docs/design/02_1_so_do_chuc_nang.md` … `02_10_thiet_ke_test.md`.

## Cấu trúc thư mục & module CLAUDE.md riêng

- `backend/CLAUDE.md` — quy ước API, DB models, cách thêm endpoint/model mới
- `frontend/CLAUDE.md` — quy ước component, design system (CS:GO theme tùy biến), state management
- `ml/CLAUDE.md` — quy ước train/evaluate model, cách log vào MLflow
- `common/` — package `rpm_common` dùng chung cho `ml/` và `streaming/` (quy ước ở `ml/CLAUDE.md`)
- `streaming/CLAUDE.md` — Kafka producer + stream consumer, thứ tự xử lý 1 message, lệnh chạy

## Nguyên tắc chung khi code phần này

- **Không tự đổi kiến trúc/quyết định đã chốt** (Kafka, FastAPI+React, PostgreSQL+TimescaleDB, MLflow, Airflow, JWT 3 role Admin/Bác sĩ/Điều dưỡng) mà không hỏi lại — các quyết định này đã được thống nhất kỹ với người dùng qua nhiều vòng hỏi đáp.
- **Thiết kế đã có trước, code bám theo thiết kế** — nếu code cần lệch khỏi sơ đồ trong `docs/design/`, phải cập nhật lại tài liệu thiết kế tương ứng, không để lệch nhau.
- **Patient-level split theo `subject_id`**: 4 nhóm cố định train/validation/test/stream. Không bao giờ để cùng 1 bệnh nhân ở 2 nhóm; `test` chỉ dùng cho quality gate (xem `docs/design/02_9_thiet_ke_giai_thuat.md` mục 2.9.1c).
- **Không rò rỉ thông tin tương lai**: nhãn rủi ro là nhãn dự báo; mọi feature tại t chỉ dùng dữ liệu ≤ t; chỉ forward-fill, không nội suy.
- **Một nguồn code feature duy nhất**: mọi tính toán feature nằm trong `common/rpm_common`, không copy sang `ml/` hay `streaming/` (tránh lệch giữa lúc train và lúc chạy thật).
- **Champion–Challenger**: model mới chỉ nhận alias `champion` trên MLflow khi đạt quality gate. Gate gồm: ngưỡng tuyệt đối ở `02_10` mục 2.10.3, thắng baseline persistence, không kém champion trên cùng tập test. Không dùng stage `Production` (đã lỗi thời).
- **Cùng một phiên bản MLflow** (`3.11.1`) cho server (`infra/Dockerfile.mlflow`) và mọi client (`ml/`, `streaming/`, Airflow).
- Style giao diện: nền dark-theme lấy cảm hứng từ `csgo-case-opening-design` skill, tùy biến thêm màu ngữ nghĩa lâm sàng (xanh/vàng/đỏ theo risk level) — xem `docs/design/02_8_thiet_ke_giao_dien.md`. Không tự ý đổi sang theme y tế "an toàn" thông thường trừ khi người dùng yêu cầu lại.

## Lệnh hay dùng

```bash
# Hạ tầng nền (Kafka từ host: localhost:29092; trong mạng docker: kafka:9092)
docker compose up -d postgres zookeeper kafka mlflow prometheus grafana
docker compose up -d airflow-webserver airflow-scheduler   # tự chạy airflow-init trước

# Backend (chi tiết ở backend/CLAUDE.md; trên host cần POSTGRES_HOST=localhost KAFKA_BOOTSTRAP_SERVERS=localhost:29092)
cd backend && ../.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000

# Frontend (khi đã có code, Giai đoạn F)
cd frontend && npm run dev

# Test backend (cần postgres đang chạy; tự tạo DB rpm_test)
cd backend && ../.venv/Scripts/python -m pytest -q

# Môi trường Python (một lần, từ gốc repo)
python -m venv .venv
.venv\Scripts\python -m pip install -e common -r ml/requirements.txt

# Test phần dữ liệu (Giai đoạn C)
cd common && ..\.venv\Scripts\python -m pytest -q && cd ..
cd ml && ..\.venv\Scripts\python -m pytest -q && cd ..

# Tiền xử lý dữ liệu → ml/data/processed/
.venv\Scripts\python ml/src/preprocess.py

# Schema DB (Alembic, từ backend/) và streaming — chi tiết ở streaming/CLAUDE.md
cd backend && POSTGRES_HOST=localhost ../.venv/Scripts/python -m alembic upgrade head && cd ..
KAFKA_BOOTSTRAP_SERVERS=localhost:29092 MLFLOW_TRACKING_URI=http://localhost:5000 POSTGRES_HOST=localhost .venv/Scripts/python streaming/src/consumer.py
KAFKA_BOOTSTRAP_SERVERS=localhost:29092 .venv/Scripts/python streaming/src/producer.py --seconds-per-hour 1
cd streaming && ..\.venv\Scripts\python -m pytest -q && cd ..

# Train model — chạy trên host cần MLFLOW_TRACKING_URI=http://localhost:5000
.venv\Scripts\python ml/src/train.py            # mô hình rủi ro
.venv\Scripts\python ml/src/train_anomaly.py    # LSTM-Autoencoder
.venv\Scripts\python ml/src/evaluate.py         # bảng/hình báo cáo → ml/reports/
```
