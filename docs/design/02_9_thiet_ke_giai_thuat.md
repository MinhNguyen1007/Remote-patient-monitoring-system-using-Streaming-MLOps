# 2.9. Thiết kế giải thuật

Mọi con số về dữ liệu trong mục này được đo trực tiếp trên MIMIC-III Clinical Database Demo v1.4 (xem `ml/README.md`). Toàn bộ mã tiền xử lý và tính đặc trưng nằm trong **một package Python dùng chung** (`packages/common` (`rpm_common`)), được cả pipeline huấn luyện (`ml/`) và consumer streaming (`services/streaming`) import — đảm bảo lúc huấn luyện và lúc suy luận thời gian thực tính đặc trưng giống hệt nhau (tránh *training–serving skew*).

## 2.9.1. Tiền xử lý dữ liệu và Feature Engineering

### a) Làm sạch và gộp itemid

- Gộp các `itemid` CareVue + MetaVision về 6 giá trị chuẩn: `heart_rate`, `spo2`, `respiratory_rate`, `systolic_bp`, `diastolic_bp`, `temperature` (°C). Mapping đầy đủ, các mã bị loại và lý do: `ml/README.md` mục 4.
- Nhiệt độ °F đổi sang °C: `(F − 32) / 1.8`.
- Bỏ dòng có `error = 1` (MetaVision), `stopped = "D/C'd"` (CareVue), `valuenum` rỗng, `icustay_id` rỗng, và giá trị ngoài khoảng sinh lý hợp lệ.

### b) Đưa về lưới thời gian 1 giờ

Dữ liệu MIMIC là vitals do điều dưỡng ghi nhận, không phải tín hiệu monitor liên tục: khoảng cách trung vị giữa 2 lần đo là **60 phút** (HR, SpO2, RR, huyết áp) và **240 phút** (nhiệt độ). Vì vậy:

- Mỗi đợt ICU được đưa về lưới **1 giờ**; nhiều lần đo trong cùng 1 giờ lấy trung vị.
- Giá trị thiếu chỉ được điền **theo chiều thời gian** (forward-fill), tối đa 2 giờ với HR/SpO2/RR/huyết áp và 6 giờ với nhiệt độ. Sau khi điền, 92,9% số giờ có đủ 5 thông số dùng cho NEWS2.
- **Không nội suy** (interpolation), vì nội suy dùng giá trị ở tương lai mà luồng streaming không có — nếu dùng khi huấn luyện sẽ gây rò rỉ thông tin và lệch với lúc suy luận.
- Mỗi bản ghi của lưới là 1 message trên Kafka. Mọi cửa sổ thời gian dưới đây tính bằng **số bản ghi (= số giờ dữ liệu)**, nên không phụ thuộc tốc độ replay.

### c) Chia dữ liệu theo bệnh nhân (`subject_id`)

19 bệnh nhân có hơn 1 đợt ICU, nên đơn vị chia là `subject_id` (không phải `icustay_id`/`hadm_id`). 98 bệnh nhân có dữ liệu vitals (2/100 bệnh nhân của bản Demo không có) được chia ngẫu nhiên (seed 42, phân tầng theo việc có tử vong tại viện hay không) thành 4 nhóm cố định. Số liệu thực tế sau khi chia:

| Nhóm | Bệnh nhân | Đợt ICU | Giờ dữ liệu | Dùng để |
|---|---|---|---|---|
| `train` | 48 | 69 | 6.286 | Huấn luyện ban đầu |
| `validation` | 15 | 17 | 2.251 | Cùng `train` tạo tập phát triển cho GroupKFold (chọn họ mô hình, chọn `τ_critical`); early stopping và hiệu chỉnh `anomaly_score` của LSTM-Autoencoder |
| `test` | 15 | 21 | 3.476 | **Cố định tuyệt đối** — chỉ dùng cho quality gate và báo cáo kết quả cuối |
| `stream` | 20 | 25 | 2.125 | Được producer phát lại qua Kafka như bệnh nhân "đang nằm viện" (20 đợt, 1.834 giờ); dữ liệu tích lũy từ nhóm này là "dữ liệu mới" cho retrain |

- Danh sách `subject_id` của từng nhóm được lưu cố định trong `ml/splits/subject_split.json` (commit vào git), mọi lần train/retrain dùng chung.
- Chia theo bệnh nhân nên số giờ mỗi nhóm không tỷ lệ với số bệnh nhân (độ dài đợt ICU chênh lệch rất lớn, từ vài giờ tới hơn 300 giờ). Tập `train` chỉ chiếm ~44% số giờ — chấp nhận đổi lấy việc không rò rỉ bệnh nhân; không chọn lại seed để "đẹp" số liệu.
- Model không bao giờ thấy dữ liệu của nhóm `stream` trước khi nó được phát lại, và không bao giờ huấn luyện trên `test`.
- Do tập test nhỏ, kết quả chọn model được báo thêm dạng mean ± std qua **GroupKFold 5 fold** (nhóm theo `subject_id`) trên `train ∪ validation`.

