# CLAUDE.md — Hệ thống giám sát bệnh nhân từ xa bằng Streaming + MLOps

Đồ án môn học. Kế hoạch tổng thể và các quyết định kiến trúc đã chốt nằm trong lịch sử hội thoại lúc lập plan; tài liệu thiết kế đầy đủ nằm ở `docs/design/` (đọc `docs/design/01_gioi_thieu.md` và `02_0_quy_trinh_thiet_ke.md` trước khi code bất kỳ phần nào).

## ⚠️ Trạng thái hiện tại (đọc mục này trước tiên)

> **Quy tắc**: mỗi khi hoàn thành xong 1 giai đoạn hoặc 1 mốc quan trọng, PHẢI cập nhật lại mục này (đặc biệt dòng "Đang ở đâu" và "Việc tiếp theo") trước khi kết thúc phiên làm việc — đây là cách duy nhất để phiên chat sau không bị mất ngữ cảnh.

- **Đang ở đâu**:
  - Giai đoạn A (thiết kế, mục 2) và Giai đoạn B (khung repo + hạ tầng Docker) đã xong, nhánh `master`.
  - 2026-09-10: **rà soát toàn bộ** thiết kế + hạ tầng + dữ liệu thật và sửa lại (commit `d25a37b`).
  - **Giai đoạn C — Dữ liệu & Model: dữ liệu xong; cả 2 mô hình đã qua gate và có `champion` (`risk_classifier` v2, `anomaly_detector` v2); còn `evaluate.py` (SHAP, h = 1 vs h = 4, nhãn proxy vs tử vong).**
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
- **Việc tiếp theo**:
  1. `ml/src/evaluate.py` cho báo cáo 3.4/3.5 (chỉ đọc model/metric đã có, **không chọn lại gì trên test**):
     - SHAP cho `risk_classifier@champion` (mục 2.9.2);
     - so sánh h = 1 và h = 4 (chạy `train.py --horizon 1`, không đăng ký);
     - đối chiếu nhãn proxy với `hospital_expire_flag`;
     - bảng/biểu đồ ma trận nhầm lẫn, phân phối `anomaly_score`.
  2. Sau đó chuyển Giai đoạn D (streaming: producer + consumer dùng `rpm_common` và 2 model champion).
  3. Cần hạ tầng: `docker compose up -d postgres mlflow`, rồi đặt `MLFLOW_TRACKING_URI=http://localhost:5000`.
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
.venv\Scripts\python ml/src/train.py            # mô hình rủi ro
.venv\Scripts\python ml/src/train_anomaly.py    # LSTM-Autoencoder
```
