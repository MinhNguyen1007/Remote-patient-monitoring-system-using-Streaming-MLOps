# 2.8. Thiết kế giao diện

Mục này trình bày thiết kế giao diện người dùng của hệ thống: định hướng thẩm mỹ, hệ thống thiết kế (design system), kiến trúc điều hướng theo vai trò và thiết kế chi tiết từng màn hình kèm mockup. Mọi màn hình ánh xạ trực tiếp tới use case ở mục 2.2 và API backend (`backend/CLAUDE.md`).

Mockup độ trung thực cao được dựng bằng Claude Design canvas: https://claude.ai/code/artifact/06619c98-443f-4157-be37-cef16741dc5d. Mã nguồn artboard nằm ở `docs/design/mockups/`, ảnh dùng trong tài liệu ở `docs/design/mockups/png/`. Số liệu trên mockup là **số liệu mẫu**, cùng định dạng với response của API.

> **Cập nhật 2026-09-30 — đổi giao diện sang theme "CS:GO classic" của bộ `truanayangi-ui`** (người dùng yêu cầu nâng cấp giao diện). Bố cục màn hình, luồng nghiệp vụ và màu lâm sàng giữ nguyên; thay đổi nằm ở màu nền, chữ, header thay sidebar, và thêm overlay/âm báo cảnh báo mới. Các mục 2.8.1–2.8.4 dưới đây đã viết lại theo giao diện mới; mockup và ảnh `mockups/png/` là của giao diện trước đó (bố cục vẫn đúng, màu và chữ đã khác).

## 2.8.1. Định hướng thiết kế

**Người dùng và bối cảnh sử dụng.** Bác sĩ và điều dưỡng theo dõi đồng thời nhiều bệnh nhân ICU trên màn hình máy tính, thường trong ca trực kéo dài và ở phòng có ánh sáng thấp. Giao diện cần:

1. Cho biết **ai cần chú ý trước** chỉ trong một lần nhìn.
2. Tách rõ **dự báo của mô hình** với **điểm lâm sàng hiện tại**.
3. Cho phép xem diễn biến vitals trước khi xác nhận cảnh báo.
4. Không gây mỏi mắt hoặc "bão cảnh báo" bằng hiệu ứng nhấp nháy.

**Phong cách.** Giao diện dùng theme **"CS:GO classic"** của bộ giao diện `truanayangi-ui` (tái hiện giao diện kho đồ CS:GO): nền xám xanh với lớp gradient, panel trong mờ viền mảnh, góc vuông, chữ Arial nét thường, nút chính xanh lá gradient, số liệu nhấn màu vàng. Đây là lựa chọn thẩm mỹ có chủ đích để dashboard có bản sắc riêng. Bên trên theme đó, hệ thống bổ sung một lớp màu ngữ nghĩa lâm sàng.

Các tùy biến so với design system gốc:

| Thành phần của design system gốc | Tùy biến trong RPM | Lý do |
|---|---|---|
| Cơ chế "mở hòm", vòng quay ngẫu nhiên | Bỏ hoàn toàn | Không có khoảnh khắc ngẫu nhiên trong nghiệp vụ y tế |
| Thang "rarity" (độ hiếm) trên thẻ | Thay bằng 3 mức rủi ro lâm sàng + màu bất thường; giữ cách thể hiện (ánh màu dâng lên từ thanh đáy thẻ) | Giữ cơ chế gán màu qua biến `--tn-rarity`, đổi ý nghĩa |
| Màn "NEW ITEM" toàn màn hình sau khi quay | Dùng cho **cảnh báo rủi ro nguy kịch mới**; nội dung là đúng dữ liệu của cảnh báo | Khoảnh khắc cần chú ý thật trong nghiệp vụ; không có yếu tố ngẫu nhiên |
| Âm thanh mở hòm theo độ hiếm | Âm báo tổng hợp (Web Audio) khi có cảnh báo mới; nguy kịch/bất thường/drift kêu khác nhau; tắt được, nhớ lựa chọn | Không dùng tệp âm thanh có bản quyền |
| Bo góc hộp thoại/nút phụ của theme | **Góc vuông tuyệt đối** `--radius: 0` | Theo yêu cầu của người dùng (2026-09-11) |
| Ảnh nền nhà kho | Chỉ dùng gradient dự phòng của theme | Ảnh gốc không được phép dùng trong repo công khai |
| Motion | Chỉ cho thay đổi có ý nghĩa thật: cảnh báo mới, badge đổi mức, trạng thái cảnh báo đổi | Tránh chuyển động trang trí trong môi trường lâm sàng |

