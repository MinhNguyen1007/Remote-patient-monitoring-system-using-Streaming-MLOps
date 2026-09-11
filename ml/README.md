# Dataset: MIMIC-III Clinical Database Demo v1.4

Tài liệu này mô tả bộ dữ liệu dùng cho toàn bộ hệ thống (huấn luyện model ở Giai đoạn C, replay streaming ở Giai đoạn D) và lý do lựa chọn nó thay vì các nguồn khác. Nội dung này sẽ được rút gọn đưa vào báo cáo mục 3.2 (Dữ liệu).

## 1. Dataset là gì

**MIMIC-III Clinical Database Demo** là bản trích xuất công khai, thu nhỏ (100 bệnh nhân) từ bộ dữ liệu **MIMIC-III** (Medical Information Mart for Intensive Care III) — cơ sở dữ liệu lâm sàng thật, phi định danh (de-identified), thu thập từ bệnh nhân điều trị tại khoa Hồi sức tích cực (ICU) của Beth Israel Deaconess Medical Center (Boston, Mỹ) trong giai đoạn 2001-2012. Dataset do nhóm nghiên cứu MIT Laboratory for Computational Physiology công bố, lưu trữ trên **PhysioNet**.

- Nguồn: https://physionet.org/content/mimiciii-demo/1.4/
- Giấy phép: Open Data Commons Open Database License v1.0 (ODbL) — không cần CITI training/Data Use Agreement có kiểm duyệt như bản đầy đủ, chỉ cần tài khoản PhysioNet miễn phí và chấp nhận điều khoản sử dụng.
- Quy mô: 100 bệnh nhân, 129 lượt nhập viện, 136 đợt nằm ICU (77 đợt MetaVision, 59 đợt CareVue).
- **Cách chọn mẫu (quan trọng)**: PhysioNet chọn ngẫu nhiên 100 bệnh nhân từ nhóm bệnh nhân **về sau đã tử vong** — đã kiểm chứng: `PATIENTS.expire_flag = 1` và `dod` có giá trị ở cả 100/100 bệnh nhân. Không phải ai cũng tử vong ngay trong lượt nằm viện: 40/129 lượt nhập viện có `hospital_expire_flag = 1` (31%). Đây là thiên lệch chọn mẫu, phải nêu ở mục 3.5.
- Cấu trúc: 26 bảng CSV quan hệ với nhau qua `subject_id` (bệnh nhân), `hadm_id` (lượt nhập viện), `icustay_id` (đợt nằm ICU).

## 2. Trích dẫn bắt buộc khi sử dụng (đưa vào mục 5 - Tài liệu tham khảo)

PhysioNet yêu cầu trích dẫn đầy đủ khi công bố bất kỳ công trình nào dùng dữ liệu này:

> Johnson, A., Pollard, T., & Mark, R. (2016). MIMIC-III Clinical Database Demo (version 1.4). PhysioNet. https://doi.org/10.13026/C2HM2Q
>
> Johnson, A. E. W., Pollard, T. J., Shen, L., Lehman, L. H., Feng, M., Ghassemi, M., Moody, B., Szolovits, P., Celi, L. A., & Mark, R. G. (2016). MIMIC-III, a freely accessible critical care database. Scientific Data, 3, 160035.
>
> Goldberger, A., et al. (2000). PhysioBank, PhysioToolkit, and PhysioNet: Components of a new research resource for complex physiologic signals. Circulation, 101(23), e215–e220.

## 3. Các bảng dùng trong project

Dataset gồm 26 file CSV. Mô tả đầy đủ ý nghĩa từng file và từng cột: xem [`ml/data_dictionary.md`](data_dictionary.md). Tóm tắt 5 bảng dùng trực tiếp:

| Bảng | Dùng để làm gì |
|---|---|
| `PATIENTS.csv` | Thông tin nhân khẩu học (giới tính, ngày sinh) → tính tuổi, feature phụ |
| `ADMISSIONS.csv` | Thời điểm nhập/xuất viện, **kết quả tử vong tại viện** (`hospital_expire_flag`) → dùng đối chiếu chéo với nhãn proxy NEWS2 (xem `docs/design/02_9_thiet_ke_giai_thuat.md`) |
| `ICUSTAYS.csv` | Thời điểm vào/ra ICU, đơn vị điều trị → xác định giai đoạn để replay streaming theo đúng trình tự thời gian thật |
| `CHARTEVENTS.csv` | Bảng chính — toàn bộ vitals đo định kỳ theo `itemid` (77MB, **758.355 dòng**), là nguồn dữ liệu chính cho cả huấn luyện lẫn replay streaming |
| `D_ITEMS.csv` | Từ điển giải nghĩa `itemid` trong `CHARTEVENTS` (tên chỉ số, đơn vị, hệ ghi nhận CareVue/MetaVision) |