### d) Điểm NEWS2 rút gọn (5 thông số)

NEWS2 gốc (Royal College of Physicians, 2017) có 7 thông số. Dự án dùng 5 thông số đo được liên tục; **không** có "thở oxy bổ sung" (+2) và "mức ý thức" (+3), nên tổng điểm nằm trong **0–15** (không phải 0–20). Huyết áp tâm trương không có điểm trong NEWS2 (chỉ dùng làm đặc trưng). SpO2 dùng Scale 1.

| Thông số | 3 | 2 | 1 | 0 | 1 | 2 | 3 |
|---|---|---|---|---|---|---|---|
| Nhịp thở (nhịp/phút) | ≤ 8 | | 9–11 | 12–20 | | 21–24 | ≥ 25 |
| SpO2 Scale 1 (%) | ≤ 91 | 92–93 | 94–95 | ≥ 96 | | | |
| Huyết áp tâm thu (mmHg) | ≤ 90 | 91–100 | 101–110 | 111–219 | | | ≥ 220 |
| Nhịp tim (bpm) | ≤ 40 | | 41–50 | 51–90 | 91–110 | 111–130 | ≥ 131 |
| Nhiệt độ (°C) | ≤ 35,0 | | 35,1–36,0 | 36,1–38,0 | 38,1–39,0 | ≥ 39,1 | |

- **Quy ước với giá trị thập phân** (dữ liệu thật có số lẻ): mỗi mức là một khoảng nửa mở `(cận dưới, cận trên]` theo cận trên của bảng. Ví dụ: HR 90,5 được tính là > 90, nên được 1 điểm.
- **Phân mức lâm sàng** (theo đúng hướng dẫn NEWS2, gồm cả quy tắc "một thông số đạt 3 điểm"):

| Mức | Điều kiện |
|---|---|
| `NORMAL` | Tổng 0–4 **và** không thông số nào đạt 3 điểm |
| `WARNING` | Tổng 5–6, **hoặc** có ít nhất 1 thông số đạt 3 điểm (mức "low-medium" của NEWS2) |
| `CRITICAL` | Tổng ≥ 7 |

Nếu bỏ quy tắc "một thông số 3 điểm", 13,9% số giờ dữ liệu sẽ bị gán NORMAL sai về mặt lâm sàng. Phân bố mức theo giờ trên dữ liệu thật: NORMAL 61,6%, WARNING 31,8%, CRITICAL 6,7%; tổng điểm cao nhất quan sát được là 13.

### e) Đặc trưng thống kê theo cửa sổ trượt

- Cửa sổ **6 giờ** gần nhất (cần tối thiểu 3 giá trị đo thật, nếu không thì để trống — XGBoost xử lý giá trị trống): trung bình, độ lệch chuẩn, độ dốc tuyến tính (đơn vị/giờ) của từng vital. Tính trên giá trị đo thật, không tính trên giá trị đã điền, để không làm phẳng giả tạo độ biến thiên.
- Chênh lệch so với giờ trước (`Δ1h`) của từng vital và của tổng NEWS2; NEWS2 cao nhất trong 6 giờ qua.
- Ngữ cảnh: tuổi (bệnh nhân > 89 tuổi bị MIMIC dịch ngày sinh, gán về 90), giới tính, số giờ kể từ khi vào ICU.

### f) Baseline cá nhân (cho mô hình phát hiện bất thường)

- Baseline của mỗi đợt ICU = trung bình và độ lệch chuẩn từng vital, tính **lũy tiến** trên tối đa 24 giờ đầu; bắt đầu dùng được khi đã có ≥ 6 giờ dữ liệu; sau 24 giờ thì cố định.
- Lý do: 22/136 đợt ICU ngắn hơn 24 giờ — nếu bắt buộc đủ 24 giờ, các đợt này không bao giờ được chấm điểm bất thường.
- Độ lệch chuẩn có **sàn tối thiểu** để tránh z-score bùng nổ: HR 5 bpm, SpO2 1%, RR 2 nhịp/phút, huyết áp 5 mmHg, nhiệt độ 0,2 °C (dữ liệu thật có 9/132 đợt ICU có std SpO2 trong 24 giờ đầu < 0,5).
- `z = (giá_trị − baseline_mean) / max(baseline_std, sàn)`.
- Hạn chế cần nêu ở 3.5: giai đoạn đầu nằm ICU thường là lúc bệnh nặng nhất, nên "baseline" có thể đã bất thường.