## 2.8.2. Hệ thống thiết kế (Design System)

![Bảng thành phần giao diện](mockups/png/Components.png)

*Hình 2.8.1 — Bảng thành phần dùng chung: badge rủi ro, NEWS2, điểm bất thường, trạng thái cảnh báo, nút, trạng thái kết nối (mockup của giao diện trước; cấu tạo thành phần giữ nguyên).*

### a) Màu sắc

Toàn bộ màu khai báo thành biến CSS; component chỉ tham chiếu biến, không dùng mã màu trực tiếp.

| Nhóm | Token | Giá trị | Dùng cho |
|---|---|---|---|
| Nền | `--background` + gradient | `#27323b`, `linear-gradient(#18242edf, #25323dd9)` | Nền trang xám xanh của theme CS:GO |
| | panel | `#17232c88`, viền `#ffffff32` | Panel, bảng, thẻ thông tin (trong mờ) |
| | header | `#101a23`, viền dưới `#ffffff20` | Thanh điều hướng trên cùng |
| Chữ | chữ chính / tiêu đề | `#f3f3ef` / `#e4e8eb` | |
| | nhãn / chữ phụ | `#c2c8cd` / `#abb8c2` | Nhãn dữ liệu, mô tả |
| Nhấn | nút chính | `linear-gradient(#739b4d, #5b8139)`, hover `#83a65f` | **Chỉ** hành động chính |
| | vàng | `#dec989` | Con số đếm, tab/lựa chọn đang bật (gạch chân 2px), trạng thái cảnh báo "Mở" |
| | focus | `#e4b85c` | Viền focus bàn phím |
| Rủi ro | `--risk-normal` | `#0ca30c` | Bình thường |
| | `--risk-warning` | `#fab219` | Cảnh báo — cần theo dõi sát |
| | `--risk-critical` | `#d03b3b` | Nguy kịch |
| Bất thường | `--anomaly-flag` | `#9085e9` (tím) | Điểm/cờ bất thường của LSTM-Autoencoder; tách khỏi 3 màu rủi ro |
| Biểu đồ | series | `#3987e5` / `#199e70` | Đường vitals / huyết áp tâm trương (nét đứt + nhãn trực tiếp). Kiểm tra bằng `validate_palette.js` trên nền `#1b2731`: đạt cả 5 tiêu chí cùng màu bất thường |

Quy tắc dùng màu:

- **Không truyền đạt thông tin chỉ bằng màu.** Mọi mức rủi ro luôn gồm icon riêng và nhãn chữ (`Bình thường` / `Cảnh báo` / `Nguy kịch`): vòng tròn dấu tích, tam giác, bát giác. Nhờ vậy người mù màu đỏ–xanh vẫn phân biệt được.
- Badge dùng nền màu trạng thái ở độ phủ 14% và viền 45%. Chữ giữ màu `--foreground` để đạt tương phản đọc. Màu trạng thái chỉ nằm ở icon và nền.
- Màu rủi ro lấy từ bảng màu trạng thái của hướng dẫn trực quan hóa dữ liệu (`dataviz`). Nút chính xanh lá của theme là dạng gradient và luôn có chữ, nên không bị nhầm với trạng thái "Bình thường" của bệnh nhân.

### b) Typography

