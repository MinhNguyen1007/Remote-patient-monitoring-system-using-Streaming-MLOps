# Data Dictionary — MIMIC-III Clinical Database Demo v1.4

Mô tả chi tiết toàn bộ 26 file CSV trong dataset: file dùng để làm gì, mỗi cột nghĩa là gì. Số liệu (số dòng) lấy thực tế từ file đã tải tại `mimic-iii-clinical-database-demo-1.4_data/` (đã trừ dòng header).

## Khóa liên kết dùng xuyên suốt các bảng

| Cột | Ý nghĩa |
|---|---|
| `row_id` | Số thứ tự dòng nội bộ của từng bảng, không mang ý nghĩa lâm sàng |
| `subject_id` | Mã định danh **bệnh nhân**, xuyên suốt mọi lượt nhập viện của người đó |
| `hadm_id` | Mã định danh **1 lượt nhập viện** (hospital admission) — 1 bệnh nhân có thể có nhiều `hadm_id` nếu nhập viện nhiều lần |
| `icustay_id` | Mã định danh **1 đợt nằm ICU** trong 1 lượt nhập viện — các lần chuyển giữa các ICU cách nhau dưới 24 giờ được gộp vào cùng 1 đợt; 1 `hadm_id` có nhiều `icustay_id` khi bệnh nhân rời ICU rồi quay lại sau hơn 24 giờ |
| `itemid` | Mã một loại chỉ số/xét nghiệm/thủ thuật cụ thể, tra nghĩa ở các bảng `D_*` tương ứng |
| `cgid` | Mã nhân viên y tế ghi nhận dữ liệu (Caregiver ID), tra ở `CAREGIVERS.csv` |

---

## Nhóm 1 — Bệnh nhân & lượt điều trị

### `PATIENTS.csv` (100 dòng) — ⭐ dùng trong project
Thông tin nhân khẩu học cố định, mỗi dòng 1 bệnh nhân.

| Cột | Ý nghĩa |
|---|---|
| `gender` | Giới tính (M/F) |
| `dob` | Ngày sinh — đã bị dịch chuyển ngẫu nhiên để ẩn danh (de-identify); riêng bệnh nhân >89 tuổi bị gán `dob` lùi về khoảng 300 năm theo quy định HIPAA, cần xử lý khi tính tuổi |
| `dod` | Ngày mất (tổng hợp từ nhiều nguồn), rỗng nếu còn sống tại thời điểm trích xuất dữ liệu |
| `dod_hosp` | Ngày mất ghi nhận tại bệnh viện |
| `dod_ssn` | Ngày mất theo dữ liệu an sinh xã hội (Social Security Death Index) |
| `expire_flag` | 1 = đã mất, 0 = còn sống (tại thời điểm dữ liệu được trích xuất, không phải tại thời điểm nằm viện). **Trong bản Demo cả 100/100 bệnh nhân đều = 1** vì PhysioNet chọn mẫu từ nhóm bệnh nhân về sau đã tử vong |

### `ADMISSIONS.csv` (129 dòng) — ⭐ dùng trong project
Mỗi dòng 1 lượt nhập viện.

| Cột | Ý nghĩa |
|---|---|
| `admittime` / `dischtime` | Thời điểm nhập viện / xuất viện |
| `deathtime` | Thời điểm tử vong nếu có (rỗng nếu không mất trong lượt này) |
| `admission_type` | Loại nhập viện: `EMERGENCY`, `ELECTIVE`, `URGENT`, `NEWBORN` |
| `admission_location` | Nơi chuyển đến từ đâu (vd `EMERGENCY ROOM ADMIT`, `TRANSFER FROM HOSP/EXTRAM`) |
| `discharge_location` | Nơi xuất viện đến (vd `HOME`, `SNF`, `DEAD/EXPIRED`) |
| `insurance`, `language`, `religion`, `marital_status`, `ethnicity` | Thông tin hành chính/nhân khẩu học bổ sung |
| `edregtime` / `edouttime` | Thời điểm vào/ra khoa Cấp cứu (Emergency Dept.) trước khi nhập viện chính thức |
| `diagnosis` | Chẩn đoán sơ bộ dạng văn bản tự do lúc nhập viện (không phải mã ICD chuẩn) |
| `hospital_expire_flag` | **1 nếu tử vong trong chính lượt nhập viện này, 0 nếu không** (bản Demo: 40/129 lượt = 1) — dùng đối chiếu chéo với nhãn `risk_level` suy ra từ NEWS2-score (xem `docs/design/02_9_thiet_ke_giai_thuat.md`) |
| `has_chartevents_data` | 1 nếu lượt nhập viện có dữ liệu vitals trong `CHARTEVENTS` |

