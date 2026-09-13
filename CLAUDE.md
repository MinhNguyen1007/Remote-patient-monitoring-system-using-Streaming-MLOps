# CLAUDE.md — Hệ thống giám sát bệnh nhân từ xa bằng Streaming + MLOps

Đồ án môn học. Kế hoạch tổng thể và các quyết định kiến trúc đã chốt nằm trong lịch sử hội thoại lúc lập plan; tài liệu thiết kế đầy đủ nằm ở `docs/design/` (đọc `docs/design/01_gioi_thieu.md` và `02_0_quy_trinh_thiet_ke.md` trước khi code bất kỳ phần nào).

## ⚠️ Trạng thái hiện tại (đọc mục này trước tiên)

> **Quy tắc**: mỗi khi hoàn thành xong 1 giai đoạn hoặc 1 mốc quan trọng, PHẢI cập nhật lại mục này (đặc biệt dòng "Đang ở đâu" và "Việc tiếp theo") trước khi kết thúc phiên làm việc — đây là cách duy nhất để phiên chat sau không bị mất ngữ cảnh.

- **Đang ở đâu**:
  - Giai đoạn A (thiết kế, mục 2) và Giai đoạn B (khung repo + hạ tầng Docker) đã xong, nhánh `master`.
  - 2026-09-10: **rà soát toàn bộ** thiết kế + hạ tầng + dữ liệu thật và sửa lại (commit `d25a37b`).
  - **Giai đoạn C — Dữ liệu & Model: XONG (2026-09-11).** Cả 2 mô hình có `champion` (`risk_classifier` v2, `anomaly_detector` **v3** = v2 đóng gói lại, cùng trọng số); bảng/hình cho báo cáo ở `ml/reports/evaluation.md`.
    - `packages/common` (`rpm_common`): mapping itemid, làm sạch, lưới 1 giờ, forward-fill, NEWS2 rút gọn, feature cửa sổ 6 giờ, baseline z-score, nhãn dự báo, hàm ghép `build_hourly_features`, cửa sổ 12 giờ + điểm bất thường (`anomaly.py`). 99 unit test qua, gồm test tính nhân quả (feature tại t không phụ thuộc dữ liệu sau t).
    - `rpm_ml/data/preprocess.py` + `split.py`, 7 test qua. Đã chạy trên dữ liệu thật và sinh ra (trong `ml/data/processed/`, không nằm trong git):
      - `hourly.parquet`: 132 đợt ICU, 14.138 giờ;
      - `stream_replay.parquet`: 20 bệnh nhân, 1.834 giờ;
      - `summary.json`.
    - File chia nhóm cố định `ml/splits/subject_split.json`: 48/15/15/20 bệnh nhân có vitals, seed 42 — **không tạo lại**.
    - Môi trường: `.venv` ở gốc repo (tạo bằng `--system-site-packages`, đã cài editable `packages/common`, `ml`, `services/streaming`).
  - **Mô hình dự báo rủi ro (h = 4): xong, `risk_classifier` v2 là `champion`**:
    - Code: `rpm_ml/training/train_risk.py` + `models/risk.py`, `evaluation/metrics.py`, `evaluation/gate.py`, `drift/stats.py`; `rpm_common/risk.py`. 41 test ở `ml/` (cả 2 mô hình).
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
    - Code: `rpm_ml/training/train_anomaly.py`, `models/anomaly.py` (kiến trúc + wrapper pyfunc: cửa sổ z-score gốc (n, 12, 6) → `anomaly_score`), `evaluation/injection.py`; `rpm_common/anomaly.py` (`make_windows`, `latest_window`, `center_windows`, ECDF).
    - Cửa sổ NORMAL: train 1.146, validation 334, test 485.
    - v1 (chưa căn giữa): test Precision 0,23, Recall 0,15, AUROC 0,850, gắn cờ nhầm 5,5% → trượt gate cũ (P, R ≥ 0,7) → tag `gate=rejected`.
    - Chẩn đoán **chỉ trên train ∪ validation** (GroupKFold): tiêu chí 0,7/0,7 tại τ = 0,99 không đạt được với dữ liệu này, vì bất thường tiêm nằm trong độ biến thiên tự nhiên. Căn giữa cửa sổ làm ngưỡng ổn định hơn nhiều giữa các bệnh nhân.
    - **Người dùng chọn**: căn giữa cửa sổ theo kênh + gate **AUROC ≥ 0,75** và không kém champion (`MIN_AUROC_ANOMALY`). P/R/F1 chỉ báo cáo.
    - v2 (run `b96c9105a15f4f0a84466277e91eb1f1`), trên test: **AUROC 0,864**, Precision 0,727, Recall 0,167, F1 0,271, gắn cờ nhầm 0,7%. Recall theo loại: spike 0,25, level shift 0,19, drift 0,06.
    - **Ghi chú bắt buộc cho báo cáo 3.4/3.5**: test của mô hình bất thường đã dùng 2 lần; gate đổi sau khi xem kết quả test lần đầu; recall thấp ở τ = 0,99 (chi tiết `02_9` mục 2.9.3, `02_10` mục 2.10.3).
  - **Đánh giá cho báo cáo** (`rpm_ml/evaluation/report.py` → `ml/reports/`, commit vào git; chạy lại khi champion đổi):
    - h = 1 (run log riêng, không đăng ký): model Macro F1 0,578 < persistence 0,621, dù Recall CRITICAL 0,784 so với 0,486. Ở tầm 1 giờ, persistence rất khó thắng vì vitals tự tương quan mạnh → lý do chọn h = 4.
    - SHAP lớp CRITICAL: `news2_max_6h`, `news2_score`, `respiratory_rate_mean_6h`, `heart_rate` đứng đầu.
    - Nhãn proxy: tỷ lệ giờ CRITICAL 19,1% ở đợt ICU tử vong tại viện so với 3,6% ở đợt sống sót; AUROC mức đợt 0,718.
    - Anomaly trên dữ liệu thật (không tiêm), cửa sổ test theo mức NEWS2 cao nhất trong 12 giờ: tỷ lệ gắn cờ NORMAL 0,6%, WARNING 17,4%, CRITICAL 34,8%. AUROC CRITICAL so với NORMAL 0,837 — bằng chứng thực nghiệm cho mô hình bất thường ngoài phần tiêm tổng hợp.
  - **Giai đoạn D — Streaming: XONG (2026-09-11)**. Quy ước và lệnh ở `services/streaming/CLAUDE.md`.
    - Schema DB: `services/backend/app/db/models.py` + Alembic migration `0001` (hypertable `vital_records`, `predictions`), đã `upgrade head` trên `rpm_db`.
    - `services/streaming`: producer (replay + `--drift`), consumer (state → `rpm_common` → 2 champion → alert chống trùng → 1 transaction DB → publish), `reset_demo.py`. 27 test, gồm test đồng nhất train/serving từng giờ trên dữ liệu thật.
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
    - Docker: `services/streaming/Dockerfile` + service `stream-consumer`/`stream-producer` (profile `app`), `.dockerignore`. Image `rpm-streaming:latest` 4,09 GB đã build. Smoke test trong Docker đạt: 74/74 bản ghi, nạp 2 champion qua `http://mlflow:5000`.
    - **Lỗi thật tìm ra khi smoke test Docker**: `anomaly_detector` v2 log từ Windows lưu đường dẫn artifact dạng `artifactsutoencoder.keras`, Linux không mở được.
      - Đã sửa wrapper (`artifact_path`) và đóng gói lại thành **v3** bằng `rpm_ml/training/repackage_anomaly.py`: cùng trọng số, điểm trùng khít v2 trên tập test, qua gate → champion.
      - Consumer tự chuyển cờ champion v2 → v3 trong `model_versions`.
  - **Giai đoạn E — Backend FastAPI: XONG (2026-09-11)**. API, quy ước và lệnh ở `services/backend/CLAUDE.md`.
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
    - Docker: `services/backend/Dockerfile` (tự chạy `alembic upgrade head`), service `backend` (profile `app`, cổng 8000), Prometheus scrape `backend:8000/metrics`. Smoke test container đạt.
    - Tài khoản demo (`python -m app.seed --demo`, mật khẩu `demo12345`):
      - bs.an, bs.binh — mỗi người phụ trách nửa số bệnh nhân;
      - dd.cuong — phụ trách tất cả.
      - Admin mặc định `admin@rpm.local` / `admin12345` khi `.env` chưa có `ADMIN_*` — đổi khi triển khai.