### g) Replay cho streaming

- Producer phát lại **1 đợt ICU cho mỗi bệnh nhân nhóm `stream`** (đợt dài nhất có dữ liệu vitals). Như vậy mỗi bệnh nhân trên dashboard ứng với đúng 1 đợt điều trị. 20 đợt được phát lại dài 12–365 giờ dữ liệu (trung vị 36,5 giờ); với tốc độ mặc định, đợt dài nhất phát trong khoảng 30 phút.
- Producer gửi **giá trị đo theo giờ chưa điền** (`<vital>_obs`, kể cả các giờ không đo) lấy từ `stream_replay.parquet`. Consumer tự forward-fill và tính đặc trưng bằng `rpm_common`, giống hệt lúc huấn luyện.
- Thời gian trong MIMIC đã bị dịch sang năm 2102–2202, nên producer bỏ mốc tuyệt đối và chỉ giữ thứ tự giờ.
- `recorded_at` = thời điểm phát theo đồng hồ hệ thống. 1 giờ dữ liệu được phát trong `REPLAY_SECONDS_PER_DATA_HOUR` giây (mặc định 5).
- Payload giữ thêm `hour_index` (giờ thứ mấy kể từ khi vào ICU) và `source_charttime` để truy vết.
- Message có key = mã bệnh nhân, để các bản ghi của cùng 1 bệnh nhân luôn vào cùng 1 partition và giữ đúng thứ tự.

## 2.9.2. Mô hình Dự báo rủi ro (Risk Forecasting)

- **Bài toán**: tại mỗi giờ t, dự báo mức rủi ro **cao nhất trong h giờ tới**: `y_t = max(risk_class(t+1), …, risk_class(t+h))`, với `risk_class` là mức NEWS2 ở mục 2.9.1(d). Mặc định **h = 4 giờ**; thực nghiệm ở mục 3.4 so sánh thêm h = 1.
- **Lý do chọn bài toán dự báo** (thay vì phân loại tức thời):
  - Nếu nhãn là mức NEWS2 **tại chính thời điểm t**, nhãn sẽ là một hàm tất định của đặc trưng đầu vào: mô hình đạt độ chính xác ~100% nhưng chỉ học lại bảng NEWS2 (rò rỉ nhãn).
  - Dự báo tương lai là bài toán có giá trị thật ("cảnh báo sớm"). Trên dữ liệu thật, 434/874 giờ CRITICAL là khởi phát mới (giờ trước chưa CRITICAL).
- **Nhãn chỉ dùng mẫu có đủ h giờ phía sau** trong cùng đợt ICU, và cả h giờ đó đều tính được mức NEWS2 (đủ 5 thông số sau khi điền). Với dữ liệu streaming, nhãn của giờ t "chín" sau h giờ — đây là nguồn nhãn cho retrain.
- **Đặc trưng đầu vào** (chỉ dùng dữ liệu ≤ t):
  - 6 vitals hiện tại.
  - Điểm thành phần và tổng NEWS2 hiện tại, cờ "có thông số 3 điểm".
  - Các đặc trưng cửa sổ 6 giờ và Δ1h.
  - Ngữ cảnh (mục 2.9.1e).
- **Mô hình**:
  - **Baseline persistence** (bắt buộc so sánh): dự báo = mức NEWS2 hiện tại. Mô hình học máy chỉ có ý nghĩa khi thắng baseline này. Kết quả đo trên dữ liệu thật (đầu ra của `rpm_ml.data.preprocess`):

    | Horizon | Tập | Accuracy | Macro F1 | Recall CRITICAL |
    |---|---|---|---|---|
    | h = 4 (mặc định) | toàn bộ | 62,1% | 0,567 | 31,3% |
    | h = 4 (mặc định) | `test` | 59,7% | 0,547 | 30,8% |
    | h = 1 | toàn bộ | 73,6% | 0,643 | 48,8% |
    | h = 1 | `test` | 71,5% | 0,621 | 48,6% |
  - Logistic Regression (multinomial, L2).
  - **XGBoost** multi-class (`objective=multi:softprob`), so sánh thêm Random Forest; chọn mô hình theo GroupKFold.
  - Mất cân bằng lớp xử lý bằng trọng số lớp (`sample_weight`), không sinh mẫu giả. CRITICAL chiếm 6,7% số giờ; với h = 4, nhãn CRITICAL chiếm 14,5%.
