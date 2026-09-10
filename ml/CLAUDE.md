# CLAUDE.md — ml/

Xem thiết kế giải thuật chi tiết ở `../docs/design/02_9_thiet_ke_giai_thuat.md` — mọi thay đổi kiến trúc model phải đối chiếu/cập nhật tài liệu đó. Mapping itemid, quy tắc làm sạch và đặc điểm dataset: `README.md` mục 4 và 6.

## Cấu trúc

```
src/
  preprocess.py     [đã có] Load MIMIC-III Demo → gọi rpm_common (làm sạch, lưới 1 giờ, NEWS2, feature, baseline),
                    tạo nhãn dự báo h=1/h=4, gắn nhóm chia dữ liệu, xuất dữ liệu cho train và cho producer
  split.py          [đã có] Chia 4 nhóm theo subject_id, phân tầng theo tử vong tại viện, đọc/ghi file cố định
  train.py          [đã có, phần rủi ro] CV chọn họ mô hình, chọn τ_critical, đánh giá test, gate, log/đăng ký MLflow
  risk_models.py    [đã có] Ứng viên LogisticRegression/RandomForest/XGBoost, trọng số lớp, GroupKFold
  metrics.py        [đã có] Metric phân loại + chọn τ_critical theo recall mục tiêu
  gate.py           [đã có] Quality gate cho mô hình rủi ro
  drift.py          [đã có] reference_stats (log kèm model), PSI, KS
  (chưa có)         LSTM-Autoencoder
  evaluate.py       Metric theo docs/design/02_10_thiet_ke_test.md mục 2.10.3, luôn kèm baseline persistence
  drift_detect.py   PSI/KS theo 02_9 mục 2.9.4
  retrain.py        Entry point cho Airflow DAG retrain_pipeline, Champion–Challenger theo 02_9 mục 2.9.5
splits/             File danh sách subject_id của 4 nhóm train/validation/test/stream (commit vào git)
notebooks/          EDA, thử nghiệm trước khi đưa vào src/ chính thức
```

Code tính đặc trưng (NEWS2, cửa sổ, baseline, mapping itemid) **không đặt trong `ml/src/`**. Nó nằm ở package dùng chung `../common/rpm_common`, được import bởi cả `ml/` và `streaming/`, để lúc train và lúc suy luận realtime tính giống hệt nhau.

## Quy ước bắt buộc

- **Chia dữ liệu theo `subject_id`** (không phải `icustay_id`/`hadm_id` — 19 bệnh nhân có nhiều đợt ICU). Có 4 nhóm cố định (48/15/15/20 trên 98 bệnh nhân có vitals) lưu ở `splits/subject_split.json` — không tạo lại file này.
  - Nhóm `test` chỉ dùng cho quality gate và báo cáo cuối.
  - Nhóm `stream` chỉ dùng để replay, không dùng cho huấn luyện ban đầu.
- **Nhãn rủi ro là nhãn dự báo**: `y_t` = mức NEWS2 rút gọn cao nhất trong `(t, t+h]`, mặc định h = 4. **Không bao giờ** lấy mức NEWS2 tại chính t làm nhãn, vì nhãn khi đó là hàm tất định của đặc trưng (rò rỉ nhãn).
  - NEWS2 dùng 5 thông số (0–15) kèm quy tắc "một thông số đạt 3 điểm → WARNING".
- **Mọi cửa sổ tính theo giờ dữ liệu**: rolling 6 giờ, LSTM 12 bước, baseline lũy tiến ≤ 24 giờ (≥ 6 giờ mới dùng được). Vitals trong MIMIC đo trung vị 60 phút/lần, nhiệt độ 240 phút/lần.
- **Chỉ forward-fill** (2 giờ với vitals, 6 giờ với nhiệt độ), **không nội suy** — nội suy dùng dữ liệu tương lai mà streaming không có.
- **Luôn báo baseline persistence** (dự báo = mức hiện tại) cạnh model; model phải thắng baseline. Tham chiếu h = 4 trên tập `test`: Macro F1 0,547, Recall CRITICAL 30,8%.
- Đối chiếu nhãn proxy với `hospital_expire_flag` (không dùng "chuyển ICU" — mọi dữ liệu đã là ICU). Ghi kết quả vào báo cáo 3.5, kèm thiên lệch chọn mẫu: cả 100 bệnh nhân Demo đều về sau đã tử vong.
- **LSTM-Autoencoder** chỉ train trên cửa sổ mà cả 12 giờ đều NORMAL, 6 kênh.
  - `anomaly_score` = hàm phân phối tích lũy thực nghiệm của MSE trên cửa sổ NORMAL tập validation, nằm trong [0, 1]. Hàm này được lưu kèm model.
- Đánh giá anomaly bằng synthetic injection: 10% cửa sổ, 3 loại spike / level shift / drift dần, seed cố định — xem 02_9 mục 2.9.3.
- Mọi lần train phải log vào MLflow (params, metrics, artifact, `reference_stats.json` cho drift) — không train "chui" ngoài tracking.
- **Promote bằng alias `champion`**, không dùng stage `Production` (đã lỗi thời từ MLflow 2.9). Mỗi challenger đều được đăng ký version; chỉ chuyển alias khi đạt quality gate:
  - ngưỡng tuyệt đối ở 02_10 mục 2.10.3;
  - thắng baseline persistence;
  - không kém champion khi **đánh giá lại cả hai trên cùng tập test cố định**.
  - Không đạt thì gắn tag `gate=rejected` kèm lý do.

## Lệnh

```bash
# Môi trường (từ gốc repo, một lần): venv + package dùng chung ở chế độ editable
python -m venv .venv
.venv\Scripts\python -m pip install -e common -r ml/requirements.txt

# Test (từ gốc repo)
cd common && ..\.venv\Scripts\python -m pytest -q && cd ..
cd ml && ..\.venv\Scripts\python -m pytest -q && cd ..

# Tiền xử lý → ml/data/processed/{hourly,stream_replay}.parquet + summary.json (không nằm trong git)
.venv\Scripts\python ml/src/preprocess.py

# Chạy trên host: MLFLOW_TRACKING_URI=http://localhost:5000 (không phải http://mlflow:5000)
.venv\Scripts\python ml/src/train.py
.venv\Scripts\python ml/src/evaluate.py
.venv\Scripts\python ml/src/drift_detect.py
```

Máy phát triển hiện tại tạo venv bằng `--system-site-packages` để dùng lại thư viện đã cài sẵn (mạng chậm); phiên bản trong `requirements.txt` là phiên bản đã kiểm chứng trên máy đó.