- **Giai đoạn F — Frontend React: XONG phần code (2026-09-11)**; người dùng tạm chấp nhận mockup (sẽ nâng cấp giao diện sau).
  - Mockup: https://claude.ai/code/artifact/06619c98-443f-4157-be37-cef16741dc5d (bản góc vuông), phân tích ở `02_8`, ảnh `docs/design/mockups/png/`.
  - `services/frontend/`: Vite 8 + React 19 + TS 7 + Tailwind v4 + Base UI/CVA (template skill), đủ 8 màn hình theo mockup, route chặn theo vai trò, WebSocket tự nối lại, cập nhật realtime bằng hàm thuần (`lib/realtime.ts`). Quy ước ở `frontend/CLAUDE.md`.
  - 23 test Vitest; `npm run typecheck` và `npm run build` sạch. Đã chạy thật với backend + streaming (20 bệnh nhân): API và WebSocket qua proxy `/api` của Vite đều hoạt động.
  - Bổ sung backend để khớp mockup:
    - `latest` trả vitals sau forward-fill (trùng `vitals_filled`);
    - `recent_risk_levels` (12 giờ) cho dải trên thẻ;
    - `news2_components` tính bằng `rpm_common.news2` (backend giờ cài `rpm_common`);
    - consumer đồng bộ thêm metric `persistence_test_*` vào `model_versions`.
    - Backend 30 test.
  - Docker: `services/frontend/Dockerfile` + `nginx.conf` (proxy `/api` + WebSocket tới backend), service `frontend` cổng 3000 (profile `app`).
  - **Chưa soát trực quan các màn hình cần đăng nhập trên trình duyệt**: quy tắc an toàn không cho Claude tự nhập mật khẩu vào trang web. Người dùng đăng nhập ở tab trình duyệt, hoặc tự xem ở http://127.0.0.1:5173.