- **Đầu ra**: xác suất 3 lớp; `risk_score = P(CRITICAL)`; `risk_level` suy ra theo ngưỡng ở mục 2.9.6.
- **Đánh giá** (trên tập `test` cố định):
  - Accuracy, Macro F1, **Recall lớp CRITICAL** (ưu tiên lâm sàng: bỏ sót ca nguy kịch nghiêm trọng hơn báo động giả).
  - AUROC one-vs-rest, AUPRC lớp CRITICAL, ma trận nhầm lẫn.
  - Luôn kèm kết quả của baseline persistence trên cùng tập.
- **Đối chiếu nhãn proxy với outcome thật**: so sánh tỷ lệ giờ CRITICAL giữa các đợt ICU tử vong tại viện và sống sót (`hospital_expire_flag`). Đo sơ bộ: tỷ lệ giờ CRITICAL trung bình mỗi đợt ICU là 19,1% ở nhóm tử vong tại viện so với 3,6% ở nhóm sống sót, tức nhãn proxy có liên hệ với kết cục thật. Kết quả này mang thiên lệch chọn mẫu của bản Demo (cả 100 bệnh nhân về sau đều tử vong) — nêu ở 3.5.
- **Giải thích mô hình**: SHAP values — phục vụ thảo luận ở 3.4/3.5.

## 2.9.3. Mô hình Phát hiện bất thường (Anomaly Detection — Deep Learning)

- **Kiến trúc**: LSTM-Autoencoder.
  - Encoder: `LSTM(64, return_sequences=True) → LSTM(32, return_sequences=False)` → vector ẩn.
  - Decoder: `RepeatVector(L) → LSTM(32, return_sequences=True) → LSTM(64, return_sequences=True) → TimeDistributed(Dense(6))`.
  - Hàm mất mát: MSE giữa chuỗi vào và chuỗi tái tạo. Optimizer: Adam, early stopping theo tập validation.
- **Cửa sổ đầu vào**: **L = 12** bản ghi liên tiếp (12 giờ dữ liệu), **6 kênh** (HR, SpO2, RR, SBP, DBP, nhiệt độ), đã chuẩn hóa z-score theo baseline cá nhân (mục 2.9.1f).
  - Chỉ chấm điểm khi baseline đã dùng được và cửa sổ không còn giá trị trống sau khi điền.
  - Baseline dùng được từ `hour_index` 5 (đủ 6 giờ), cửa sổ cần 12 giờ z-score liên tiếp, nên mỗi bệnh nhân sớm nhất có `anomaly_score` ở `hour_index` **16** (giờ thứ 17); trước đó chỉ có dự báo rủi ro.
  - **Căn giữa cửa sổ**: trước khi đưa vào autoencoder, mỗi kênh được trừ đi trung bình của chính nó trong cửa sổ. Autoencoder học **hình dạng** diễn biến 12 giờ (dao động, bước nhảy, xu hướng); độ lớn biến thiên vẫn tính theo độ lệch chuẩn baseline cá nhân. Mức lệch tuyệt đối so với baseline không đưa vào, vì NEWS2 và mô hình dự báo rủi ro đã xử lý phần này.
  - Lý do (đo bằng GroupKFold 5 fold theo bệnh nhân trên `train ∪ validation`, 2026-09-11): không căn giữa thì MSE của cửa sổ bình thường có đuôi rất dày (p99 gấp 8 lần trung vị), do vài bệnh nhân lệch xa baseline dù NEWS2 vẫn NORMAL. Hệ quả là ngưỡng p99 không dùng lại được cho bệnh nhân mới: tỷ lệ gắn cờ nhầm dao động 0–24% giữa các fold. Căn giữa giảm con số này về 0–6% và nâng precision từ 0,19 lên 0,50 ở cùng ngưỡng.
  - Phép căn giữa nằm trong `rpm_common.anomaly.center_windows` và được thực hiện bên trong wrapper model, nên consumer vẫn truyền cửa sổ z-score gốc.
- **Huấn luyện**: chỉ dùng cửa sổ của nhóm `train` mà **cả 12 giờ đều ở mức NORMAL**, để mô hình học đúng "hình dạng bình thường" của tín hiệu.
- **Điểm bất thường** chuẩn hóa về [0, 1]: `anomaly_score = F(MSE)`.
  - `F` là hàm phân phối tích lũy thực nghiệm của MSE trên các cửa sổ NORMAL của tập `validation` (lưu kèm model thành artifact).
  - Nghĩa là: `anomaly_score = 0,99` ⇔ lỗi tái tạo lớn hơn 99% cửa sổ bình thường.
  - Ngưỡng gắn cờ ở mục 2.9.6.