| Vai trò | Font | Cỡ / độ đậm | Ghi chú |
|---|---|---|---|
| Tiêu đề trang | Arial | 32px / 400, căn giữa (27px, căn trái trên điện thoại) | Theo theme CS:GO; dưới tiêu đề là dòng đếm 12px, số màu vàng |
| Tiêu đề khối | Arial | 17px / 400 | |
| Nội dung | Arial | 14px / 400 | Có sẵn trên mọi máy, đủ dấu tiếng Việt; không tải web font |
| Nhãn dữ liệu, số liệu | Arial | nhãn 12px `#c2c8cd`; số 22px / 400, số tabular | Mọi con số (vitals, xác suất, thời gian) dùng số tabular để thẳng cột |

Số thập phân dùng dấu phẩy theo chuẩn tiếng Việt (`0,72`). Cách này nhất quán với báo cáo.

### c) Hình khối, khoảng cách, icon

- **Góc vuông** cho mọi thẻ, nút, ô nhập, badge, tooltip và ô biểu đồ. Ngoại lệ duy nhất là nút radio giữ hình tròn, vì hình tròn là quy ước nhận biết lựa chọn đơn, phân biệt với checkbox.
- Panel có viền mảnh 1px. Thẻ bệnh nhân dùng đúng thẻ CS:GO của theme: **thanh đáy 5px theo màu rủi ro, ánh màu dâng lên từ đáy thẻ**, di chuột thì sáng lên.
- Khoảng cách theo bội số 4px. Thẻ cách nhau 16px; nội dung rộng tối đa 1320px, lề 40px (16px trên điện thoại).
- Icon vẽ bằng SVG nét 1,8px trên lưới 24px, cùng một phong cách. Không dùng emoji.

### d) Chuyển động và khả năng tiếp cận

- Cảnh báo mới (bác sĩ, điều dưỡng — chỉ bệnh nhân được phân công):
  - **Rủi ro nguy kịch** → overlay toàn màn hình kiểu "NEW ITEM" của theme: tên bệnh nhân, xác suất nguy kịch cỡ lớn trên vầng sáng đỏ, giờ dữ liệu, NEWS2; nút **Xem bệnh nhân**, **Xác nhận** (chỉ Bác sĩ), **Để sau**. Nhiều cảnh báo đến cùng lúc thì xếp hàng ("còn n cảnh báo chờ", **Bỏ qua tất cả**). Esc đóng overlay.
  - **Bất thường** → toast góc dưới phải (viền đáy tím), tự ẩn sau 20 giây, không che màn hình.
  - Admin nhận toast khi phát hiện drift cần báo và khi huấn luyện lại xong.
  - Âm báo tổng hợp (Web Audio, không dùng tệp có bản quyền): nguy kịch, bất thường, drift, huấn luyện lại kêu khác nhau. Nút **Âm báo bật/tắt** trên header, nhớ lựa chọn trên trình duyệt; không lưu được thì nút ghi rõ chỉ áp dụng phiên hiện tại. Âm chỉ phát sau thao tác đầu tiên của người dùng (quy định của trình duyệt) và tự dừng khi tab ẩn.
- Trong bảng cảnh báo: hàng mới có nền vàng nhạt + tag `MỚI` trong vài giây rồi mờ dần, không nhấp nháy liên tục.
- Badge đổi mức rủi ro: chuyển màu mượt khi nhận prediction mới qua WebSocket.
- Tôn trọng `prefers-reduced-motion`: tắt mọi chuyển động khi người dùng bật tùy chọn giảm chuyển động.
- `focus-visible`: viền vàng `#e4b85c` 2px, cách phần tử 3px, cho điều hướng bằng bàn phím.
- Vùng bấm tối thiểu 32–44px. Mọi biểu đồ có `role="img"` và `aria-label` mô tả nội dung.

## 2.8.3. Kiến trúc thông tin và điều hướng