- **Giai đoạn G — MLOps vận hành: XONG (2026-09-11)**, kiểm chứng thật trên Docker Compose. Chi tiết số liệu: `docs/report/ghi_chu_bao_cao.md` mục 3.4(d) và hạn chế 11–14.
  - **Hai quyết định mới của người dùng** (đã ghi vào 02_9 mục 2.9.4):
    - Ngưỡng drift **hiệu chỉnh theo từng đặc trưng** (sàn 0,25, tỷ lệ báo nhầm ≈ 5%/lần kiểm tra), thay cho "max PSI ≥ 0,25". Lý do: với cửa sổ ~20 bệnh nhân, ngưỡng chung gắn cờ 93% cửa sổ không drift. Ngưỡng log thành `drift_thresholds.json` cạnh `reference_stats.json` mỗi lần train/retrain; champion v2 được bổ sung bằng `drift_detect.py backfill-thresholds`.
    - `drift_check` chạy **2 phút/lần** (= 24 giờ dữ liệu ở tốc độ mặc định). Cửa sổ phải đủ 24 nhịp và ≥ 200 bản ghi; không có dữ liệu mới thì bỏ qua.
    - Thông báo Admin qua Kafka topic `mlops-events` → backend (email + WebSocket); email chỉ khi bắt đầu đợt drift mới hoặc đã kích hoạt retrain.
  - Code: `rpm_ml` drift/detect, pipelines/retrain, pipelines/policy, data/stream_data, storage/db, storage/events; `training/train_risk.py`/`train_anomaly.py` tách thành `train_risk_model`/`train_anomaly_model` dùng chung. DAG ở `infra/airflow/dags/`. Image `infra/Dockerfile.airflow` (Airflow 2.9.3-python3.11 + venv `/opt/rpm-venv`, bỏ shap/pytest vì shap 0.51 cần numpy ≥ 2). Backend: migration `0002`, listener tự tạo topic trước khi subscribe. Frontend: tab Giám sát mô hình tự làm mới, hiện lý do gate.
  - Test: common 99, ml 61, streaming 27, backend 34, frontend 23 (tổng 244).
  - **Kết quả chạy thật**:
    - phát lại sạch → 2 lần kiểm tra, không drift;
    - `--drift` → drift SpO2 → tự retrain → risk v3 **từ chối** (Macro F1 0,612 < 0,623), anomaly v4 promote (bằng điểm v3, do lúc đó chưa có dữ liệu stream mới — đã sửa bằng điều kiện 24 nhịp);
    - chạy lại → bị chặn bởi cooldown 1 giờ, không gửi email lặp;
    - UC10 qua API → risk v4 từ chối (Macro F1 0,631 nhưng Recall CRITICAL 0,759 < 0,790), anomaly v5 từ chối (AUROC 0,853 < 0,864).
  - **Champion hiện tại**: `risk_classifier` v2, `anomaly_detector` **v4**. `ml/reports/` đã sinh lại.
  - Nếu bật lại mà các lần drift bị chặn, kiểm tra cooldown 1 giờ tính từ lần retrain gần nhất.
- **Tổ chức lại toàn bộ repo (2026-09-11, người dùng yêu cầu — thấy cấu trúc cũ rối)**: `services/{backend,frontend,streaming}`, `packages/common`, `ml/src/rpm_ml/{data,models,training,evaluation,drift,pipelines,storage}`, `rpm_streaming/{producer,consumer,kafka,storage}`, dataset chuyển vào `ml/data/raw/`, script chạy dạng `python -m`. Chi tiết ở mục "Cấu trúc thư mục" bên dưới và `README.md` (viết lại).
  - Đã kiểm chứng: 244 test qua; 4 image build lại và chạy trong Docker; model anomaly log bằng code mới nạp được trong container consumer (không cài `rpm_ml`); DAG `drift_check` và bước `build` của retrain chạy trong container.
  - `.venv` đã cài lại editable theo đường dẫn mới (`packages/common`, `ml`, `services/streaming`). Máy/phiên khác phải cài lại như vậy.