- **Đánh giá** — do dataset không có nhãn "bất thường" thật, dùng **tiêm bất thường tổng hợp** vào cửa sổ NORMAL của tập `test`:
  - **σ** của mỗi kênh = độ lệch chuẩn z-score của kênh đó trên các cửa sổ NORMAL của nhóm `train` cố định (đo được 1,26–1,91, không phải 1). σ không đổi giữa các lần retrain, nên challenger và champion luôn được chấm trên cùng một tập tiêm.
  - Tỷ lệ tiêm: **10%** số cửa sổ, seed cố định, 3 loại chia đều:
    - (1) *spike*: 1–2 bước liên tiếp lệch ±4σ ở 1 kênh;
    - (2) *level shift*: từ giữa cửa sổ, 1 kênh dịch +3σ;
    - (3) *drift dần*: 1 kênh tăng tuyến tính tới +3σ ở cuối cửa sổ.
  - Không dùng kiểu "mất tín hiệu": giá trị thiếu đã được xử lý ở bước tiền xử lý (cửa sổ thiếu dữ liệu không được chấm).
  - Đo AUROC (tiêu chí gate, mục 2.10.3) và Precision/Recall/F1 tại ngưỡng mặc định, kèm recall theo từng loại bất thường — nêu rõ đây là đánh giá bán thực nghiệm ở mục 3.5.
  - Kết quả cần nêu ở 3.4/3.5: tại `τ_anomaly = 0,99`, mô hình gắn cờ ít nhưng khá chính xác (precision cao, recall thấp).
    - Bất thường tiêm ±3–4σ trên 1 kênh phần lớn nằm trong độ biến thiên tự nhiên của vitals theo giờ: trung vị |z| lớn nhất của một cửa sổ bình thường đã là 3,6.
    - Riêng loại *drift dần* gần như không phân biệt được với xu hướng bình thường.

## 2.9.4. Drift Detection

- **Đặc trưng theo dõi**: 6 vitals (giá trị sau forward-fill) và tổng NEWS2 (7 đặc trưng), dựng lại từ `vital_records` bằng `rpm_common` giống hệt lúc huấn luyện.
- **Phân phối tham chiếu**: phân phối trên tập huấn luyện của **`risk_classifier` champion hiện tại**, lưu thành artifact `reference_stats.json` (mốc chia bin + tỷ lệ mỗi bin + mẫu con cho KS) khi model được log. Lần đầu là nhóm `train`; sau retrain là `train` + dữ liệu stream đã dùng để huấn luyện.
- **Cửa sổ hiện tại**: 24 giờ dữ liệu streaming gần nhất của tất cả bệnh nhân đang được phát lại.
  - Producer gửi giờ thứ k của mọi bệnh nhân trong cùng một nhịp với cùng `recorded_at`, nên cửa sổ = các bản ghi có `recorded_at` thuộc **24 nhịp mới nhất**, không phụ thuộc tốc độ phát lại.
  - Bỏ qua lần kiểm tra (không ghi báo cáo) khi: chưa có champion; cửa sổ **chưa đủ 24 nhịp** (đầu lần phát lại — ngưỡng được hiệu chỉnh trên cửa sổ đủ 24 giờ nên cửa sổ ngắn hơn không so được); cửa sổ dưới **200 bản ghi**; hoặc không có dữ liệu mới kể từ lần kiểm tra trước (cùng `window_end`).
  - Điều kiện 24 nhịp được thêm sau lần chạy thật đầu tiên (2026-09-11): drift được kết luận ở nhịp 16, retrain chỉ có 316 giờ stream và 0 cửa sổ NORMAL mới cho LSTM-AE.
  - Đo trên dữ liệu thật: các đợt ICU nhóm `stream` dài 12–365 giờ, nên cửa sổ chỉ đủ ≥ 200 bản ghi ở nhịp 24–55 của lần phát lại (446 bản ghi ở nhịp 24, 244 ở nhịp 48, 193 ở nhịp 60).
- **PSI** cho từng đặc trưng:

  `PSI = Σ (actual_pct_i − expected_pct_i) × ln(actual_pct_i / expected_pct_i)`

  - 10 bin theo các mốc thập phân vị (decile) của phân phối tham chiếu; bin đầu/cuối mở rộng ra ±∞.
  - Bin có tỷ lệ bằng 0 được thay bằng ε = 1e-4 để tránh chia cho 0 hoặc `ln(0)`.
