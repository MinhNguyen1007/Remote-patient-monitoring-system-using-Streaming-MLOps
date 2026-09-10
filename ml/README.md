# Dataset: MIMIC-III Clinical Database Demo v1.4

Tài liệu này mô tả bộ dữ liệu dùng cho toàn bộ hệ thống (huấn luyện model ở Giai đoạn C, replay streaming ở Giai đoạn D) và lý do lựa chọn nó thay vì các nguồn khác. Nội dung này sẽ được rút gọn đưa vào báo cáo mục 3.2 (Dữ liệu).

## 1. Dataset là gì

**MIMIC-III Clinical Database Demo** là bản trích xuất công khai, thu nhỏ (100 bệnh nhân) từ bộ dữ liệu **MIMIC-III** (Medical Information Mart for Intensive Care III) — cơ sở dữ liệu lâm sàng thật, phi định danh (de-identified), thu thập từ bệnh nhân điều trị tại khoa Hồi sức tích cực (ICU) của Beth Israel Deaconess Medical Center (Boston, Mỹ) trong giai đoạn 2001-2012. Dataset do nhóm nghiên cứu MIT Laboratory for Computational Physiology công bố, lưu trữ trên **PhysioNet**.

- Nguồn: https://physionet.org/content/mimiciii-demo/1.4/
- Giấy phép: Open Data Commons Open Database License v1.0 (ODbL) — không cần CITI training/Data Use Agreement có kiểm duyệt như bản đầy đủ, chỉ cần tài khoản PhysioNet miễn phí và chấp nhận điều khoản sử dụng.
- Quy mô: 100 bệnh nhân (trích ngẫu nhiên từ ~46.520 bệnh nhân của bản đầy đủ, trong đó có đủ các case còn sống và tử vong tại viện).
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

## 4. Mapping itemid → 5 vitals cần dùng

MIMIC-III trải qua 2 hệ thống ghi hồ sơ điện tử khác nhau theo thời gian (**CareVue** cho bệnh nhân cũ, **MetaVision** cho bệnh nhân mới hơn) → cùng 1 loại vital có 2 `itemid` khác nhau, phải gộp lại khi xử lý:

| Vital | itemid CareVue | itemid MetaVision | Đơn vị gốc |
|---|---|---|---|
| Heart Rate (HR) | 211 | 220045 | bpm |
| SpO2 | 646 | 220277 | % |
| Respiratory Rate (RR) | 618 | 220210 | insp/min |
| Huyết áp tâm thu (systolic BP) | 51, 455 | 220179 | mmHg |
| Huyết áp tâm trương (diastolic BP) | 8368, 8441 | 220180 | mmHg |
| Nhiệt độ | 678 (°F) | 223761 (°F) / 223762 (°C) | cần quy đổi hết về °C |

Đã verify thực tế (2026-09-10): checksum khớp `SHA256SUMS.txt`, đủ 100 bệnh nhân, tất cả itemid trên đều có dữ liệu thật (7.000-8.000 dòng/itemid với HR/SpO2/RR, 3.000-4.900 dòng/itemid với huyết áp, ít hơn với nhiệt độ do đo thưa hơn).

## 5. Lý do chọn dataset này

| Tiêu chí | MIMIC-III Demo (đã chọn) | MIMIC-III/eICU đầy đủ | Tự mô phỏng (simulator) | Kaggle "Human Vital Signs" |
|---|---|---|---|---|
| Dữ liệu lâm sàng thật | ✅ Có | ✅ Có | ❌ Không | ❌ Phần lớn là tổng hợp |
| Cần xin quyền/CITI training | ❌ Không cần | ✅ Cần (mất vài ngày-tuần chờ duyệt) | ❌ Không cần | ❌ Không cần |
| Có chuỗi thời gian theo từng bệnh nhân | ✅ Có (phù hợp replay streaming + LSTM-Autoencoder) | ✅ Có | ✅ Có (nhưng do mình tạo, không phản ánh đúng biến động thật) | ❌ Thường là bảng tĩnh, không theo chuỗi thời gian |
| Có outcome thật để đối chiếu nhãn | ✅ Có (`hospital_expire_flag`) | ✅ Có | ❌ Không có | ❌ Không có |
| Quy mô đủ nhẹ để chạy nhanh trong đồ án | ✅ 100 bệnh nhân | ❌ Hàng chục nghìn bệnh nhân, nặng | ✅ Tùy chỉnh được | ✅ Nhẹ |

**Kết luận**: MIMIC-III Demo là điểm cân bằng tốt nhất giữa (a) tính xác thực lâm sàng — dữ liệu ICU thật, không phải số random hay công thức giả lập, (b) khả năng tiếp cận ngay không cần chờ duyệt hồ sơ như bản đầy đủ hay eICU, và (c) đủ nhỏ để xử lý/huấn luyện nhanh trong phạm vi đồ án môn học. Đây cũng là bộ dữ liệu được dùng phổ biến nhất trong các nghiên cứu/đồ án học thuật về clinical early-warning system, giúp kết quả có cơ sở so sánh với tài liệu tham khảo.

## 6. Hạn chế cần nêu rõ ở mục 3.5 (Đánh giá, thảo luận)

- **Chỉ 100 bệnh nhân** → tập validation/test theo patient-level split sẽ khá nhỏ, cần diễn giải kết quả thận trọng, không suy rộng thành kết luận lâm sàng tổng quát.
- **Không có nhãn `risk_level` hay nhãn "bất thường" trực tiếp theo từng thời điểm** → phải suy ra bằng quy tắc NEWS2 (proxy label) và đánh giá anomaly detection bằng dữ liệu tiêm bất thường tổng hợp (synthetic injection) — đã nêu rõ trong `docs/design/02_9_thiet_ke_giai_thuat.md`.
- **Tần suất đo không đều** giữa các bệnh nhân/vitals (một số đo mỗi giờ, một số thưa hơn) → cửa sổ thời gian cho LSTM-Autoencoder cần resample/nội suy có kiểm soát.
- **Dữ liệu từ 2001-2012, hệ thống CareVue/MetaVision của Mỹ** → có thể không phản ánh đúng đặc điểm dân số/thiết bị y tế tại Việt Nam; đây là giới hạn chấp nhận được trong phạm vi đồ án học thuật, không phải hệ thống triển khai thực tế.

## 7. Vị trí file trên máy

Dataset được tải về `mimic-iii-clinical-database-demo-1.4_data/` ở thư mục gốc repo — **không nằm trong git** (xem `.gitignore`) do có giấy phép riêng và dung lượng lớn (~95MB). Muốn tải lại: đăng ký tài khoản miễn phí tại physionet.org → vào trang dataset ở mục 1 → chấp nhận điều khoản → tải toàn bộ về đúng đường dẫn trên.