```mermaid
flowchart LR
    Login[Đăng nhập<br/>UC01] --> Role{Vai trò}
    Role -- Bác sĩ / Điều dưỡng --> Dash[Dashboard bệnh nhân<br/>UC04]
    Role -- Admin --> Users[Quản trị · Người dùng<br/>UC03]
    Dash --> Detail[Chi tiết bệnh nhân<br/>UC05, UC06, UC07]
    Dash --> Alerts[Trung tâm cảnh báo<br/>UC06, UC07]
    Alerts --> Detail
    Email([Email cảnh báo<br/>UC11]) -. liên kết .-> Detail
    Users --- Assign[Phân công<br/>UC13]
    Users --- Thresh[Ngưỡng cảnh báo<br/>UC08]
    Users --- Models[Giám sát mô hình<br/>UC09, UC10]
```

| Vai trò | Mục trên header | Route | API chính |
|---|---|---|---|
| Bác sĩ, Điều dưỡng | Bệnh nhân | `/patients`, `/patients/:id` | `GET /patients`, `/patients/{id}`, `/timeline`, `/alerts` |
| | Cảnh báo (badge số cảnh báo mở) | `/alerts` | `GET /alerts`, `/alerts/open-count`; Bác sĩ: `POST /alerts/{id}/acknowledge`, `/resolve` |
| Admin | Người dùng, Phân công, Ngưỡng cảnh báo, Giám sát mô hình | `/admin/users`, `/admin/assignments`, `/admin/thresholds`, `/admin/models` | `/users`, `/admin/*` |
| Mọi vai trò | Nút âm báo, tên + vai trò, nút đăng xuất ở góc phải header | — | `GET /auth/me`; đăng xuất = xóa token phía client (UC02) |

Nguyên tắc:
- Route được chặn theo vai trò đúng bảng phân quyền ở mục 2.2. Admin **không** có mục Bệnh nhân vì không theo dõi bệnh nhân; Admin chỉ quản lý phân công.
- Bác sĩ và Điều dưỡng chỉ thấy bệnh nhân được phân công. Việc lọc do backend thực hiện, frontend không tự lọc thay.
- Trạng thái kết nối WebSocket luôn hiển thị cạnh các điều khiển dưới tiêu đề trang (`Realtime · đã kết nối` / `Đang kết nối lại…`).

## 2.8.4. Thiết kế chi tiết các màn hình

### a) Đăng nhập (UC01)

![Màn hình đăng nhập](mockups/png/Login.png)

*Hình 2.8.2 — Màn hình đăng nhập.*

- **Bố cục**: chia đôi màn hình.
  - Nửa trái giới thiệu hệ thống bằng một câu nêu giá trị cốt lõi ("Cảnh báo sớm nguy kịch trong 4 giờ tới") và 3 badge rủi ro.
  - Nửa phải là form email/mật khẩu.
- **Tương tác**: ô đang nhập có viền focus vàng; có nút hiện/ẩn mật khẩu.
- **Báo lỗi**: hiển thị **ngay dưới nút Đăng nhập**, không dùng toast ở góc màn hình. Người dùng thấy lỗi ở đúng chỗ đang thao tác, và trình đọc màn hình đọc được theo thứ tự form.
- **Nội dung lỗi**: cùng một thông báo cho sai email, sai mật khẩu và tài khoản bị khóa ("Email hoặc mật khẩu không đúng"), để không lộ tài khoản nào tồn tại. Cách này khớp với API `POST /auth/login` trả 401.

### b) Dashboard bệnh nhân (UC04) — Bác sĩ, Điều dưỡng

![Dashboard bệnh nhân](mockups/png/Main.png)

*Hình 2.8.3 — Dashboard bệnh nhân của điều dưỡng: 6 bệnh nhân được phân công, sắp theo rủi ro dự báo.*

