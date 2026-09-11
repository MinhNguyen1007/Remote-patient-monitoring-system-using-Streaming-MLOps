# 2.9. Thiết kế giải thuật

Mọi con số về dữ liệu trong mục này được đo trực tiếp trên MIMIC-III Clinical Database Demo v1.4 (xem `ml/README.md`). Toàn bộ mã tiền xử lý và tính đặc trưng nằm trong **một package Python dùng chung** (`common/rpm_common`), được cả pipeline huấn luyện (`ml/`) và consumer streaming (`streaming/`) import — đảm bảo lúc huấn luyện và lúc suy luận thời gian thực tính đặc trưng giống hệt nhau (tránh *training–serving skew*).

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
  - **Baseline persistence** (bắt buộc so sánh): dự báo = mức NEWS2 hiện tại. Mô hình học máy chỉ có ý nghĩa khi thắng baseline này. Kết quả đo trên dữ liệu thật (đầu ra của `ml/src/preprocess.py`):

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
  - Vì vậy mỗi bệnh nhân bắt đầu có `anomaly_score` từ giờ thứ 12; trước đó chỉ có dự báo rủi ro.
- **Huấn luyện**: chỉ dùng cửa sổ của nhóm `train` mà **cả 12 giờ đều ở mức NORMAL**, để mô hình học đúng "hình dạng bình thường" của tín hiệu.
- **Điểm bất thường** chuẩn hóa về [0, 1]: `anomaly_score = F(MSE)`.
  - `F` là hàm phân phối tích lũy thực nghiệm của MSE trên các cửa sổ NORMAL của tập `validation` (lưu kèm model thành artifact).
  - Nghĩa là: `anomaly_score = 0,99` ⇔ lỗi tái tạo lớn hơn 99% cửa sổ bình thường.
  - Ngưỡng gắn cờ ở mục 2.9.6.
- **Đánh giá** — do dataset không có nhãn "bất thường" thật, dùng **tiêm bất thường tổng hợp** vào cửa sổ NORMAL của tập `test`:
  - Tỷ lệ tiêm: **10%** số cửa sổ, seed cố định, 3 loại chia đều:
    - (1) *spike*: 1–2 bước liên tiếp lệch ±4σ ở 1 kênh;
    - (2) *level shift*: từ giữa cửa sổ, 1 kênh dịch +3σ;
    - (3) *drift dần*: 1 kênh tăng tuyến tính tới +3σ ở cuối cửa sổ.
  - Không dùng kiểu "mất tín hiệu": giá trị thiếu đã được xử lý ở bước tiền xử lý (cửa sổ thiếu dữ liệu không được chấm).
  - Đo Precision/Recall/F1 tại ngưỡng mặc định và AUROC — nêu rõ đây là đánh giá bán thực nghiệm ở mục 3.5.

## 2.9.4. Drift Detection

- **Đặc trưng theo dõi**: 6 vitals và tổng NEWS2 (7 đặc trưng).
- **Phân phối tham chiếu**: phân phối trên tập huấn luyện của **model champion hiện tại**, lưu thành artifact `reference_stats.json` (mốc chia bin + tỷ lệ mỗi bin) khi model được đăng ký.
- **Cửa sổ hiện tại**: 24 giờ dữ liệu streaming gần nhất của tất cả bệnh nhân đang được phát lại. Cần tối thiểu 200 bản ghi, nếu không thì bỏ qua lần kiểm tra.
- **PSI** cho từng đặc trưng:

  `PSI = Σ (actual_pct_i − expected_pct_i) × ln(actual_pct_i / expected_pct_i)`

  - 10 bin theo các mốc thập phân vị (decile) của phân phối tham chiếu; bin đầu/cuối mở rộng ra ±∞.
  - Bin có tỷ lệ bằng 0 được thay bằng ε = 1e-4 để tránh chia cho 0 hoặc `ln(0)`.
