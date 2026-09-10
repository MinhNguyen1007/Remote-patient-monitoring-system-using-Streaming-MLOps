# CLAUDE.md — ml/

Xem thiết kế giải thuật chi tiết ở `../docs/design/02_9_thiet_ke_giai_thuat.md` — mọi thay đổi kiến trúc model phải đối chiếu/cập nhật tài liệu đó. Mapping itemid, quy tắc làm sạch và đặc điểm dataset: `README.md` mục 4 và 6.

## Cấu trúc

```
src/
  preprocess.py     Load MIMIC-III Demo → làm sạch, gộp itemid, lưới 1 giờ, forward-fill có giới hạn,
                    tạo nhãn dự báo, chia 4 nhóm theo subject_id, xuất dữ liệu cho train và cho producer
  train.py          Baseline persistence + LogisticRegression + XGBoost/RandomForest (dự báo rủi ro) và LSTM-Autoencoder
  evaluate.py       Metric theo docs/design/02_10_thiet_ke_test.md mục 2.10.3, luôn kèm baseline persistence
  drift_detect.py   PSI/KS theo 02_9 mục 2.9.4
  retrain.py        Entry point cho Airflow DAG retrain_pipeline, Champion–Challenger theo 02_9 mục 2.9.5
splits/             File danh sách subject_id của 4 nhóm train/validation/test/stream (commit vào git)
notebooks/          EDA, thử nghiệm trước khi đưa vào src/ chính thức
```

Code tính đặc trưng (NEWS2, cửa sổ, baseline, mapping itemid) **không đặt trong `ml/src/`**. Nó nằm ở package dùng chung `../common/rpm_common`, được import bởi cả `ml/` và `streaming/`, để lúc train và lúc suy luận realtime tính giống hệt nhau.

## Quy ước bắt buộc

- **Chia dữ liệu theo `subject_id`** (không phải `icustay_id`/`hadm_id` — 19 bệnh nhân có nhiều đợt ICU). Có 4 nhóm cố định (50/15/15/20) lưu ở `splits/`.
  - Nhóm `test` chỉ dùng cho quality gate và báo cáo cuối.
  - Nhóm `stream` chỉ dùng để replay, không dùng cho huấn luyện ban đầu.
- **Nhãn rủi ro là nhãn dự báo**: `y_t` = mức NEWS2 rút gọn cao nhất trong `(t, t+h]`, mặc định h = 4. **Không bao giờ** lấy mức NEWS2 tại chính t làm nhãn, vì nhãn khi đó là hàm tất định của đặc trưng (rò rỉ nhãn).
  - NEWS2 dùng 5 thông số (0–15) kèm quy tắc "một thông số đạt 3 điểm → WARNING".
- **Mọi cửa sổ tính theo giờ dữ liệu**: rolling 6 giờ, LSTM 12 bước, baseline lũy tiến ≤ 24 giờ (≥ 6 giờ mới dùng được). Vitals trong MIMIC đo trung vị 60 phút/lần, nhiệt độ 240 phút/lần.
- **Chỉ forward-fill** (2 giờ với vitals, 6 giờ với nhiệt độ), **không nội suy** — nội suy dùng dữ liệu tương lai mà streaming không có.
- **Luôn báo baseline persistence** (dự báo = mức hiện tại) cạnh model; model phải thắng baseline. Tham chiếu trên toàn bộ dữ liệu, h = 4: Macro F1 0,566, Recall CRITICAL 31,1%.
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
# Chạy trên host: MLFLOW_TRACKING_URI=http://localhost:5000 (không phải http://mlflow:5000)
python src/preprocess.py
python src/train.py
python src/evaluate.py
python src/drift_detect.py
```