- **KS-test**: tính thống kê D hai mẫu để kiểm chứng chéo và hiển thị trong báo cáo drift. Không dùng p-value để ra quyết định, vì với số mẫu lớn, chênh lệch rất nhỏ cũng "có ý nghĩa thống kê".
- **Mức lệch để hiển thị** (thang PSI thông dụng): < 0,1 không đáng kể; 0,1 – < 0,25 trung bình; ≥ 0,25 đáng kể.
- **Ngưỡng quyết định drift — hiệu chỉnh theo từng đặc trưng** (hiệu chỉnh 2026-09-11, người dùng chọn):
  - **Vấn đề của ngưỡng chung 0,25**: ngưỡng 0,1/0,25 giả định mẫu lớn và độc lập. Một cửa sổ ở đây chỉ gồm ~20 bệnh nhân × 24 giờ, các giờ của cùng bệnh nhân tương quan mạnh, nên chỉ riêng khác biệt giữa các bệnh nhân đã đẩy PSI lên cao. Đo trên cửa sổ không có drift cùng hình dạng lần phát lại (lấy từ bệnh nhân không nằm trong tham chiếu, GroupKFold trên `train ∪ validation`), quy tắc "max PSI ≥ 0,25" gắn cờ **93%** số cửa sổ. Nếu giữ quy tắc này, hệ thống retrain liên tục dù không có drift.
  - **Cách hiệu chỉnh** (`rpm_ml/drift/stats.py`, `calibrate_thresholds`), chỉ dùng dữ liệu phát triển (nhóm huấn luyện ∪ `validation`, không bao giờ dùng `test`):
    1. GroupKFold 5 fold theo `subject_id`. Mỗi fold dựng tham chiếu từ 4 fold còn lại.
    2. Lấy ngẫu nhiên tối đa 20 đợt ICU (= số bệnh nhân nhóm `stream`) của fold bị giữ lại, 150 lần. Mọi đợt cùng bắt đầu ở giờ 0, cửa sổ 24 giờ kết thúc ở các nhịp 24, 28, … khi còn ≥ 200 bản ghi — đúng hình dạng cửa sổ lúc phát lại.
    3. Ngưỡng của mỗi đặc trưng = max(0,25; phân vị q của PSI không drift của đặc trưng đó). Cùng một q cho mọi đặc trưng, chọn bằng tìm nhị phân sao cho tỷ lệ cửa sổ không drift bị gắn cờ (bất kỳ đặc trưng nào) ≈ **5%**.
  - Ngưỡng được tính tự động mỗi lần train/retrain và log thành artifact `drift_thresholds.json` cạnh `reference_stats.json`. Champion train trước khi có bước này được bổ sung bằng `python -m rpm_ml.drift.detect backfill-thresholds` (chỉ thêm file vào run, model không đổi).
  - **Kết luận drift** (`drift_detected = true`) khi có ít nhất một đặc trưng có PSI ≥ ngưỡng của nó. Khi đó:
    - gửi thông báo cho Admin (email + tab Giám sát mô hình, xem 2.4.4);
    - **tự động kích hoạt retrain** (mục 2.9.5).
  - Kết quả đo thử (tham chiếu nhóm `train`, 2026-09-11): ngưỡng thu được từ 0,45 (DBP) tới 1,80 (HR), SpO2 0,745. Dữ liệu `stream` sạch không bị gắn cờ ở nhịp nào trong 24–52. Với `--drift` trên 50% bệnh nhân, lần kiểm tra nào cũng bị gắn cờ (SpO2 PSI 0,82–1,61).
- **Tần suất chạy**: Airflow DAG `drift_check` chạy **2 phút/lần** (biến `DRIFT_CHECK_INTERVAL_MINUTES`), có thể chạy thủ công.
  - Ở tốc độ phát lại mặc định (5 giây/giờ dữ liệu), 2 phút = đúng 24 giờ dữ liệu: các lần kiểm tra liên tiếp phủ các cửa sổ nối tiếp, không chồng lấp và không bỏ sót.
  - Lịch 10 phút ban đầu bị bỏ, vì vùng có ≥ 200 bản ghi (nhịp 24–55) chỉ kéo dài ~2,7 phút nên thường bị bỏ lỡ hoàn toàn.