- **Mục tiêu**: trả lời câu hỏi "bệnh nhân nào cần chú ý trước" trong một lần nhìn.
- **Bố cục**: lưới thẻ 3 cột, mỗi thẻ một bệnh nhân. Danh sách **sắp theo rủi ro dự báo cao nhất lên đầu**, cùng mức thì xác suất nguy kịch cao hơn đứng trước (đúng thứ tự API trả về).
- **Nội dung thẻ**, theo thứ tự đọc:
  1. Mã bệnh nhân, tuổi, giới, giờ dữ liệu hiện tại.
  2. **Badge rủi ro dự báo 4 giờ tới** kèm xác suất — thông tin quan trọng nhất, đặt góc phải trên.
  3. 4 vitals mới nhất: HR, SpO₂, RR, huyết áp, chữ mono cỡ lớn.
  4. **Dải rủi ro 12 giờ qua**: 12 ô màu, cho thấy bệnh nhân đang xấu đi hay ổn định lại mà không cần mở chi tiết.
  5. **NEWS2 hiện tại** (màu trung tính) và **trạng thái bất thường**. Bệnh nhân vào ICU chưa đủ 16 giờ hiển thị "Chưa đủ 16 giờ" thay vì để trống khó hiểu.
  6. Số cảnh báo đang mở và thời gian cập nhật.
- **Viền dưới 3px** theo màu rủi ro giúp quét nhanh cả lưới thẻ.
- **Bộ lọc** Tất cả / Nguy kịch / Cảnh báo kèm số lượng; ô tìm theo mã bệnh nhân.
- **Realtime**: mỗi prediction mới qua WebSocket cập nhật đúng thẻ tương ứng. Badge đổi mức có chuyển màu và thẻ được sắp lại vị trí.

### c) Chi tiết bệnh nhân (UC05, UC06, UC07)

![Chi tiết bệnh nhân](mockups/png/PatientDetail.png)

*Hình 2.8.4 — Chi tiết bệnh nhân BN-10069 (góc nhìn Bác sĩ), đang ở trạng thái hover tại giờ 58.*

- **Hàng tóm tắt**: 3 thẻ ứng với 3 nguồn thông tin khác nhau, **không gộp làm một**.

| Thẻ | Nguồn | Nội dung |
|---|---|---|
| Rủi ro dự báo 4 giờ tới | Mô hình Random Forest (champion) | Badge lớn + xác suất nguy kịch (72%) + ngưỡng τ_critical và version model đang dùng |
| NEWS2 hiện tại | Luật lâm sàng | Tổng điểm /15 và **điểm từng thông số**, để biết thông số nào kéo điểm lên |
| Diễn biến bất thường | LSTM-Autoencoder | Trạng thái + điểm 0–1 + một câu giải thích ý nghĩa điểm |

- **Biểu đồ vitals 48 giờ** (chọn 24 giờ / 48 giờ / cả đợt):
  - **5 dải xếp chồng** dùng chung trục thời gian: nhịp tim, SpO₂, nhịp thở, huyết áp (tâm thu nét liền, tâm trương nét đứt, có nhãn trực tiếp), nhiệt độ. Mỗi chỉ số một đơn vị, nên tách dải thay vì dùng 2 trục y (một trục y cho mỗi biểu đồ).
  - **Vùng xám** = khoảng 0 điểm NEWS2 của từng thông số, để thấy ngay giá trị nào ra khỏi vùng an toàn.
  - Giờ không có số đo được **để trống**, không nội suy, đúng với dữ liệu mô hình nhìn thấy. Nhiệt độ đo 4 giờ/lần nên vẽ thành điểm.
  - **Vạch tím** đánh dấu giờ bị gắn cờ bất thường, xuyên qua mọi dải.
  - **Làn Bất thường**: cột điểm 0–1 mỗi giờ, đường ngưỡng 0,99; cột vượt ngưỡng tô tím.
  - **Dải Rủi ro 4 giờ tới**: mỗi ô là mức rủi ro dự báo tại giờ đó, cho thấy thời điểm bệnh nhân chuyển từ Bình thường sang Cảnh báo rồi Nguy kịch.
  - **Hover**: crosshair dọc qua mọi dải và tooltip tổng hợp mọi chỉ số, mức rủi ro, NEWS2, điểm bất thường tại giờ đó.
- **Cảnh báo của bệnh nhân**: đặt **dưới biểu đồ**, theo đúng quan hệ `UC07 <<include>> UC05` (xem vitals trước khi xác nhận). Mỗi cảnh báo hiển thị loại, trạng thái, giờ dữ liệu và chi tiết. Thao tác chỉ dành cho Bác sĩ:
  - `Mở` → nút **Xác nhận**, kèm nút mở vitals đúng giờ phát sinh cảnh báo;
  - `Đã xác nhận` → ô **ghi chú xử lý** (bắt buộc) + nút **Đã xử lý**;
  - `Đã xử lý` → hiển thị ghi chú và người xử lý.

