# CLAUDE.md — Hệ thống giám sát bệnh nhân từ xa bằng Streaming + MLOps

Đồ án môn học. Kế hoạch tổng thể và các quyết định kiến trúc đã chốt nằm trong lịch sử hội thoại lúc lập plan; tài liệu thiết kế đầy đủ nằm ở `docs/design/` (đọc `docs/design/01_gioi_thieu.md` và `02_0_quy_trinh_thiet_ke.md` trước khi code bất kỳ phần nào).

## ⚠️ Trạng thái hiện tại (đọc mục này trước tiên)

> **Quy tắc**: mỗi khi hoàn thành xong 1 giai đoạn hoặc 1 mốc quan trọng, PHẢI cập nhật lại mục này (đặc biệt dòng "Đang ở đâu" và "Việc tiếp theo") trước khi kết thúc phiên làm việc — đây là cách duy nhất để phiên chat sau không bị mất ngữ cảnh.

- **Đang ở đâu**:
  - Giai đoạn A (thiết kế, mục 2) và Giai đoạn B (khung repo + hạ tầng Docker) đã xong, nhánh `master`.
  - 2026-09-10: **rà soát toàn bộ** thiết kế + hạ tầng + dữ liệu thật và sửa lại (commit `d25a37b`).
  - **Giai đoạn C — Dữ liệu & Model: phần dữ liệu đã xong; mô hình dự báo rủi ro đã train nhưng chưa qua gate; LSTM-AE chưa làm.**
    - `common/rpm_common`: mapping itemid, làm sạch, lưới 1 giờ, forward-fill, NEWS2 rút gọn, feature cửa sổ 6 giờ, baseline z-score, nhãn dự báo, hàm ghép `build_hourly_features`. 85 unit test qua, gồm test tính nhân quả (feature tại t không phụ thuộc dữ liệu sau t).
    - `ml/src/preprocess.py` + `ml/src/split.py`, 7 test qua. Đã chạy trên dữ liệu thật và sinh ra (trong `ml/data/processed/`, không nằm trong git):
      - `hourly.parquet`: 132 đợt ICU, 14.138 giờ;
      - `stream_replay.parquet`: 20 bệnh nhân, 1.834 giờ;
      - `summary.json`.
    - File chia nhóm cố định `ml/splits/subject_split.json`: 48/15/15/20 bệnh nhân có vitals, seed 42 — **không tạo lại**.
    - Môi trường: `.venv` ở gốc repo (tạo bằng `--system-site-packages`, đã cài `-e common`).
  - **Mô hình dự báo rủi ro (h = 4): code xong, đã chạy thật**:
    - Code: `ml/src/train.py` + `risk_models.py`, `metrics.py`, `gate.py`, `drift.py`; `rpm_common/risk.py`. 21 test ở `ml/`, 87 test ở `common/`.
    - CV Macro F1: Random Forest 0,622 (được chọn), Logistic Regression 0,618, XGBoost 0,608, persistence 0,565.
    - Trên tập test, với `τ_critical = 0,25` chọn trên validation:

      | Metric | Model | Persistence |
      |---|---|---|
      | Macro F1 | 0,639 | 0,547 |
      | Recall CRITICAL | 0,730 | 0,308 |
      | AUROC | 0,836 | — |

    - **Quality gate từ chối** vì Recall CRITICAL 0,730 < ngưỡng tuyệt đối 0,80. Trên MLflow, `risk_classifier` v1 mang alias `challenger`, tag `gate=rejected`; **chưa có `champion`**.
- **Việc tiếp theo**:
  1. **Làm ngay khi mở phiên mới** — người dùng đã chọn ngày 2026-09-10: *chọn τ bằng CV, giữ ngưỡng 0,80*.
     - Sửa `train.py`: chọn `τ_critical` trên dự đoán out-of-fold của GroupKFold trên train ∪ validation (63 bệnh nhân), thay vì chỉ trên validation (15 bệnh nhân). Model cuối vẫn fit trên train.
     - Cập nhật câu mô tả cách chọn τ ở `docs/design/02_9` mục 2.9.6 và `02_10` mục 2.10.3 cho khớp.
     - Chạy lại `train.py` **đúng 1 lần**. Nếu Recall CRITICAL trên test vẫn < 0,80 thì **hỏi lại người dùng**, không tự hạ ngưỡng trong `ml/src/gate.py`.
     - Ghi chú cho báo cáo mục 3.4: tập test đã được dùng 2 lần (lần chạy đầu + lần chạy lại).
     - Cần hạ tầng: `docker compose up -d postgres mlflow`, rồi đặt `MLFLOW_TRACKING_URI=http://localhost:5000`.
  2. LSTM-Autoencoder (cửa sổ 12 giờ, 6 kênh z-score, chỉ cửa sổ NORMAL), đánh giá bằng tiêm bất thường; viết `evaluate.py`. Thêm tensorflow 2.21.0, shap 0.51.0 vào `ml/requirements.txt` (máy đã cài sẵn).
  3. Bám `docs/design/02_9_thiet_ke_giai_thuat.md` mục 2.9.2–2.9.3, 2.9.5 và `02_10` mục 2.10.3.
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
- `streaming/` (tạo ở Giai đoạn D) — Kafka producer + stream consumer

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

# Backend (khi đã có code, Giai đoạn E)
cd backend && uvicorn app.main:app --reload

# Frontend (khi đã có code, Giai đoạn F)
cd frontend && npm run dev

# Test backend
cd backend && pytest

# Môi trường Python (một lần, từ gốc repo)
python -m venv .venv
.venv\Scripts\python -m pip install -e common -r ml/requirements.txt

# Test phần dữ liệu (Giai đoạn C)
cd common && ..\.venv\Scripts\python -m pytest -q && cd ..
cd ml && ..\.venv\Scripts\python -m pytest -q && cd ..

# Tiền xử lý dữ liệu → ml/data/processed/
.venv\Scripts\python ml/src/preprocess.py

# Train model (khi đã có code) — chạy trên host cần MLFLOW_TRACKING_URI=http://localhost:5000
.venv\Scripts\python ml/src/train.py
```