## 4. Mapping itemid → 5 loại vitals (6 giá trị số) cần dùng

MIMIC-III trải qua 2 hệ thống ghi hồ sơ điện tử khác nhau theo thời gian (**CareVue** cho bệnh nhân cũ, **MetaVision** cho bệnh nhân mới hơn) → cùng 1 loại vital có nhiều `itemid` khác nhau, phải gộp lại khi xử lý. Danh sách dưới đây bám theo các concept vitals chuẩn của cộng đồng (`vitals_first_day`, `pivoted_vital` trong repo `MIT-LCP/mimic-code`), số dòng/số đợt ICU lấy từ dữ liệu thật:

| Vital | itemid CareVue | itemid MetaVision | Đơn vị gốc | Khoảng hợp lệ giữ lại |
|---|---|---|---|---|
| Heart Rate (HR) | 211 (7.396 dòng) | 220045 (8.094) | bpm | 0 < x < 300 |
| SpO2 | 646 (7.262) | 220277 (8.053) | % | 0 < x ≤ 100 |
| Respiratory Rate (RR) | 618 (7.030), 615 (988) | 220210 (8.056), 224690 (518) | nhịp/phút | 0 < x < 70 |
| Huyết áp tâm thu (SBP) | 51 (4.519), 455 (3.214), 6701 (27), 442 (2) | 220179 (4.884), **220050 (3.018 — HA động mạch, 24 đợt ICU)** | mmHg | 0 < x < 400 |
| Huyết áp tâm trương (DBP) | 8368 (4.504), 8441 (3.205), 8555 (27), 8440 (1) | 220180 (4.879), **220051 (3.017)** | mmHg | 0 < x < 300 |
| Nhiệt độ | 678 °F (1.670), **676 °C (1.020, 14 đợt ICU)** | 223761 °F (1.976), 223762 °C (30) | quy đổi hết về °C: `(F − 32) / 1.8` | 70 < °F < 120; 10 < °C < 50 |

**Không dùng**:
- `677` (Temperature C calc) và `679` (Temperature F calc): giá trị tính lại từ 678/676, gộp vào sẽ bị trùng lặp.
- `224689` (RR spontaneous): tập con của nhịp thở tổng.
- Các mã đo tay trái/phải hiếm (`224167`, `227243`, `224643`, `227242`): tổng cộng 12 dòng, không có trong concept chuẩn.

**Quy tắc làm sạch bắt buộc trong `rpm_ml/data/preprocess.py`**:
- Bỏ các dòng sau:

  | Điều kiện | Số dòng | Ghi chú |
  |---|---|---|
  | `error = 1` | 36 | cờ lỗi của MetaVision |
  | `stopped = "D/C'd"` | 64 | cờ hủy của CareVue |
  | `valuenum` rỗng | 2.765 | |
  | `icustay_id` rỗng | 81 | |
- Bỏ giá trị ngoài khoảng hợp lệ ở bảng trên. Dữ liệu thật có HR = 0, SpO2 = 0, SBP = 11.647.

**Tần suất đo thực tế** (khoảng cách trung vị giữa 2 lần đo liên tiếp trong cùng đợt ICU):
- HR/SpO2/RR/HA: **60 phút**.
- Nhiệt độ: **240 phút**.

Hệ quả:
- Dữ liệu được đưa về lưới 1 giờ (trung vị trong giờ).
- Mọi cửa sổ thời gian trong thiết kế tính bằng giờ, không phải phút.
- Nhiệt độ chỉ có mặt ở ~32% số giờ trước khi điền giá trị.

Chi tiết tiền xử lý: `docs/design/02_9_thiet_ke_giai_thuat.md` mục 2.9.1.

Đã verify thực tế (2026-09-10):
- Checksum khớp `SHA256SUMS.txt`.
- Đủ 100 bệnh nhân.
- Số dòng từng itemid như bảng trên.
- 132/136 đợt ICU có dữ liệu vitals; 4 đợt còn lại không có.

## 5. Lý do chọn dataset này