### d) Trung tâm cảnh báo (UC06, UC07)

![Trung tâm cảnh báo](mockups/png/AlertsCenter.png)

*Hình 2.8.5 — Trung tâm cảnh báo (góc nhìn Bác sĩ).*

- **Bố cục**: bảng cảnh báo của mọi bệnh nhân được phân công, mới nhất lên đầu. Các cột: Loại, Bệnh nhân, Thời điểm (kèm giờ dữ liệu), NEWS2, Điểm (xác suất nguy kịch hoặc điểm bất thường, có nhãn), Trạng thái, Thao tác.
- **Bộ lọc**: theo trạng thái (Mở / Đã xác nhận / Đã xử lý / Tất cả, kèm số lượng) và theo loại (Rủi ro / Bất thường).
- **Cảnh báo mới** vào qua WebSocket: hàng có nền vàng nhạt và tag `MỚI` trong vài giây, đồng thời hiện overlay/toast như mục 2.8.2d. Badge số cảnh báo mở trên header cập nhật cùng lúc.
- **Phân quyền thao tác**: Bác sĩ có nút Xác nhận / Đã xử lý trên từng hàng. Điều dưỡng xem cùng danh sách nhưng không có cột Thao tác. Khi một bác sĩ đổi trạng thái, những người cùng phụ trách thấy trạng thái mới ngay (sự kiện `alert_update`).
- **Email cảnh báo (UC11)** không có màn hình riêng; email chứa đường dẫn mở thẳng trang chi tiết bệnh nhân.

### e) Quản trị · Người dùng (UC03) — Admin

![Quản trị người dùng](mockups/png/AdminUsers.png)

*Hình 2.8.6 — Tab Người dùng.*

- Header của Admin chỉ có 4 mục quản trị (không có mục Bệnh nhân); mục đang mở có gạch chân vàng.
- Bảng tài khoản: họ tên, email (mono), vai trò, trạng thái (công tắc Hoạt động / Đã khóa), số bệnh nhân phụ trách, nút Sửa. Nút **Thêm tài khoản** là hành động chính (nút xanh lá).
- Không xóa cứng tài khoản: khóa tài khoản để giữ lịch sử người xác nhận/xử lý cảnh báo. Admin không thể tự khóa hoặc tự bỏ quyền Quản trị của mình (API trả 409).

### f) Quản trị · Phân công (UC13) — Admin

![Quản trị phân công](mockups/png/AdminAssignments.png)

*Hình 2.8.7 — Tab Phân công: chọn bệnh nhân bên trái, quản lý người phụ trách bên phải.*

- Bố cục master–detail:
  - cột trái: danh sách bệnh nhân kèm số người phụ trách. Bệnh nhân **chưa có người phụ trách** được làm nổi bật bằng màu cảnh báo, vì cảnh báo của họ sẽ không gửi tới ai;
  - cột phải: bệnh nhân đang chọn, mức rủi ro hiện tại, danh sách người đang phụ trách (nút Gỡ) và ô thêm người phụ trách.
- Ô chọn chỉ liệt kê tài khoản Bác sĩ / Điều dưỡng đang hoạt động, đúng ràng buộc API (gán cho Admin → 422, gán trùng → 409).

### g) Quản trị · Ngưỡng cảnh báo (UC08) — Admin

![Quản trị ngưỡng cảnh báo](mockups/png/AdminThresholds.png)

*Hình 2.8.8 — Tab Ngưỡng cảnh báo.*

- Form 2 cột: cột trái là tên và giải thích ngắn của từng ngưỡng; cột phải là ô điều khiển.
- **τ_critical**: hai lựa chọn loại trừ nhau.
  - Mặc định: **dùng ngưỡng khuyến nghị của model champion**, hiển thị giá trị hiện hành 0,22.
  - Hoặc tự đặt ngưỡng. Cách này tránh việc Admin phải nhớ và nhập lại ngưỡng mỗi khi champion đổi.