- **KS-test**: tính thống kê D hai mẫu cho biến liên tục để kiểm chứng chéo và hiển thị trong báo cáo drift. Không dùng p-value để ra quyết định, vì với số mẫu lớn, chênh lệch rất nhỏ cũng "có ý nghĩa thống kê".
- **Ngưỡng quyết định** (theo max PSI giữa các đặc trưng):

  | PSI | Kết luận | Hành động |
  |---|---|---|
  | < 0,1 | Không đáng kể | — |
  | 0,1 – < 0,25 | Lệch trung bình | Ghi vào `drift_reports`, không hành động |
  | ≥ 0,25 | Lệch đáng kể | `drift_detected = true` → gửi thông báo cho Admin (email + tab Giám sát mô hình) và **tự động kích hoạt retrain** (mục 2.9.5) |
- **Tần suất chạy**: Airflow DAG `drift_check` chạy theo lịch (mặc định 10 phút/lần khi demo, vì 1 giờ dữ liệu chỉ được phát trong vài giây), có thể chạy thủ công.
- **Kịch bản drift cho demo/kiểm thử**: dữ liệu `stream` cùng phân phối với `train`, nên bình thường sẽ không có drift. Producer có chế độ `--drift` áp một độ lệch có kiểm soát lên một nhóm bệnh nhân được phát lại (ví dụ HR +15 bpm, SpO2 −3%), mô phỏng thay đổi thiết bị đo hoặc quần thể bệnh nhân. Báo cáo ghi rõ đây là drift mô phỏng.

## 2.9.5. Chiến lược Retrain (Champion–Challenger)

**Kích hoạt**:
- **Tự động** khi `drift_check` phát hiện drift (PSI ≥ 0,25).
- **Thủ công** khi Admin bấm "Kích hoạt huấn luyện lại" (UC10).
- Chống vòng lặp: không kích hoạt tự động nếu đang có một lần retrain chạy, hoặc lần retrain gần nhất mới kết thúc trong vòng 1 giờ.
- Sau khi model mới được promote, phân phối tham chiếu đổi theo model mới nên PSI giảm lại.

**Dữ liệu retrain**: nhóm `train` cố định + dữ liệu đã tích lũy từ nhóm `stream` có nhãn đã "chín" (đủ h giờ phía sau). Nhóm `validation` và `test` **không bao giờ đổi**.

**Các bước của Airflow DAG `retrain_pipeline`**:
1. Dựng tập dữ liệu.
2. Huấn luyện challenger cho cả 2 mô hình và log toàn bộ vào MLflow.
3. Đăng ký mỗi challenger thành một model version mới (alias `challenger`).
4. Đánh giá **cả challenger lẫn champion hiện tại trên cùng tập `test` cố định**. Không so sánh với metric đã log từ lần trước, vì có thể được đo trên dữ liệu khác.
5. Áp dụng quality gate.
6. Promote hoặc từ chối.
7. Ghi kết quả vào bảng `model_versions`.

**Quality gate** — mô hình dự báo rủi ro chỉ được promote khi đạt **đồng thời**:
1. Ngưỡng tuyệt đối ở `02_10_thiet_ke_test.md` mục 2.10.3 (Macro F1, Recall CRITICAL).
2. Macro F1 **cao hơn baseline persistence** trên cùng tập test.
3. Macro F1 ≥ champion **và** Recall CRITICAL ≥ champion (không được đánh đổi khả năng phát hiện ca nguy kịch lấy độ chính xác tổng thể). Lần huấn luyện đầu tiên chưa có champion thì bỏ qua điều kiện này.

Mô hình phát hiện bất thường được gate **độc lập**: đạt ngưỡng Precision/Recall ở 2.10.3 trên tập tiêm bất thường (seed cố định) và F1 ≥ champion. Hai mô hình có thể được promote riêng rẽ.

**Promote/từ chối**:
- Dùng **alias** của MLflow Model Registry. Khái niệm "stage Production" đã bị MLflow đánh dấu lỗi thời từ bản 2.9.
- Promote: chuyển alias `champion` sang version mới. Model service trong consumer kiểm tra alias định kỳ và nạp lại.
- Từ chối: version được gắn tag `gate=rejected` kèm lý do; champion giữ nguyên — tránh tự động hạ cấp chất lượng hệ thống khi retrain trên dữ liệu nhiễu.
- Trong tài liệu, "model Production" = version đang giữ alias `champion`.

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