### `ICUSTAYS.csv` (136 dòng) — ⭐ dùng trong project
Mỗi dòng 1 đợt nằm ICU (1 lượt nhập viện có nhiều đợt khi bệnh nhân quay lại ICU sau hơn 24 giờ). Trong bản Demo: 19 bệnh nhân có hơn 1 đợt ICU; thời gian nằm ICU trung vị 50,7 giờ, 22/136 đợt ngắn hơn 24 giờ.

| Cột | Ý nghĩa |
|---|---|
| `dbsource` | Hệ nguồn dữ liệu ghi nhận đợt ICU này: `carevue`, `metavision`, hoặc `both` (bản Demo chỉ có `metavision` 77 đợt, `carevue` 59 đợt) |
| `first_careunit` / `last_careunit` | Đơn vị điều trị đầu/cuối (vd `MICU`, `SICU`, `CCU`, `CSRU`) |
| `first_wardid` / `last_wardid` | Mã phòng/khu vật lý đầu/cuối |
| `intime` / `outtime` | Thời điểm vào/ra ICU — dùng để xác định khoảng thời gian replay streaming cho từng bệnh nhân |
| `los` | Length of stay — số ngày nằm ICU |

### `TRANSFERS.csv` (524 dòng) — tham khảo thêm
Lịch sử chuyển khoa/phòng/giường đầy đủ hơn ICUSTAYS (bao gồm cả di chuyển ngoài ICU).

| Cột | Ý nghĩa |
|---|---|
| `dbsource` | Hệ nguồn (carevue/metavision) |
| `eventtype` | Loại sự kiện: `admit`, `transfer`, `discharge` |
| `prev_careunit` / `curr_careunit` | Đơn vị điều trị trước/hiện tại |
| `prev_wardid` / `curr_wardid` | Phòng trước/hiện tại |
| `intime` / `outtime` | Thời điểm vào/ra vị trí đó |
| `los` | Thời gian lưu trú tại vị trí đó |

### `SERVICES.csv` (163 dòng) — không dùng trực tiếp
Lịch sử đổi chuyên khoa điều trị (không phải vị trí vật lý mà là "dịch vụ" phụ trách).

| Cột | Ý nghĩa |
|---|---|
| `transfertime` | Thời điểm đổi chuyên khoa |
| `prev_service` / `curr_service` | Chuyên khoa trước/hiện tại (vd `MED`, `SURG`, `CSURG`, `NB` = sơ sinh) |

### `CALLOUT.csv` (77 dòng) — không dùng
Theo dõi quy trình hành chính "callout" (đăng ký chuyển bệnh nhân ra khỏi ICU khi đủ điều kiện xuất viện/chuyển khoa thường).

| Cột | Ý nghĩa |
|---|---|
| `submit_wardid` / `submit_careunit` | Khoa gửi yêu cầu callout |
| `curr_wardid` / `curr_careunit` | Khoa hiện tại của bệnh nhân |
| `callout_wardid` / `callout_service` | Khoa/dịch vụ đích được đề nghị chuyển tới |
| `request_tele` / `request_resp` / `request_cdiff` / `request_mrsa` / `request_vre` | Cờ yêu cầu đặc biệt (theo dõi từ xa, hỗ trợ hô hấp, cách ly C.diff/MRSA/VRE) |
| `callout_status` / `callout_outcome` | Trạng thái và kết quả xử lý callout |
| `discharge_wardid` | Khoa xuất viện thực tế |
| `acknowledge_status` | Trạng thái xác nhận yêu cầu |
| `createtime`/`updatetime`/`acknowledgetime`/`outcometime`/`firstreservationtime`/`currentreservationtime` | Các mốc thời gian trong quy trình hành chính |