- **Tạm dừng 2026-09-11 (theo yêu cầu người dùng) sau Giai đoạn G + tổ chức lại repo**, đã commit. Mọi container đã `docker compose --profile app down` (volume vẫn giữ: DB, MLflow registry, Airflow DB).
  - Bật lại: `docker compose up -d postgres zookeeper kafka mlflow`, `docker compose up -d airflow-webserver airflow-scheduler`, `docker compose --profile app up -d`.
  - DB đang chứa dữ liệu của lần phát lại `--drift` cuối (72 nhịp). Trước khi đo/demo mới: dừng consumer rồi `python -m rpm_streaming.storage.reset_demo --yes`.
  - **Số liệu cho báo cáo gom ở [`docs/report/ghi_chu_bao_cao.md`](docs/report/ghi_chu_bao_cao.md)** (bản đồ mục báo cáo → nguồn, phiên bản công nghệ, kết quả, hạn chế bắt buộc công khai, tài liệu tham khảo). Cập nhật file đó sau H.
- **Giai đoạn H — kiểm thử tích hợp & phi chức năng: XONG phần tự động (2026-09-12)**. Bộ test ở `tests/e2e/` (README riêng), 10 test chạy ~6 phút trên hệ thống thật.
  - Không mock gì: Kafka + TimescaleDB + MLflow từ docker compose; **stream consumer và backend do chính bộ test khởi động** dưới dạng tiến trình con nên giết/bật lại được (2.10.4).
  - Phủ 2.10.2 dòng 1, 2, 3, 6 và 2.10.4 cả 3 dòng. Dòng 4 (retrain thủ công) nằm ở `services/backend/tests`, dòng 5 (drift → retrain) đã chạy thật ở Giai đoạn G.
  - **Độ trễ đầu–cuối đạt ngưỡng**: p95 **1,30–1,62 giây** qua 3 lần chạy (20 bệnh nhân cùng lúc, tốc độ mặc định; toàn bộ mẫu 1,52–1,64). Bảng của lần chạy gần nhất ở `tests/e2e/reports/latency.md` (sinh tự động, commit vào git).
  - Chịu lỗi: giết cứng consumer → đủ bản ghi, 0 giờ trùng, không cảnh báo trùng; tắt backend giữa chừng → bật lại đọc tiếp offset cũ, `notification_logs` đúng người được phân công.
  - Tổng test: 254 (common 99, ml 61, streaming 27, backend 34, frontend 23, e2e 10).
  - ⚠ Bộ E2E **xóa dữ liệu phát lại** trong `rpm_db` khi bắt đầu (như `reset_demo`), giữ users/model_versions/alert_settings/drift_reports.
  - **Lỗi thật bộ E2E tìm ra**: `sync_champion` của consumer ghi đè `model_versions.gate_status = 'PROMOTED'` mỗi lần đồng bộ, nên trỏ alias `champion` sang version đã bị gate từ chối làm tab Giám sát mô hình báo sai (dòng vẫn giữ `gate_reasons` từ chối). Đã sửa (`ON CONFLICT` không ghi `gate_status` nữa), sửa dòng sai trong DB, rebuild `rpm-streaming`, thêm khẳng định chống hồi quy trong `test_3_model_reload.py`.
  - Ba điểm đáng nhớ khi sửa bộ test (đã ghi trong README): group Kafka phải riêng từng phiên (stream consumer dùng `earliest` nên được commit sẵn offset cuối topic); khẳng định dựa trên log phải dùng `log_since_last_start()`; test cần thấy cảnh báo **mới** phải đi qua fixture `alert_slate` (cảnh báo OPEN cũ + cooldown sẽ chặn).
  - **Ảnh giao diện thật: XONG (2026-09-12)** — người dùng tự đăng nhập và chụp 9 màn hình, đặt ở `images/` (đã commit). Soát ảnh phát hiện thêm 1 lỗi frontend (thẻ "Diễn biến bất thường" nói sai lý do thiếu điểm), đã sửa → **`images/3_patient_detail.png` nên chụp lại**.