- **Thông báo Admin**: DAG publish sự kiện `drift_report` lên Kafka topic `mlops-events`; backend đẩy WebSocket cho mọi Admin và gửi email khi `notify_admin = true`, tức khi **bắt đầu một đợt drift mới** (lần kiểm tra trước không có drift) hoặc **lần này đã kích hoạt retrain**. Drift kéo dài không gửi email lặp mỗi lần kiểm tra — cùng tinh thần chống bão cảnh báo ở 2.9.6.
- **Kịch bản drift cho demo/kiểm thử**: dữ liệu `stream` cùng phân phối với `train`, nên bình thường sẽ không có drift. Producer có chế độ `--drift` áp một độ lệch có kiểm soát lên một nhóm bệnh nhân được phát lại (HR +15 bpm, SpO2 −3%), mô phỏng thay đổi thiết bị đo hoặc quần thể bệnh nhân. Báo cáo ghi rõ đây là drift mô phỏng.
- **Hạn chế cần nêu ở 3.5**: ngưỡng được hiệu chỉnh cho đúng hình dạng cửa sổ của bản Demo (~20 bệnh nhân). Với số bệnh nhân lớn hơn, cửa sổ ổn định hơn và ngưỡng hiệu chỉnh sẽ tự giảm về gần 0,25. Tỷ lệ báo nhầm 5% là trên từng cửa sổ không drift của dữ liệu phát triển, chưa phải trên dữ liệu vận hành thật.

## 2.9.5. Chiến lược Retrain (Champion–Challenger)

**Kích hoạt**:
- **Tự động** khi `drift_check` kết luận drift (mục 2.9.4).
- **Thủ công** khi Admin bấm "Kích hoạt huấn luyện lại" (UC10).
- Chống vòng lặp: không kích hoạt tự động nếu đang có một lần retrain chạy (trạng thái `queued`/`running`), hoặc lần retrain gần nhất (kể cả lần thủ công hay thất bại) mới kết thúc trong vòng 1 giờ.
- Sau khi model rủi ro mới được promote, phân phối tham chiếu và ngưỡng drift đổi theo model mới.

**Dữ liệu retrain**: nhóm `train` cố định + dữ liệu đã tích lũy từ nhóm `stream`. Nhóm `validation` và `test` **không bao giờ đổi**.
- Dữ liệu stream được dựng lại từ `vital_records` (giá trị đo chưa điền) bằng đúng đường tính của lúc huấn luyện: lưới giờ → forward-fill → `build_hourly_features` → nhãn dự báo. Chỉ những giờ đã "chín" (đủ h giờ phía sau trong phần đã phát) mới có nhãn. Có test so khớp với `hourly.parquet`.
- Chỉ phần đã thực sự phát được dùng; phần chưa phát của đợt ICU nhóm `stream` (có sẵn trong `hourly.parquet`) không bao giờ vào huấn luyện.
- Mô hình rủi ro: dùng lại **nguyên quy trình huấn luyện ban đầu** (`train_risk_model`): chọn họ mô hình và `τ_critical` bằng GroupKFold trên (`train` + `stream`) ∪ `validation`, model cuối huấn luyện trên `train` + `stream`.
- Mô hình bất thường: huấn luyện trên cửa sổ NORMAL của `train` + `stream`; early stopping và ECDF vẫn trên `validation`. σ của phần tiêm bất thường **vẫn lấy từ nhóm `train` cố định**, nên tập test đã tiêm không đổi giữa các lần.

**Các bước của Airflow DAG `retrain_pipeline`** (`infra/airflow/dags/retrain_pipeline.py`, code ở `rpm_ml/pipelines/retrain.py`):
1. `build_dataset`: dựng tập dữ liệu.
2. `retrain_risk` và `retrain_anomaly` (chạy song song): huấn luyện challenger, log toàn bộ vào MLflow, đăng ký version mới (alias `challenger`).
3. Trong mỗi bước: đánh giá **cả challenger lẫn champion hiện tại trên cùng tập `test` cố định** (không so với metric đã log từ lần trước, vì có thể được đo trên dữ liệu khác), áp quality gate, promote hoặc từ chối.
4. Ghi kết quả vào bảng `model_versions`, kể cả version bị từ chối (`gate_reasons`, `trigger`, `drift_report_id`, `dag_run_id`, metric của challenger và champion).
5. `publish_result`: sự kiện `retrain_completed` cho giao diện Admin (chạy cả khi một mô hình lỗi). Task `all_models_trained` chỉ thành công khi cả 2 bước huấn luyện thành công, để trạng thái DAG phản ánh đúng lỗi.

**Quality gate** — mô hình dự báo rủi ro chỉ được promote khi đạt **đồng thời**:
1. Ngưỡng tuyệt đối ở `02_10_thiet_ke_test.md` mục 2.10.3 (Macro F1, Recall CRITICAL).
2. Macro F1 **cao hơn baseline persistence** trên cùng tập test.
3. Macro F1 ≥ champion **và** Recall CRITICAL ≥ champion (không được đánh đổi khả năng phát hiện ca nguy kịch lấy độ chính xác tổng thể). Lần huấn luyện đầu tiên chưa có champion thì bỏ qua điều kiện này.