---

## Nhóm 2 — Từ điển tra cứu (Dictionary tables, tiền tố `D_`)

### `D_ITEMS.csv` (12.487 dòng) — ⭐ dùng trong project
Từ điển giải nghĩa `itemid` xuất hiện trong `CHARTEVENTS`, `DATETIMEEVENTS`, `INPUTEVENTS_*`, `OUTPUTEVENTS`, `PROCEDUREEVENTS_MV`.

| Cột | Ý nghĩa |
|---|---|
| `label` | Tên đầy đủ của chỉ số (vd `Heart Rate`, `SpO2`) |
| `abbreviation` | Tên viết tắt (chỉ có ở nguồn MetaVision, rỗng ở CareVue) |
| `dbsource` | Hệ nguồn: `carevue` hoặc `metavision` — **cùng 1 loại vital có itemid khác nhau giữa 2 hệ, phải tra và gộp thủ công** |
| `linksto` | Tên bảng chứa dữ liệu thực tế của itemid này (vd `chartevents`) |
| `category` | Nhóm chỉ số (vd `Routine Vital Signs`, `Labs`, `Alarms`, `Respiratory`) |
| `unitname` | Đơn vị đo mặc định |
| `param_type` | Kiểu dữ liệu: `Numeric`, `Text`, `Date` |
| `conceptid` | Mã khái niệm chuẩn hóa liên hệ thống — thường rỗng trong bản Demo |

### `D_LABITEMS.csv` (753 dòng) — dùng nếu mở rộng thêm xét nghiệm
Từ điển mã xét nghiệm dùng trong `LABEVENTS`.

| Cột | Ý nghĩa |
|---|---|
| `label` | Tên xét nghiệm |
| `fluid` | Loại bệnh phẩm (`Blood`, `Urine`...) |
| `category` | Nhóm xét nghiệm (`Hematology`, `Chemistry`...) |
| `loinc_code` | Mã chuẩn quốc tế LOINC |

### `D_ICD_DIAGNOSES.csv` (14.567 dòng) / `D_ICD_PROCEDURES.csv` (3.882 dòng) — tham khảo
Từ điển mã ICD-9 cho chẩn đoán / thủ thuật.

| Cột | Ý nghĩa |
|---|---|
| `icd9_code` | Mã ICD-9 |
| `short_title` / `long_title` | Tên ngắn/dài của chẩn đoán hoặc thủ thuật |

### `D_CPT.csv` (134 dòng) — không dùng
Từ điển mô tả nhóm mã CPT (Current Procedural Terminology, dùng thanh toán bảo hiểm Mỹ) theo section/subsection.

| Cột | Ý nghĩa |
|---|---|
| `category` | Nhóm CPT lớn |
| `sectionrange` / `sectionheader` | Khoảng mã / tên section |
| `subsectionrange` / `subsectionheader` | Khoảng mã / tên subsection |
| `codesuffix` | Hậu tố mã |
| `mincodeinsubsection` / `maxcodeinsubsection` | Mã nhỏ nhất/lớn nhất trong subsection |

### `CAREGIVERS.csv` (7.567 dòng) — tham khảo
Từ điển nhân viên y tế ghi nhận dữ liệu (đã ẩn danh).

| Cột | Ý nghĩa |
|---|---|
| `cgid` | Mã người ghi nhận |
| `label` | Chức danh (vd `RN` = điều dưỡng, `MD` = bác sĩ, `RRT` = kỹ thuật viên hô hấp) |
| `description` | Mô tả thêm |

---

## Nhóm 3 — Dữ liệu đo lường theo thời gian (Events tables)

### `CHARTEVENTS.csv` (758.355 dòng) — ⭐⭐ bảng quan trọng nhất, dùng trực tiếp
Mỗi dòng là **1 lần đo 1 chỉ số** (vitals, thang điểm ý thức, cài đặt máy thở...) tại 1 thời điểm cho 1 bệnh nhân. Đây là nguồn dữ liệu chính cho cả huấn luyện model lẫn replay streaming.