- **Giai đoạn I — viết bài báo & báo cáo: XONG nội dung (2026-09-12)**. Mọi thứ liên quan ở [`docs/report/README.md`](docs/report/README.md).
  - Người dùng đưa **2 tệp mẫu** ở `docs/report/` (chỉ có trên máy, `.gitignore` loại khỏi repo public vì chứa tên/MSSV/email người khác): `Mau_Bai_bao_Project_NLP.md` (bài báo 5 mục) và `BaoCao_GiaoDichDinhLuong.md` (báo cáo đồ án 5 chương + phần đầu/cuối). Mẫu thứ hai là đồ án trước của chính người dùng → dùng lại được trường/khoa/khoá/thể thức cam đoan.
  - **Quyết định của người dùng 2026-09-12**: giữ đúng 5 chương của mẫu, nhét 10 mục thiết kế vào Ch2 (chức năng, use case, DFD, ERD) + Ch3 (activity, sequence, class, giải thuật, giao diện), thiết kế test vào 4.4 — **không** thêm chương mới, **không** đẩy xuống phụ lục.
  - **Nội dung đã viết xong (2026-09-12)**: `bao_cao_do_an.md` ~19.600 từ (5 chương, **29 hình, 18 bảng** — tất cả đánh số đúng thứ tự xuất hiện và khớp 2 danh mục) và `bai_bao.md` ~7.350 từ (5 mục, 7 hình, 4 bảng); 17 hình PNG ở `docs/report/figures/`.
  - **12 tài liệu tham khảo đã tra cứu và xác minh** (MIMIC-III Johnson 2016, MIMIC-III Demo, PhysioNet Goldberger 2000, NEWS2 RCP 2017, tổng quan Muralitharan JMIR 2021, LSTM-AE Malhotra 2016, drift Gama 2014, technical debt Sculley 2015, LSTM Hochreiter 1997, Random Forest Breiman 2001, XGBoost Chen 2016, SHAP Lundberg 2017). Mọi trích dẫn `[n]` trong thân bài đều khớp danh mục ở cả 2 tài liệu (đã kiểm bằng script).
  - **Theo yêu cầu người dùng "chưa biết thì không ghi"**: đã bỏ hẳn (không để chỗ trống) tên môn học, mã lớp, tên giảng viên hướng dẫn, danh sách thành viên nhóm; **bỏ luôn 2 mục "LÀM VIỆC NHÓM" và "TỰ ĐÁNH GIÁ"** của mẫu. Lời cảm ơn và trang cam đoan viết "giảng viên hướng dẫn" chung. Thêm lại khi người dùng cung cấp.
  - **Người dùng xác nhận 2026-09-12: KHÔNG cần bản Word.** Bản giao là hai tệp Markdown; `build_docx.py` giữ lại nhưng không còn là bước bắt buộc, và `reference.docx` không cần làm nữa.
  - **Hai script bảo trì ở `docs/report/tools/`** (dùng lại thay vì viết lại):
    - `render_figures.py` — trích khối ```mermaid từ `docs/design/02_*.md` + `figures/src/*.mmd` rồi render PNG nền trắng. **Chạy lại mỗi khi sửa sơ đồ thiết kế.** Thêm/bớt khối mermaid làm lệch chỉ số → script báo lỗi, phải cập nhật bảng `NAMES`.
    - `check_report.py` — soát 5 loại lỗi (số hình/bảng lệch thứ tự, chú thích lệch danh mục, bảng chưa đánh số, trích dẫn không khớp danh mục TLTK, ảnh thiếu); `--renumber` để đánh số lại và sinh lại 2 danh mục. Cả 5 lỗi này **đều đã từng xảy ra** ở lần viết đầu → chạy sau mỗi lần sửa nội dung.
  - **Hai lỗi thiết kế lệch code, tìm ra khi tách sơ đồ (2026-09-12, đã sửa)**: cả `02_3` mục 2.3.1 và `02_4` mục 2.4.1 đều vẽ **hai lần ghi DB** (prediction rồi alert riêng) và đặt bước quyết định cảnh báo **sau** khi publish prediction. Code thực tế quyết định cảnh báo trước, rồi ghi vital_record + prediction + alert trong **một transaction**, publish, cuối cùng mới commit offset.
  - **Về việc hình có lọt trang in**: tiêu chí đúng là **cỡ chữ sau khi thu hình**, không phải tỉ lệ khung hình (`cỡ chữ pt ≈ 794 × bề_rộng_in_cm / bề_rộng_ảnh_px` với ảnh render `-s 2`; ngưỡng đọc được ~7 pt). Theo tiêu chí này các sơ đồ tuần tự và `dfd_level1` khó in nhất, không phải sơ đồ hoạt động. Không còn là vấn đề chặn vì bản giao là Markdown.
  - **Chặn ở người dùng**: thông tin hành chính trang bìa và logo trường (danh sách đủ ở `docs/report/README.md` mục "Còn thiếu").
- **Ba sơ đồ tổng quát vẽ tay bằng HTML/CSS (2026-09-12, commit `e000f6f` + `bfdff0b`)**: `so_do_tong_quat`, `mo_hinh_train_serve_monitor`, `vong_lap_mlops` ở `docs/report/figures/`; nguồn HTML + 3 tệp CSS phong cách ở `figures/src/`, render bằng `tools/render_html_figures.py`, logo Simple Icons (CC0) ở `figures/logos/`. Mỗi sơ đồ bám một tệp mẫu người dùng đưa ở `images/Ve_So_Do/` (chỉ có trên máy, `.gitignore` loại khỏi repo public). Ba lỗi đã mắc (khai báo nhãn phụ phải toàn cục, mũi tên dọc không xuyên hộp nhánh rẽ, đọc mũi tên thành câu để kiểm chiều) ghi ở `docs/report/README.md`.
- **Tạm dừng 2026-09-12 tối (người dùng: "mai làm tiếp")**. Cây làm việc sạch, mọi thứ đã commit tới `bfdff0b`; toàn bộ container đã `docker compose down` (volume vẫn giữ: `rpm_db`, MLflow registry, Airflow DB, Kafka).
  - Bật lại: `docker compose up -d postgres zookeeper kafka mlflow prometheus grafana`, `docker compose up -d airflow-webserver airflow-scheduler`, `docker compose --profile app up -d`.
  - DB đang giữ dữ liệu của lần phát lại gần nhất. Trước khi demo/đo mới: dừng consumer rồi `python -m rpm_streaming.storage.reset_demo --yes`.
  - **Việc tiếp theo (1 việc về ảnh giao diện, cần người dùng đăng nhập vì Claude không được tự nhập mật khẩu)**:
    1. `images/3_patient_detail.png` **vẫn là ảnh cũ còn lỗi**: bệnh nhân đã ở giờ thứ 88, dải bất thường đầy đủ, nhưng thẻ "Diễn biến bất thường" vẫn ghi "Chưa đủ 16 giờ" (lỗi đã sửa trong code, ảnh chưa chụp lại). Đang được dùng ở `bao_cao_do_an.md` dòng 886 **và ở mục "Giao diện" của `README.md`** → chụp lại là cập nhật được cả hai.
    2. ~~`images/3_patient_detail_v2.png` đặt sai tên~~ — **xong 2026-09-13**: đã `git mv` đè lên `images/2_patient_list.png` (bản cũ ghi sai "Chưa đủ 16 giờ" cho bệnh nhân giờ thứ 88 đã bị thay).
- **Đẩy lên GitHub công khai: XONG (2026-09-13)** — https://github.com/MinhNguyen1007/Remote-patient-monitoring-system-using-Streaming-MLOps
  - **Nhánh đổi tên `master` → `main`** cho khớp default branch của remote. Remote `origin` đã cấu hình, `main` theo dõi `origin/main`. Code cũ trên repo bị ghi đè bằng force push (người dùng yêu cầu bỏ hết).
  - **Lịch sử đã bị viết lại bằng `git filter-branch`** để xoá hẳn khỏi mọi commit: `docs/report/BaoCao_GiaoDichDinhLuong.md`, `docs/report/Mau_Bai_bao_Project_NLP.md`, `images/Ve_So_Do/` (tệp/ảnh mẫu do người khác soạn, chứa tên + MSSV + email của họ; repo là public). Ba đường dẫn này đã thêm vào `.gitignore`, **vẫn còn trên máy** để tham khảo khi viết báo cáo.
    - Hash của mọi commit đã đổi. Nhánh `backup-truoc-khi-day-github` (local) giữ lịch sử gốc trước khi viết lại; `refs/original/` cũng còn. **Đừng đẩy nhánh backup lên remote.**
  - `README.md` viết lại hoàn toàn cho người đọc ngoài dự án (bài toán, tính năng, kiến trúc, ảnh giao diện, quickstart Docker, bảng kết quả, cấu trúc, test, hạn chế, trích dẫn MIMIC-III). `LICENSE` = MIT nguyên văn (GitHub phải nhận đúng `spdx_id: MIT`, nên **không nối thêm gì vào cuối file đó**); ghi chú dữ liệu/NEWS2/logo nằm ở `NOTICE`.
  - `images/3_patient_detail_v2.png` (đặt sai tên) đã `git mv` đè lên `images/2_patient_list.png`.
  - **Repo trên GitHub chưa có description và topics** — người dùng tự đặt trong Settings, hoặc bảo Claude làm khi đã `gh auth login`.
- **Quyết định đã chốt sau rà soát 2026-09-10** (người dùng đã duyệt):
  - Model rủi ro là **dự báo** mức NEWS2 cao nhất trong 4 giờ tới, không phân loại tức thời. Phân loại tức thời bị rò rỉ nhãn vì nhãn là hàm tất định của đặc trưng. Model phải thắng baseline persistence.
  - Drift → **tự động** kích hoạt retrain; quality gate chặn model kém; Admin vẫn retrain thủ công được. (Ngưỡng drift đổi thành ngưỡng hiệu chỉnh theo từng đặc trưng ngày 2026-09-11, xem Giai đoạn G.)
  - **Điều dưỡng được phân công như bác sĩ** (bảng `patient_assignments` nhiều–nhiều). Bác sĩ/điều dưỡng chỉ xem và nhận cảnh báo của bệnh nhân được phân công; Admin quản lý phân công (UC13).
- **Dataset**: đã tải MIMIC-III Clinical Database Demo v1.4 tại `ml/data/raw/mimic-iii-clinical-database-demo-1.4/` (chuyển từ gốc repo vào đây ngày 2026-09-11; `.gitignore` loại, KHÔNG nằm trong git). Mô tả đầy đủ dataset + lý do chọn: [`ml/README.md`](ml/README.md). Mô tả chi tiết ý nghĩa toàn bộ 26 file CSV và từng cột: [`ml/data_dictionary.md`](ml/data_dictionary.md). Thư mục dataset có thể chưa tồn tại trên máy khác/session khác — nếu không thấy, người dùng cần tải lại từ PhysioNet theo hướng dẫn trong `ml/README.md`.
- **Hạ tầng Docker**: đã sửa và **smoke test thật** ngày 2026-09-10, rồi `docker compose down` (volume vẫn giữ):
  - Kafka: produce/consume từ host qua `localhost:29092`.
  - MLflow 3.11.1: log model từ host → artifact nằm trong volume qua proxy `mlflow-artifacts:/`; đăng ký + alias `champion`; container khác tải được model qua `http://mlflow:5000` (cần `--allowed-hosts`).
  - Airflow: `airflow-init` chạy xong trước webserver/scheduler; REST API với basic auth → 200; không còn DAG ví dụ.
  - Đã nâng schema `mlflow_db` lên 3.x và sửa `artifact_location` của experiment `Default`. **Khi đổi phiên bản MLflow phải chạy `mlflow db upgrade`** trên `mlflow_db` trước khi khởi động server.
  - File `.env` trên máy đã có đủ biến của `.env.example` (bổ sung ở Giai đoạn D/E/G); chưa đặt `ADMIN_*` nên Admin dùng mật khẩu mặc định.
- **Còn phụ thuộc người dùng**: thông tin hành chính trang bìa + logo trường (xem Giai đoạn I). Hai tệp mẫu báo cáo/bài báo đã có ở `docs/report/`.

## Kiến trúc tổng quan

```
MIMIC-III Demo → preprocess (rpm_common, lưới 1 giờ) → Kafka producer (replay nhóm stream) → topic vitals-stream
  → Stream consumer: feature (rpm_common) → [Dự báo rủi ro 4h tới | LSTM-AE anomaly] + alert (chống trùng)
  → PostgreSQL+TimescaleDB  +  topic predictions-stream / alerts-stream
  → FastAPI backend (REST + WebSocket + JWT, gửi email tới người được phân công) → React dashboard (realtime)
Song song: MLflow (tracking + registry, alias champion/challenger) ← training pipeline
           Airflow DAG drift_check (PSI/KS, ngưỡng hiệu chỉnh) → tự động trigger DAG retrain_pipeline → quality gate → chuyển alias champion
           Airflow → topic mlops-events → backend → WebSocket + email cho Admin
```

Chi tiết từng sơ đồ: `docs/design/02_1_so_do_chuc_nang.md` … `02_10_thiet_ke_test.md`.

## Cấu trúc thư mục & module CLAUDE.md riêng

Tổ chức lại ngày 2026-09-11 theo yêu cầu người dùng (gọn, chia theo chức năng). Tổng quan cho người đọc: `README.md`.

```
services/backend/       FastAPI — services/backend/CLAUDE.md (API, DB models, migration, sự kiện realtime, email)
services/frontend/      React   — services/frontend/CLAUDE.md (design system CS:GO tùy biến, góc vuông, realtime)
services/streaming/     Kafka   — services/streaming/CLAUDE.md (package rpm_streaming: producer/ consumer/ kafka/ storage/)
ml/                     ML/MLOps — ml/CLAUDE.md (package rpm_ml: data/ models/ training/ evaluation/ drift/ pipelines/ storage/)
packages/common/        rpm_common — đặc trưng dùng chung cho ml/ và services/streaming (quy ước ở ml/CLAUDE.md)
infra/                  Dockerfile MLflow/Airflow, DAG Airflow (infra/airflow/dags), Prometheus/Grafana
                        (dashboard provisioning sẵn), init Postgres, smoke_test.py
tests/e2e/              Test tích hợp & phi chức năng trên hệ thống thật — tests/e2e/README.md (Giai đoạn H)
docs/                   design/ (thiết kế mục 1–2), report/ (ghi chú viết báo cáo)
```

- Ba package Python cài editable vào `.venv`: `rpm_common` (`packages/common`), `rpm_ml` (`ml`), `rpm_streaming` (`services/streaming`); script chạy dạng `python -m <package>.<module>`.
- Mọi Dockerfile dùng build context = gốc repo và **giữ đúng bố cục thư mục như trong repo** trong image (vd `/app/services/streaming/src`), vì đường dẫn dữ liệu tính từ vị trí file.
- Model `anomaly_detector` ≤ v5 mang file wrapper tên cũ (`anomaly_model.py`) và vẫn nạp được; version mới chụp kèm khung `rpm_ml/models/anomaly.py` (`serving_code_paths`).
- `.vscode/settings.json` (có trong git) ẩn `__pycache__`, `.pytest_cache`, `node_modules`, `.venv` khỏi Explorer.

## Nguyên tắc chung khi code phần này

- **Không tự đổi kiến trúc/quyết định đã chốt** (Kafka, FastAPI+React, PostgreSQL+TimescaleDB, MLflow, Airflow, JWT 3 role Admin/Bác sĩ/Điều dưỡng) mà không hỏi lại — các quyết định này đã được thống nhất kỹ với người dùng qua nhiều vòng hỏi đáp.
- **Thiết kế đã có trước, code bám theo thiết kế** — nếu code cần lệch khỏi sơ đồ trong `docs/design/`, phải cập nhật lại tài liệu thiết kế tương ứng, không để lệch nhau.
- **Patient-level split theo `subject_id`**: 4 nhóm cố định train/validation/test/stream. Không bao giờ để cùng 1 bệnh nhân ở 2 nhóm; `test` chỉ dùng cho quality gate (xem `docs/design/02_9_thiet_ke_giai_thuat.md` mục 2.9.1c).
- **Không rò rỉ thông tin tương lai**: nhãn rủi ro là nhãn dự báo; mọi feature tại t chỉ dùng dữ liệu ≤ t; chỉ forward-fill, không nội suy.
- **Một nguồn code feature duy nhất**: mọi tính toán feature nằm trong `packages/common` (`rpm_common`), không copy sang `ml/` hay `services/streaming` (tránh lệch giữa lúc train và lúc chạy thật).
- **Champion–Challenger**: model mới chỉ nhận alias `champion` trên MLflow khi đạt quality gate. Gate gồm: ngưỡng tuyệt đối ở `02_10` mục 2.10.3, thắng baseline persistence, không kém champion trên cùng tập test. Không dùng stage `Production` (đã lỗi thời).
- **Cùng một phiên bản MLflow** (`3.11.1`) cho server (`infra/Dockerfile.mlflow`) và mọi client (`ml/`, `services/streaming`, Airflow).
- Style giao diện: nền dark-theme lấy cảm hứng từ `csgo-case-opening-design` skill, tùy biến thêm màu ngữ nghĩa lâm sàng (xanh/vàng/đỏ theo risk level) — xem `docs/design/02_8_thiet_ke_giao_dien.md`. Không tự ý đổi sang theme y tế "an toàn" thông thường trừ khi người dùng yêu cầu lại.

## Lệnh hay dùng

```bash
# Hạ tầng nền (Kafka từ host: localhost:29092; trong mạng docker: kafka:9092)
docker compose up -d postgres zookeeper kafka mlflow prometheus grafana
docker compose up -d airflow-webserver airflow-scheduler   # tự chạy airflow-init trước; image rpm-airflow (build lần đầu ~10 phút)
docker compose build airflow-scheduler                      # sau khi sửa ml/src hoặc packages/common (code ML nằm trong image)
docker compose --profile app up -d                          # backend :8000, frontend :3000, stream-consumer

# Môi trường Python (một lần, từ gốc repo); cài package nội bộ không cần mạng: thêm --no-build-isolation --no-deps
python -m venv .venv
.venv\Scripts\python -m pip install -e packages/common -e ml -e services/streaming -r ml/requirements.txt

# Test (từ gốc repo; backend cần postgres đang chạy, tự tạo DB rpm_test)
cd packages/common && ..\..\.venv\Scripts\python -m pytest -q && cd ..\..
cd ml && ..\.venv\Scripts\python -m pytest -q && cd ..
cd services/streaming && ..\..\.venv\Scripts\python -m pytest -q && cd ..\..
cd services/backend && ..\..\.venv\Scripts\python -m pytest -q && cd ..\..
cd services/frontend && npm run test && cd ..\..
# E2E trên hệ thống thật (~6 phút; XÓA dữ liệu phát lại trong rpm_db — xem tests/e2e/README.md)
cd tests/e2e && ..\..\.venv\Scripts\python -m pytest -q && cd ..\..
# Smoke test hạ tầng (chạy mỗi khi sửa docker-compose.yml hoặc Dockerfile trong infra/)
.venv\Scripts\python infra\smoke_test.py

# Dữ liệu và model — trên host cần MLFLOW_TRACKING_URI=http://localhost:5000
.venv\Scripts\python -m rpm_ml.data.preprocess            # → ml/data/processed/
.venv\Scripts\python -m rpm_ml.training.train_risk        # mô hình rủi ro
.venv\Scripts\python -m rpm_ml.training.train_anomaly     # LSTM-Autoencoder
.venv\Scripts\python -m rpm_ml.evaluation.report          # bảng/hình báo cáo → ml/reports/

# Schema DB và chạy backend/streaming trên host (POSTGRES_HOST=localhost KAFKA_BOOTSTRAP_SERVERS=localhost:29092)
cd services/backend && POSTGRES_HOST=localhost ../../.venv/Scripts/python -m alembic upgrade head && cd ../..
cd services/backend && ../../.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
KAFKA_BOOTSTRAP_SERVERS=localhost:29092 MLFLOW_TRACKING_URI=http://localhost:5000 POSTGRES_HOST=localhost .venv/Scripts/python -m rpm_streaming.consumer
KAFKA_BOOTSTRAP_SERVERS=localhost:29092 .venv/Scripts/python -m rpm_streaming.producer --seconds-per-hour 1
cd services/frontend && npm run dev
```