- **τ_anomaly** kèm diễn giải "≈ 1% cửa sổ bình thường bị gắn cờ nhầm".
- **Thời gian chờ** ghi rõ đơn vị là giờ dữ liệu, không phải giờ đồng hồ (mục 2.9.6).
- **Lịch sử thay đổi**: mỗi lần lưu tạo một bản ghi mới, kèm người sửa và thời điểm. Thay đổi có hiệu lực với stream consumer trong vòng 30 giây.

### h) Quản trị · Giám sát mô hình (UC09, UC10) — Admin

![Quản trị giám sát mô hình](mockups/png/AdminModels.png)

*Hình 2.8.9 — Tab Giám sát mô hình.*

- **Hai thẻ champion** (dự báo rủi ro, phát hiện bất thường): version, họ mô hình, ngưỡng, và metric chính trên tập test. Mô hình rủi ro luôn kèm **baseline persistence**: model chỉ có giá trị khi thắng baseline này.
- **Biểu đồ drift**:
  - đường max PSI của mỗi lần kiểm tra, với 2 đường ngưỡng có nhãn (0,10 lệch trung bình; 0,25 lệch đáng kể);
  - điểm vượt 0,25 tô đỏ, có chú thích "Kích hoạt retrain tự động";
  - nút mở chi tiết PSI/KS từng đặc trưng.
  - Số liệu drift trên mockup chỉ để minh họa, vì DAG `drift_check` thuộc Giai đoạn G.
- **Bảng version**: mọi version kể cả bị từ chối, kèm kết quả quality gate, nguồn kích hoạt (INITIAL/DRIFT/MANUAL), metric và **lý do** từ chối. Ví dụ đúng lịch sử thật: v1 bị từ chối vì Recall CRITICAL 0,730 < 0,80.
- **Kích hoạt huấn luyện lại** (UC10):
  - bấm nút → nhận `dag_run_id` → khối trạng thái cạnh nút cập nhật định kỳ (queued / running / success / failed) cho tới khi có kết quả promote hay từ chối;
  - giao diện không giữ một request chờ lâu.

## 2.8.5. Nguyên tắc trực quan hóa dữ liệu

Mọi biểu đồ tuân theo hướng dẫn `dataviz`:

| Nguyên tắc | Áp dụng |
|---|---|
| Một trục y cho mỗi biểu đồ | Vitals khác đơn vị → 5 dải xếp chồng dùng chung trục thời gian |
| Màu theo vai trò, không tùy tiện | Đường dữ liệu dùng một màu xanh; màu trạng thái chỉ cho mức rủi ro; tím chỉ cho bất thường |
| Nhận diện không chỉ bằng màu | Huyết áp tâm thu/tâm trương phân biệt bằng nét liền/đứt + nhãn trực tiếp; mức rủi ro luôn kèm icon + chữ |
| Nét mảnh, lưới mờ | Đường 2px, lưới và trục màu tối nhạt, không lấn dữ liệu |
| Có lớp tương tác | Crosshair + tooltip trên biểu đồ đường; tooltip trên từng điểm/ô |
| Trung thực với dữ liệu | Giờ không đo để trống, không nội suy; ngưỡng vẽ thành đường có nhãn thay vì chỉ ghi trong chú thích |

## 2.8.6. Ghi chú hiện thực

- Mockup là tài liệu tham chiếu bắt buộc khi lập trình frontend (Giai đoạn F): lấy đúng token màu, font, kích thước và cấu tạo component từ `docs/design/mockups/build_mockups.py`.
- Sửa mockup: chỉnh `build_mockups.py`, chạy `python docs/design/mockups/build_mockups.py --png` để sinh lại artboard và ảnh trong `png/`, rồi cập nhật canvas.
- Ảnh trong mục này có kích thước 1440px chiều ngang, dùng trực tiếp được cho báo cáo Word (mục 6).