| Cột | Ý nghĩa |
|---|---|
| `icustay_id` | Đợt ICU đang diễn ra khi đo |
| `itemid` | Mã chỉ số được đo (tra `D_ITEMS`) |
| `charttime` | **Thời điểm đo thực tế** (thời gian lâm sàng) — dùng làm timestamp khi replay qua Kafka |
| `storetime` | Thời điểm dữ liệu được nhập vào hệ thống (có thể trễ hơn `charttime`) |
| `cgid` | Người ghi nhận |
| `value` | Giá trị dạng văn bản gốc |
| `valuenum` | Giá trị dạng số — **dùng để tính toán/feature engineering** |
| `valueuom` | Đơn vị đo của giá trị này |
| `warning` / `error` | **Chỉ có ở nguồn MetaVision** (CareVue để trống): cờ hệ thống cảnh báo giá trị bất thường / lỗi đo-nhập liệu — bỏ các dòng `error = 1` |
| `resultstatus` / `stopped` | **Chỉ có ở nguồn CareVue** (MetaVision để trống): kiểu kết quả / trạng thái dừng (`NotStopd`, `D/C'd`) — bỏ các dòng `stopped = "D/C'd"`. Kiểm chứng: itemid 211 (CareVue) có `stopped = NotStopd` ở 100% dòng, itemid 220045 (MetaVision) có `warning`/`error` và để trống `stopped` |
| `charttime` (lưu ý) | Mọi mốc thời gian trong MIMIC đã bị dịch sang khoảng năm 2100–2200 để ẩn danh — chỉ khoảng cách tương đối giữa các mốc là có ý nghĩa |

### `DATETIMEEVENTS.csv` (15.551 dòng) — không dùng trực tiếp
Giống cấu trúc `CHARTEVENTS` nhưng dành cho các chỉ số mà **giá trị đo được là một mốc thời gian** (vd giờ đặt ống thông tiểu, giờ thay băng) thay vì một con số — do đó không có cột `valuenum`.

| Cột | Ý nghĩa |
|---|---|
| (giống CHARTEVENTS, trừ) `value` | Ở đây giá trị là một timestamp, không phải số đo |

### `LABEVENTS.csv` (76.074 dòng) — tham khảo, có thể mở rộng feature sau này
Kết quả xét nghiệm cận lâm sàng (không đo tại giường như CHARTEVENTS mà gửi phòng lab).

| Cột | Ý nghĩa |
|---|---|
| `itemid` | Mã xét nghiệm (tra `D_LABITEMS`) |
| `charttime` | Thời điểm lấy mẫu/có kết quả |
| `value` / `valuenum` / `valueuom` | Giá trị kết quả (text/số/đơn vị) |
| `flag` | Cờ `abnormal` do hệ thống xét nghiệm tự gắn khi giá trị ngoài khoảng bình thường |

### `INPUTEVENTS_CV.csv` (34.799 dòng) — không dùng trong scope hiện tại
Ghi nhận dịch truyền/thuốc tiêm truyền vào cơ thể bệnh nhân, nguồn **CareVue**.

| Cột | Ý nghĩa |
|---|---|
| `charttime` | Thời điểm ghi nhận |
| `itemid` | Loại dịch/thuốc (tra `D_ITEMS`) |
| `amount` / `amountuom` | Lượng đã truyền và đơn vị |
| `rate` / `rateuom` | Tốc độ truyền và đơn vị |
| `orderid` / `linkorderid` | Mã y lệnh / liên kết y lệnh gốc |
| `stopped` | Trạng thái dừng truyền |
| `newbottle` | Cờ đổi sang chai/túi mới |
| `originalamount`, `originalamountuom`, `originalroute`, `originalrate`, `originalrateuom`, `originalsite` | Thông tin gốc trước hiệu chỉnh (route = đường truyền, site = vị trí truyền) |

### `INPUTEVENTS_MV.csv` (13.224 dòng) — không dùng trong scope hiện tại
Tương tự trên nhưng nguồn **MetaVision**, chi tiết y lệnh hơn.