| Tiêu chí | MIMIC-III Demo (đã chọn) | MIMIC-III/eICU đầy đủ | Tự mô phỏng (simulator) | Kaggle "Human Vital Signs" |
|---|---|---|---|---|
| Dữ liệu lâm sàng thật | ✅ Có | ✅ Có | ❌ Không | ❌ Phần lớn là tổng hợp |
| Cần xin quyền/CITI training | ❌ Không cần | ✅ Cần (mất vài ngày-tuần chờ duyệt) | ❌ Không cần | ❌ Không cần |
| Có chuỗi thời gian theo từng bệnh nhân | ✅ Có (phù hợp replay streaming + LSTM-Autoencoder) | ✅ Có | ✅ Có (nhưng do mình tạo, không phản ánh đúng biến động thật) | ❌ Thường là bảng tĩnh, không theo chuỗi thời gian |
| Có outcome thật để đối chiếu nhãn | ✅ Có (`hospital_expire_flag`) | ✅ Có | ❌ Không có | ❌ Không có |
| Quy mô đủ nhẹ để chạy nhanh trong đồ án | ✅ 100 bệnh nhân | ❌ Hàng chục nghìn bệnh nhân, nặng | ✅ Tùy chỉnh được | ✅ Nhẹ |

**Kết luận**: MIMIC-III Demo là điểm cân bằng tốt nhất giữa (a) tính xác thực lâm sàng — dữ liệu ICU thật, không phải số random hay công thức giả lập, (b) khả năng tiếp cận ngay không cần chờ duyệt hồ sơ như bản đầy đủ hay eICU, và (c) đủ nhỏ để xử lý/huấn luyện nhanh trong phạm vi đồ án môn học. MIMIC-III (bản đầy đủ) là một trong những bộ dữ liệu được dùng phổ biến nhất trong nghiên cứu về hệ thống cảnh báo sớm lâm sàng; bản Demo có cùng cấu trúc bảng nên toàn bộ pipeline có thể chạy lại trên bản đầy đủ khi có quyền truy cập (hướng phát triển, mục 4.2).

## 6. Hạn chế cần nêu rõ ở mục 3.5 (Đánh giá, thảo luận)

- **Chỉ 100 bệnh nhân**, 19 người có hơn 1 đợt ICU → chia dữ liệu phải theo `subject_id`; tập test sẽ nhỏ nên cần báo kết quả dạng mean ± std qua GroupKFold, diễn giải thận trọng, không suy rộng thành kết luận lâm sàng.
- **Thiên lệch chọn mẫu**: cả 100 bệnh nhân đều là người về sau đã tử vong, tỷ lệ tử vong tại viện 31%/lượt nhập viện → nhóm bệnh nhân nặng hơn quần thể ICU chung; mọi phép đối chiếu với `hospital_expire_flag` mang thiên lệch này.
- **Không có nhãn `risk_level` hay nhãn "bất thường" trực tiếp theo từng thời điểm** → nhãn rủi ro là proxy suy ra từ NEWS2 rút gọn ở **thời điểm tương lai** (bài toán dự báo, tránh rò rỉ nhãn), và anomaly detection được đánh giá bằng dữ liệu tiêm bất thường tổng hợp — xem `docs/design/02_9_thiet_ke_giai_thuat.md`.
- **NEWS2 chỉ tính được 5/7 thông số** (không dùng thở oxy bổ sung và mức ý thức) → thang điểm tối đa 15 thay vì 20.
- **Tần suất đo thưa và không đều** (trung vị 60 phút, nhiệt độ 240 phút) → chỉ điền giá trị theo chiều thời gian (forward-fill có giới hạn), **không nội suy** vì nội suy dùng giá trị tương lai mà luồng streaming không có.
- **Thời gian bị dịch chuyển để ẩn danh** (năm 2102–2202) → khi replay phải quy đổi về đồng hồ hệ thống, chỉ giữ khoảng cách tương đối giữa các lần đo.
- **Có giá trị lỗi/nhiễu** (HR = 0, SBP = 11.647, dòng bị đánh dấu lỗi) → bắt buộc làm sạch theo mục 4.
- **Dữ liệu từ 2001-2012, hệ thống CareVue/MetaVision của Mỹ** → có thể không phản ánh đúng đặc điểm dân số/thiết bị y tế tại Việt Nam; đây là giới hạn chấp nhận được trong phạm vi đồ án học thuật, không phải hệ thống triển khai thực tế.

## 7. Vị trí file trên máy

Dataset được tải về `ml/data/raw/mimic-iii-clinical-database-demo-1.4/` — **không nằm trong git** (xem `.gitignore`) do có giấy phép riêng và dung lượng lớn (~95MB). Muốn tải lại: đăng ký tài khoản miễn phí tại physionet.org → vào trang dataset ở mục 1 → chấp nhận điều khoản → tải toàn bộ về đúng đường dẫn trên.