Mô hình phát hiện bất thường được gate **độc lập**: AUROC trên tập test tiêm bất thường (seed cố định) đạt ngưỡng ở 2.10.3 **và** AUROC ≥ champion. Hai mô hình có thể được promote riêng rẽ.

**Promote/từ chối**:
- Dùng **alias** của MLflow Model Registry. Khái niệm "stage Production" đã bị MLflow đánh dấu lỗi thời từ bản 2.9.
- Promote: chuyển alias `champion` sang version mới. Model service trong consumer kiểm tra alias định kỳ và nạp lại.
- Từ chối: version được gắn tag `gate=rejected` kèm lý do; champion giữ nguyên — tránh tự động hạ cấp chất lượng hệ thống khi retrain trên dữ liệu nhiễu.
- Trong tài liệu, "model Production" = version đang giữ alias `champion`.

**Môi trường chạy**: image Airflow riêng (`infra/Dockerfile.airflow`, Airflow 2.9.3, Python 3.11). Code ML chạy trong venv `/opt/rpm-venv` với đúng phiên bản thư viện của `ml/requirements.txt` (MLflow 3.11.1), tách khỏi môi trường của Airflow để không xung đột phụ thuộc; DAG gọi code ML qua `BashOperator`.

## 2.9.6. Logic sinh cảnh báo

**Mức rủi ro hiển thị**:
- `risk_level = CRITICAL` nếu `risk_score = P(CRITICAL) ≥ τ_critical`.
- Ngược lại, lấy lớp có xác suất lớn hơn giữa NORMAL và WARNING.
- `τ_critical` mặc định là ngưỡng lớn nhất (lưới bước 0,01) mà Recall CRITICAL vẫn đạt **mục tiêu 0,80** (cao hơn ngưỡng gate 0,75 ở 2.10.3 để có biên cho nhiễu của tập test nhỏ), chọn trên **dự đoán out-of-fold** của GroupKFold 5 fold trên `train ∪ validation` (63 bệnh nhân). Model cuối vẫn chỉ huấn luyện trên `train`. Ngưỡng này lưu thành tag của model champion. Admin có thể ghi đè (UC08).
  - Lý do không chọn trên riêng `validation`: 15 bệnh nhân quá ít, ngưỡng dao động mạnh theo vài bệnh nhân. Lần chạy đầu chọn trên `validation` được τ = 0,25, nhưng Recall CRITICAL trên `test` chỉ đạt 0,730.
  - Dự đoán out-of-fold của mỗi bệnh nhân đến từ model không thấy bệnh nhân đó lúc huấn luyện, và mỗi model fold được huấn luyện trên số bệnh nhân tương đương model cuối (~50 so với 48), nên phân phối xác suất gần giống nhau.
- Nhờ vậy, badge đỏ trên dashboard trùng khớp với việc có cảnh báo.

**Bất thường**: `is_anomaly = anomaly_score ≥ τ_anomaly`, mặc định `τ_anomaly = 0,99` (khoảng 1% cửa sổ bình thường bị gắn cờ nhầm). Ngưỡng percentile 95 ban đầu bị bỏ vì theo định nghĩa sẽ gắn cờ nhầm 5% cửa sổ bình thường, quá nhiều cho cảnh báo.

**Loại cảnh báo**:

| Loại | Điều kiện |
|---|---|
| `RISK` | `risk_level = CRITICAL` |
| `ANOMALY` | `is_anomaly = true` |

Mức WARNING chỉ đổi màu badge, không tạo cảnh báo.

**Chống bão cảnh báo (alarm fatigue)** — với mỗi cặp (bệnh nhân, loại cảnh báo):
- Chỉ tạo cảnh báo mới khi **không còn cảnh báo cùng loại đang ở trạng thái OPEN**, **và** cảnh báo cùng loại gần nhất đã cách ít nhất `cooldown` giờ dữ liệu (mặc định 4).
- Trong lúc cảnh báo đang OPEN, prediction mới vẫn được lưu và đẩy lên dashboard, nhưng không sinh thêm cảnh báo hay email.
- Lý do: dữ liệu thật có 874 giờ CRITICAL. Nếu mỗi giờ sinh 1 cảnh báo, bác sĩ sẽ nhận hàng trăm email lặp lại cho cùng một đợt nguy kịch.

**Người nhận**: khi cảnh báo được tạo, email được gửi tới **mọi bác sĩ và điều dưỡng được phân công** cho bệnh nhân đó (bảng `patient_assignments`).

Các ngưỡng `τ_critical`, `τ_anomaly`, `cooldown` lưu trong bảng `alert_settings`; giá trị seed lần đầu lấy từ biến môi trường `DEFAULT_*` (`.env.example`).