| Cột | Ý nghĩa |
|---|---|
| `starttime` / `endtime` | Thời gian bắt đầu/kết thúc truyền (thay vì chỉ 1 `charttime` như CV) |
| `ordercategoryname`, `secondaryordercategoryname`, `ordercomponenttypedescription`, `ordercategorydescription` | Các tầng phân loại y lệnh |
| `patientweight` | Cân nặng bệnh nhân tại thời điểm ra y lệnh (dùng tính liều theo kg) |
| `totalamount` / `totalamountuom` | Tổng lượng cả túi/chai |
| `isopenbag` | Cờ túi dịch đang mở |
| `continueinnextdept` | Có tiếp tục truyền khi chuyển khoa không |
| `cancelreason` / `statusdescription` | Lý do hủy / trạng thái y lệnh |
| `comments_editedby`, `comments_canceledby`, `comments_date` | Thông tin chỉnh sửa/hủy y lệnh |
| `originalamount` / `originalrate` | Giá trị gốc trước hiệu chỉnh |

### `OUTPUTEVENTS.csv` (11.320 dòng) — không dùng trong scope hiện tại
Lượng dịch xuất ra khỏi cơ thể (nước tiểu, dẫn lưu...).

| Cột | Ý nghĩa |
|---|---|
| `itemid` | Loại output (tra `D_ITEMS`) |
| `value` / `valueuom` | Lượng và đơn vị |
| `stopped`, `newbottle`, `iserror` | Tương tự các cờ trạng thái ở INPUTEVENTS |

---

## Nhóm 4 — Chẩn đoán & thủ thuật

### `DIAGNOSES_ICD.csv` (1.761 dòng) — tham khảo cho phân tích mô tả (mục 3.4)
Danh sách chẩn đoán ICD-9 gán cho từng lượt nhập viện.

| Cột | Ý nghĩa |
|---|---|
| `seq_num` | Thứ tự ưu tiên chẩn đoán (1 = chẩn đoán chính) |
| `icd9_code` | Mã chẩn đoán (tra `D_ICD_DIAGNOSES`) |

### `PROCEDURES_ICD.csv` (506 dòng) — tham khảo
Danh sách thủ thuật ICD-9 thực hiện cho từng lượt nhập viện. Cấu trúc cột giống `DIAGNOSES_ICD`.

### `PROCEDUREEVENTS_MV.csv` (753 dòng) — không dùng trong scope hiện tại
Thủ thuật thực hiện trong ICU ghi nhận theo thời gian thực (đặt nội khí quản, thở máy...), chỉ có ở nguồn MetaVision.

| Cột | Ý nghĩa |
|---|---|
| `starttime` / `endtime` | Thời gian bắt đầu/kết thúc thủ thuật |
| `itemid` | Mã thủ thuật (tra `D_ITEMS`) |
| `value` / `valueuom` | Giá trị/đơn vị liên quan (vd thời lượng thực hiện) |
| `location` / `locationcategory` | Vị trí thực hiện thủ thuật trên cơ thể |
| Các cột `order*`, `comments_*`, `cancelreason`, `statusdescription`, `isopenbag`, `continueinnextdept` | Tương tự `INPUTEVENTS_MV` — chi tiết quản lý y lệnh |

### `CPTEVENTS.csv` (1.579 dòng) — không dùng
Mã thủ thuật/dịch vụ theo chuẩn CPT dùng cho thanh toán bảo hiểm.

| Cột | Ý nghĩa |
|---|---|
| `costcenter` | Trung tâm chi phí |
| `chartdate` | Ngày ghi nhận |
| `cpt_cd`, `cpt_number`, `cpt_suffix` | Mã CPT và các phần mở rộng |
| `ticket_id_seq` | Số thứ tự ticket dịch vụ |
| `sectionheader` / `subsectionheader` | Nhóm/phân nhóm dịch vụ |
| `description` | Mô tả dịch vụ |

### `DRGCODES.csv` (297 dòng) — tham khảo cho phân tích mô tả
Mã DRG (Diagnosis-Related Group) — hệ thống phân loại nhóm bệnh để thanh toán, `drg_severity`/`drg_mortality` có thể tham khảo như một proxy độ nặng bệnh độc lập.

| Cột | Ý nghĩa |
|---|---|
| `drg_type` | Hệ thống DRG áp dụng (`HCFA`, `APR`...) |
| `drg_code` | Mã DRG |
| `description` | Mô tả nhóm bệnh |
| `drg_severity` / `drg_mortality` | Mức độ nặng / nguy cơ tử vong theo thang DRG (chỉ có giá trị ở hệ APR-DRG) |

