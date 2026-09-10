# CLAUDE.md — ml/

Xem thiết kế giải thuật chi tiết ở `../docs/design/02_9_thiet_ke_giai_thuat.md` — mọi thay đổi kiến trúc model phải đối chiếu/cập nhật tài liệu đó.

## Cấu trúc

```
src/
  preprocess.py     Tải & tiền xử lý MIMIC-III Demo, tính feature (NEWS2 components, rolling stats, baseline z-score)
  train.py          Train Risk Classification (baseline LogisticRegression + XGBoost/RandomForest) và LSTM-Autoencoder
  evaluate.py        Đánh giá theo đúng metric ở docs/design/02_10_thiet_ke_test.md (Macro F1, Recall CRITICAL, Precision/Recall anomaly)
  drift_detect.py    Tính PSI/KS-test theo công thức ở 02_9_thiet_ke_giai_thuat.md mục 2.9.4
  retrain.py         Entry point Airflow DAG gọi vào, áp dụng chiến lược Champion-Challenger (02_9 mục 2.9.5)
notebooks/           EDA, thử nghiệm trước khi đưa vào src/ chính thức
```

## Quy ước bắt buộc

- **Chia dữ liệu theo patient-level**, không theo record-level — vi phạm nguyên tắc này làm sai lệch toàn bộ kết quả đánh giá đã thiết kế.
- Nhãn `risk_level` là **proxy suy ra từ NEWS2-score** (không có sẵn trong MIMIC-III Demo) — khi huấn luyện phải đối chiếu chéo với outcome thật (tử vong/chuyển ICU) trên tập validation, ghi lại kết quả đối chiếu để đưa vào báo cáo mục 3.5.
- LSTM-Autoencoder chỉ train trên cửa sổ NORMAL, không train trên toàn bộ dữ liệu.
- Đánh giá anomaly detection dùng synthetic anomaly injection (spike/dropout/drift dần) vì dataset không có nhãn bất thường thật — xem 02_9 mục 2.9.3.
- Mọi lần train phải log vào MLflow (params, metrics, artifact) — không train "chui" ngoài tracking.
- Model mới chỉ promote lên `Production` khi đạt ngưỡng ở `docs/design/02_10_thiet_ke_test.md` (Macro F1 ≥ 0.75, Recall CRITICAL ≥ 0.85, anomaly Precision/Recall ≥ 0.7) **và** không kém hơn model Production hiện tại (Champion-Challenger).

## Lệnh

```bash
python src/preprocess.py
python src/train.py
python src/evaluate.py
python src/drift_detect.py
mlflow ui   # nếu muốn xem local, thường dùng service mlflow trong docker-compose
```