---

## Nhóm 5 — Khác

### `PRESCRIPTIONS.csv` (10.398 dòng) — không dùng trong scope hiện tại
Đơn thuốc kê cho bệnh nhân.

| Cột | Ý nghĩa |
|---|---|
| `startdate` / `enddate` | Ngày bắt đầu/kết thúc dùng thuốc |
| `drug_type` | Loại: `MAIN` (thuốc chính), `BASE` (dung môi), `ADDITIVE` (phụ gia) |
| `drug`, `drug_name_poe`, `drug_name_generic` | Tên thuốc (ghi tay / theo y lệnh điện tử / tên gốc quốc tế) |
| `formulary_drug_cd` | Mã danh mục thuốc nội bộ bệnh viện |
| `gsn` / `ndc` | Mã chuẩn thuốc quốc gia Mỹ (Generic Sequence Number / National Drug Code) |
| `prod_strength` | Hàm lượng sản phẩm |
| `dose_val_rx` / `dose_unit_rx` | Liều kê đơn và đơn vị |
| `form_val_disp` / `form_unit_disp` | Dạng bào chế phát thuốc và đơn vị |
| `route` | Đường dùng thuốc (`PO` = uống, `IV` = tiêm tĩnh mạch...) |

### `MICROBIOLOGYEVENTS.csv` (2.003 dòng) — không dùng
Kết quả xét nghiệm vi sinh (cấy khuẩn, kháng sinh đồ).

| Cột | Ý nghĩa |
|---|---|
| `spec_itemid` / `spec_type_desc` | Mã/loại bệnh phẩm (máu, đờm, nước tiểu...) |
| `org_itemid` / `org_name` | Mã/tên vi khuẩn phân lập được |
| `isolate_num` | Số thứ tự chủng phân lập trong cùng mẫu |
| `ab_itemid` / `ab_name` | Mã/tên kháng sinh được thử |
| `dilution_text`, `dilution_comparison`, `dilution_value` | Kết quả pha loãng trong kháng sinh đồ |
| `interpretation` | Kết luận: `S` (nhạy), `I` (trung gian), `R` (kháng) |

### `NOTEEVENTS.csv` (0 dòng dữ liệu — chỉ có header) — không dùng
Trong bản đầy đủ, bảng này chứa ghi chú lâm sàng dạng văn bản tự do (bệnh án, tóm tắt xuất viện...). **Trong bản Demo công khai, toàn bộ nội dung đã bị loại bỏ vì lý do bảo mật/riêng tư** (ghi chú tự do có nguy cơ chứa thông tin định danh cao hơn dữ liệu dạng số) — file chỉ còn header, không có dòng dữ liệu nào. Cấu trúc cột (`category`, `description`, `text`...) được giữ nguyên cho tương thích, nhưng không có gì để dùng.

---

## Tổng kết: bảng nào dùng ở đâu trong project

| Bảng | Dùng ở module | Mục đích |
|---|---|---|
| `PATIENTS`, `ADMISSIONS`, `ICUSTAYS` | `ml/src/preprocess.py` | Tuổi, giới tính, outcome tử vong thật (đối chiếu nhãn proxy), mốc thời gian ICU |
| `CHARTEVENTS` | `ml/src/preprocess.py` | Nguồn vitals chính — được làm sạch và đưa về lưới 1 giờ; dữ liệu đã xử lý dùng cho huấn luyện, còn phần thuộc nhóm bệnh nhân "stream" được `streaming/producer.py` phát lại (producer không đọc CHARTEVENTS thô, để luồng streaming và huấn luyện dùng cùng một cách tiền xử lý) |
| `D_ITEMS` | `ml/src/preprocess.py` | Tra cứu/gộp itemid CareVue+MetaVision về cùng tên feature |
| Các bảng còn lại | không dùng trong scope hiện tại | Có thể tham khảo mở rộng ở "Hướng phát triển" (mục 4.2), ví dụ: dùng thêm `LABEVENTS` làm feature bổ sung, `DRGCODES`/`DIAGNOSES_ICD` để phân tầng bệnh nhân theo nhóm bệnh khi đánh giá mô hình |
