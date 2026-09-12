**TRƯỜNG ĐẠI HỌC CÔNG NGHIỆP TP HỒ CHÍ MINH**

**KHOA CÔNG NGHỆ THÔNG TIN**

**ĐỒ ÁN CUỐI KÌ**

**⟨TÊN MÔN HỌC⟩**

**HỆ THỐNG GIÁM SÁT BỆNH NHÂN TỪ XA BẰNG STREAMING VÀ MLOPS**

*Remote Patient Monitoring System using Streaming and MLOps*

*Người thực hiện:* **NGUYỄN TẤN MINH -- 22643511**

⟨*nếu làm nhóm: bổ sung họ tên -- MSSV thành viên còn lại*⟩

Lớp : **⟨mã lớp⟩**

Khoá : **19**

*Người hướng dẫn:* **⟨học vị + họ tên giảng viên hướng dẫn⟩**

**THÀNH PHỐ HỒ CHÍ MINH, NĂM 2026**

\newpage

# LỜI CẢM ƠN

⟨*Viết sau — giữ đúng giọng của mẫu: cảm ơn Khoa Công nghệ Thông tin, cảm ơn giảng viên hướng dẫn (nêu rõ tên và môn học), cảm ơn nhóm nghiên cứu đi trước và cộng đồng dữ liệu mở. Với đề tài này cần cảm ơn thêm nhóm PhysioNet/MIT-LCP đã công bố MIMIC-III Clinical Database Demo dưới giấy phép Open Data Commons ODbL v1.0.*⟩

\newpage

# ĐỒ ÁN ĐƯỢC HOÀN THÀNH TẠI TRƯỜNG ĐẠI HỌC CÔNG NGHIỆP TP HỒ CHÍ MINH

Tôi xin cam đoan đây là sản phẩm đồ án của riêng tôi và được sự hướng dẫn của ⟨*họ tên giảng viên*⟩. Các nội dung nghiên cứu, kết quả trong đề tài này là trung thực và chưa công bố dưới bất kỳ hình thức nào trước đây. Những số liệu trong các bảng biểu phục vụ cho việc phân tích, nhận xét, đánh giá được chính tác giả thu thập từ các nguồn khác nhau có ghi rõ trong phần tài liệu tham khảo.

Ngoài ra, trong đồ án còn sử dụng một số nhận xét, đánh giá cũng như số liệu của các tác giả khác, cơ quan tổ chức khác đều có trích dẫn và chú thích nguồn gốc.

**Nếu phát hiện có bất kỳ sự gian lận nào tôi xin hoàn toàn chịu trách nhiệm về nội dung đồ án của mình.** Trường đại học Công nghiệp TP Hồ Chí Minh không liên quan đến những vi phạm tác quyền, bản quyền do tôi gây ra trong quá trình thực hiện (nếu có).

*TP. Hồ Chí Minh, ngày tháng năm*

*Tác giả*

*(ký tên và ghi rõ họ tên)*

*Nguyễn Tấn Minh*

\newpage

# PHẦN ĐÁNH GIÁ CỦA GIẢNG VIÊN

\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

Tp. Hồ Chí Minh, ngày tháng năm

(kí và ghi họ tên)

\newpage

# TÓM TẮT

Bệnh nhân nặng trong khoa hồi sức cần được theo dõi sinh hiệu liên tục, nhưng việc phát hiện dấu hiệu xấu đi thường phụ thuộc vào quan sát định kỳ của nhân viên y tế. Đồ án xây dựng một hệ thống giám sát bệnh nhân từ xa hoạt động theo thời gian thực, kết hợp kiến trúc streaming với quy trình MLOps vận hành liên tục. Dữ liệu là MIMIC-III Clinical Database Demo v1.4 (100 bệnh nhân ICU, giấy phép ODbL v1.0); sau tiền xử lý thu được 132 đợt ICU và 14.138 giờ dữ liệu trên lưới thời gian 1 giờ.

Hệ thống giải hai bài toán học máy bổ sung nhau. Bài toán thứ nhất **dự báo** mức độ rủi ro cao nhất trong 4 giờ tới theo thang NEWS2 rút gọn — không phân loại tình trạng tức thời, vì nhãn tức thời là hàm tất định của đặc trưng nên sẽ rò rỉ nhãn. Bài toán thứ hai phát hiện diễn biến bất thường so với chính baseline của bệnh nhân bằng LSTM-Autoencoder trên cửa sổ 12 giờ. Dữ liệu được chia theo bệnh nhân (patient-level split) thành bốn nhóm cố định 48/15/15/20 để không một bệnh nhân nào xuất hiện ở hai nhóm.

Trên tập kiểm tra cố định, mô hình dự báo rủi ro (Random Forest) đạt Macro F1 0,623 và Recall lớp CRITICAL 0,790, vượt rõ baseline persistence (0,547 và 0,308); mô hình bất thường đạt AUROC 0,864 với tỷ lệ gắn cờ nhầm 0,7%. Toàn hệ thống chạy thật trên Docker Compose: Kafka truyền sinh hiệu theo giờ, stream consumer tính đặc trưng và suy luận hai mô hình rồi ghi PostgreSQL/TimescaleDB, FastAPI đẩy sự kiện realtime qua WebSocket tới đúng nhân viên được phân công, còn Airflow tự kiểm tra drift và kích hoạt huấn luyện lại dưới sự kiểm soát của quality gate theo chiến lược Champion–Challenger trên MLflow.

Kết quả kiểm thử phi chức năng cho độ trễ đầu–cuối p95 1,30–1,62 giây với 20 bệnh nhân phát đồng thời, đạt ngưỡng thiết kế 2 giây; hệ thống không mất bản ghi và không tạo cảnh báo trùng khi consumer hoặc backend bị dừng giữa luồng dữ liệu. Đồ án cũng nêu rõ các hạn chế bắt buộc phải công khai, trong đó có việc tập kiểm tra đã được dùng hai lần và ngưỡng quality gate được hiệu chỉnh sau khi xem kết quả kiểm tra.

**Từ khoá:** giám sát bệnh nhân từ xa, xử lý luồng dữ liệu, MLOps, NEWS2, phát hiện bất thường, LSTM-Autoencoder, data drift, MIMIC-III.

\newpage

# DANH MỤC KÍ HIỆU VÀ CHỮ VIẾT TẮT

| Viết tắt | Nguyên văn | Nghĩa |
|---|---|---|
| API | Application Programming Interface | Giao diện lập trình ứng dụng |
| AUROC | Area Under the Receiver Operating Characteristic curve | Diện tích dưới đường cong ROC |
| CRUD | Create, Read, Update, Delete | Bốn tác vụ cơ bản trên dữ liệu |
| DAG | Directed Acyclic Graph | Đồ thị có hướng không chu trình (luồng công việc Airflow) |
| DFD | Data Flow Diagram | Sơ đồ luồng dữ liệu |
| ERD | Entity Relationship Diagram | Sơ đồ quan hệ thực thể |
| ICU | Intensive Care Unit | Khoa hồi sức tích cực |
| JWT | JSON Web Token | Chuẩn token xác thực |
| KS | Kolmogorov–Smirnov | Kiểm định so sánh hai phân phối |
| LSTM-AE | Long Short-Term Memory Autoencoder | Bộ tự mã hoá dùng mạng LSTM |
| MIMIC | Medical Information Mart for Intensive Care | Bộ dữ liệu hồi sức tích cực của MIT |
| MLOps | Machine Learning Operations | Vận hành hệ thống học máy |
| NEWS2 | National Early Warning Score 2 | Thang điểm cảnh báo sớm quốc gia (Anh), phiên bản 2 |
| PSI | Population Stability Index | Chỉ số ổn định phân phối |
| REST | Representational State Transfer | Kiểu kiến trúc giao tiếp web |
| SHAP | SHapley Additive exPlanations | Phương pháp giải thích đóng góp đặc trưng |
| SpO₂ | Peripheral capillary oxygen saturation | Độ bão hoà oxy máu ngoại vi |
| UC | Use Case | Trường hợp sử dụng |

\newpage

# DANH MỤC CÁC HÌNH VẼ

⟨*Trong Word: thay bảng này bằng mục lục hình tự động — References → Insert Table of Figures, nhãn "Hình". Danh sách dưới đây để kiểm tra đủ hình và đúng thứ tự.*⟩

| Hình | Tên hình |
|---|---|
| Hình 2.1 | Sơ đồ chức năng tổng quát của hệ thống |
| Hình 2.2 | Biểu đồ Use Case |
| Hình 2.3 | DFD mức ngữ cảnh (Level 0) |
| Hình 2.4 | DFD mức 1 |
| Hình 2.5 | Biểu đồ quan hệ dữ liệu (ERD) |
| Hình 3.1 | Kiến trúc tổng quát của hệ thống |
| Hình 3.2 | Luồng xử lý dữ liệu streaming đến cảnh báo |
| Hình 3.3 | Tuần tự dự đoán realtime và phát cảnh báo |
| Hình 3.4 | Luồng đăng nhập và mở kết nối realtime |
| Hình 3.5 | Tuần tự đăng nhập và mở WebSocket |
| Hình 3.6 | Biểu đồ lớp |
| Hình 3.7 | Luồng phát hiện drift và huấn luyện lại mô hình |
| Hình 3.8 | Tuần tự phát hiện drift và thông báo Admin |
| Hình 3.9 | Tuần tự kích hoạt huấn luyện lại thủ công |
| Hình 3.10 | Kiến trúc thông tin và điều hướng giao diện |
| Hình 4.1 | Ma trận nhầm lẫn của mô hình dự báo rủi ro trên tập kiểm tra |
| Hình 4.2 | Mức đóng góp đặc trưng (SHAP) cho lớp CRITICAL |
| Hình 4.3 | Phân bố điểm bất thường trên cửa sổ bình thường và cửa sổ bị tiêm bất thường |
| Hình 4.4 | Màn hình đăng nhập |
| Hình 4.5 | Danh sách bệnh nhân được phân công (điều dưỡng phụ trách 20 bệnh nhân) |
| Hình 4.6 | Chi tiết bệnh nhân: dự báo rủi ro, NEWS2 và biểu đồ sinh hiệu |
| Hình 4.7 | Danh sách cảnh báo |
| Hình 4.8 | Phạm vi xem theo phân công của một bác sĩ |
| Hình 4.9 | Quản lý tài khoản người dùng |
| Hình 4.10 | Phân công bệnh nhân cho bác sĩ và điều dưỡng |
| Hình 4.11 | Cấu hình ngưỡng cảnh báo |
| Hình 4.12 | Giám sát mô hình: quality gate và biểu đồ drift |

\newpage

# DANH MỤC CÁC BẢNG

⟨*Trong Word: mục lục bảng tự động, nhãn "Bảng".*⟩

| Bảng | Tên bảng |
|---|---|
| Bảng 2.1 | Danh sách use case theo vai trò |
| Bảng 3.1 | Tập đặc trưng đầu vào của mô hình dự báo rủi ro |
| Bảng 3.2 | Thang điểm NEWS2 rút gọn |
| Bảng 4.1 | Quy mô dữ liệu sau tiền xử lý |
| Bảng 4.2 | Chia dữ liệu theo bệnh nhân |
| Bảng 4.3 | Công nghệ và phiên bản sử dụng |
| Bảng 4.4 | Tiêu chí quality gate |
| Bảng 4.5 | So sánh các thuật toán dự báo rủi ro (cross-validation) |
| Bảng 4.6 | Kết quả mô hình dự báo rủi ro trên ba tập dữ liệu |
| Bảng 4.7 | Kết quả mô hình phát hiện bất thường |
| Bảng 4.8 | Kết quả chạy end-to-end tầng streaming |
| Bảng 4.9 | Kết quả phát hiện drift và huấn luyện lại tự động |
| Bảng 4.10 | Độ trễ đầu–cuối từ producer tới dashboard |
| Bảng 4.11 | Số lượng kiểm thử tự động theo thành phần |

\newpage

# CHƯƠNG 1 GIỚI THIỆU VỀ BÀI TOÁN

## 1.1 Giới thiệu về bài toán

Trong khoa hồi sức tích cực (ICU), tình trạng bệnh nhân có thể xấu đi trong vài giờ. Các dấu hiệu sinh tồn — nhịp tim, độ bão hoà oxy, nhịp thở, huyết áp, nhiệt độ — được đo liên tục hoặc gần liên tục, và thực tế lâm sàng cho thấy phần lớn các biến cố nặng đều có dấu hiệu báo trước trong dữ liệu sinh hiệu nhiều giờ trước khi được phát hiện. Tuy nhiên, việc nhận ra những dấu hiệu đó phụ thuộc vào quan sát định kỳ của nhân viên y tế; khi một điều dưỡng phụ trách nhiều bệnh nhân, khoảng thời gian giữa hai lần đánh giá chính là khoảng thời gian rủi ro.

Các thang điểm cảnh báo sớm như NEWS2 được thiết kế để chuẩn hoá việc đánh giá này: mỗi thông số sinh tồn được cho điểm theo mức độ lệch khỏi khoảng bình thường, tổng điểm quyết định mức độ theo dõi. NEWS2 là một **luật tính toán trên trạng thái hiện tại**, nên tự nó không trả lời được câu hỏi quan trọng hơn với người trực: *trong vài giờ tới, bệnh nhân nào có khả năng chuyển nặng?*

Đồ án đặt bài toán như sau. Cho một luồng dữ liệu sinh hiệu theo giờ của nhiều bệnh nhân đang nằm ICU, hệ thống cần (1) dự báo mức độ rủi ro cao nhất mà bệnh nhân sẽ đạt tới trong 4 giờ tiếp theo, (2) phát hiện những diễn biến bất thường so với chính baseline của bệnh nhân đó, (3) phát cảnh báo tới đúng bác sĩ và điều dưỡng được phân công trong thời gian đủ ngắn để còn kịp can thiệp, và (4) tự theo dõi chất lượng của chính các mô hình đó khi phân phối dữ liệu thay đổi theo thời gian.

Yêu cầu thứ tư là điểm khiến bài toán này khác với một bài tập học máy thông thường. Một mô hình được huấn luyện trên dữ liệu quá khứ sẽ suy giảm khi thiết bị đo, quy trình chăm sóc hoặc cơ cấu bệnh nhân thay đổi — hiện tượng data drift. Trong môi trường y tế, việc âm thầm suy giảm này nguy hiểm hơn việc mô hình báo lỗi. Vì vậy hệ thống phải có một vòng vận hành khép kín: theo dõi phân phối dữ liệu đang chảy vào, tự huấn luyện lại khi cần, và **chỉ** cho mô hình mới thay thế mô hình đang dùng khi nó chứng minh được là tốt hơn trên một tập kiểm tra cố định.

## 1.2 Ý nghĩa của bài toán

### 1.2.1. Ý nghĩa học thuật

Đề tài kết hợp ba hướng thường được nghiên cứu tách rời: dự báo suy giảm lâm sàng từ dữ liệu chuỗi thời gian, phát hiện bất thường không giám sát trên dữ liệu sinh hiệu, và kỹ thuật MLOps cho hệ thống học máy vận hành liên tục. Việc đặt cả ba trong một hệ thống chạy thật buộc phải giải quyết những vấn đề ít xuất hiện khi làm riêng lẻ, cụ thể:

- **Tránh rò rỉ nhãn.** Nếu nhãn rủi ro được tính từ chính các thông số tại thời điểm t, mọi mô hình học trên đặc trưng tại t đều chỉ đang học lại công thức NEWS2. Đồ án chuyển sang bài toán dự báo (nhãn là mức rủi ro cao nhất trong khoảng (t, t+4]) và bắt buộc mô hình phải thắng baseline persistence — tức là thắng phương án "giả định 4 giờ nữa vẫn như hiện tại".
- **Chia dữ liệu theo bệnh nhân.** Dữ liệu sinh hiệu trong cùng một bệnh nhân tương quan rất mạnh; chia ngẫu nhiên theo dòng sẽ cho kết quả lạc quan giả. Đồ án dùng bốn nhóm cố định theo `subject_id`.
- **Đồng nhất giữa huấn luyện và vận hành.** Đặc trưng lúc suy luận trực tuyến phải trùng khít đặc trưng lúc huấn luyện. Đồ án đưa toàn bộ phép tính đặc trưng vào một thư viện dùng chung và kiểm chứng bằng test so sánh từng giờ trên dữ liệu thật.
- **Ngưỡng phát hiện drift phải hiệu chỉnh theo quy mô dữ liệu.** Ngưỡng PSI ≥ 0,25 thường được trích dẫn tỏ ra không dùng được với cửa sổ khoảng 20 bệnh nhân: nó gắn cờ 93% các cửa sổ không hề có drift.

### 1.2.2. Ý nghĩa thực tiễn

Về mặt ứng dụng, hệ thống cho thấy một kiến trúc khả thi để đưa mô hình học máy vào quy trình theo dõi bệnh nhân mà vẫn giữ được ba tính chất mà môi trường bệnh viện đòi hỏi:

- **Cảnh báo đến đúng người, không gây bão cảnh báo.** Cảnh báo chỉ đẩy tới bác sĩ và điều dưỡng được phân công cho bệnh nhân đó; cùng một loại cảnh báo đang mở thì không tạo thêm, và có thời gian nguội tính theo giờ dữ liệu. Trong lần chạy end-to-end 1.834 giờ, 507 giờ được dự báo CRITICAL chỉ sinh ra 28 cảnh báo.
- **Không mất dữ liệu khi có sự cố.** Thứ tự xử lý được thiết kế để ghi cơ sở dữ liệu xong mới xác nhận đã tiêu thụ dữ liệu, nên khi tiến trình bị dừng đột ngột thì dữ liệu được xử lý lại chứ không mất.
- **Người quản trị kiểm soát được mô hình.** Mọi phiên bản mô hình đều được ghi lại kèm kết luận của quality gate và lý do bị từ chối, hiển thị trên giao diện quản trị; ngưỡng cảnh báo cũng do người quản trị điều chỉnh và có hiệu lực mà không cần khởi động lại hệ thống.

\newpage

# CHƯƠNG 2 PHÂN TÍCH YÊU CẦU CỦA BÀI TOÁN

## 2.1 Yêu cầu của bài toán

⟨*Nội dung cần viết — nguồn: `docs/design/01_gioi_thieu.md`, `docs/design/02_1_so_do_chuc_nang.md`, `docs/design/02_2_usecase.md`.*⟩

⟨*Trình bày: yêu cầu chức năng theo 4 nhóm của sơ đồ chức năng; yêu cầu phi chức năng (độ trễ p95 < 2 giây, chịu lỗi, phân quyền theo phân công, bảo mật JWT 3 vai trò).*⟩

![Sơ đồ chức năng tổng quát của hệ thống](figures/so_do_chuc_nang.png){width="15cm"}

**Hình 2.1** Sơ đồ chức năng tổng quát của hệ thống

⟨*Bảng 2.1: liệt kê 13 use case UC01–UC13 kèm vai trò — lấy từ `02_2_usecase.md`.*⟩

![Biểu đồ Use Case](figures/usecase.png){width="12cm"}

**Hình 2.2** Biểu đồ Use Case của hệ thống

## 2.2 Các phương pháp giải quyết bài toán

⟨*Phần "nghiên cứu liên quan" của báo cáo. Cần tra cứu và trích dẫn tài liệu thật cho 4 nhóm:*⟩

1. ⟨*Thang điểm cảnh báo sớm: NEWS/NEWS2 (Royal College of Physicians), so sánh với MEWS; các nghiên cứu đánh giá năng lực dự báo của NEWS2.*⟩
2. ⟨*Dự báo suy giảm lâm sàng bằng học máy trên MIMIC: các mô hình dự báo tử vong/chuyển ICU, bài toán early warning.*⟩
3. ⟨*Phát hiện bất thường trên chuỗi thời gian bằng autoencoder/LSTM-AE; ưu và nhược so với phương pháp thống kê.*⟩
4. ⟨*Phát hiện data drift (PSI, kiểm định KS) và thực hành MLOps: Champion–Challenger, quality gate, model registry.*⟩

⟨*Kết đoạn: chỉ ra khoảng trống mà đồ án nhắm vào — phần lớn công trình dừng ở mô hình offline, ít công trình đặt mô hình vào một hệ thống streaming có vòng vận hành khép kín và có kiểm chứng phi chức năng.*⟩

## 2.3 Phương pháp đề xuất giải quyết bài toán

⟨*Nêu tổng quan hướng giải quyết (chi tiết ở Chương 3): kiến trúc streaming Kafka, hai mô hình bổ sung nhau, MLOps với Airflow + MLflow. Sau đó mô tả luồng dữ liệu và mô hình dữ liệu.*⟩

⟨*Nguồn: `docs/design/02_6_dfd_database.md`, `docs/design/02_7_erd.md`.*⟩

![DFD mức ngữ cảnh](figures/dfd_level0.png){width="15cm"}

**Hình 2.3** Sơ đồ luồng dữ liệu mức ngữ cảnh (Level 0)

![DFD mức 1](figures/dfd_level1.png){width="15cm"}

**Hình 2.4** Sơ đồ luồng dữ liệu mức 1

![Biểu đồ quan hệ dữ liệu](figures/erd.png){width="15cm"}

**Hình 2.5** Biểu đồ quan hệ dữ liệu (ERD)

⟨*Thuyết minh ERD: 10 bảng; `vital_records` và `predictions` là hypertable của TimescaleDB nên khoá chính phải chứa `recorded_at`; tham chiếu vào hypertable là tham chiếu logic, không đặt ràng buộc khoá ngoại.*⟩

\newpage

# CHƯƠNG 3 PHƯƠNG PHÁP ĐỀ XUẤT

## 3.1. Mô hình tổng quát

![Kiến trúc tổng quát của hệ thống](figures/kien_truc_he_thong.png){width="15cm"}

**Hình 3.1** Kiến trúc tổng quát của hệ thống

⟨*Thuyết minh 5 tầng theo hình: nguồn dữ liệu và tiền xử lý, tầng streaming, mô hình học máy, lưu trữ, tầng ứng dụng, tầng MLOps. Nhấn mạnh hai quyết định kiến trúc: (a) mọi phép tính đặc trưng nằm trong một thư viện dùng chung `rpm_common` để huấn luyện và vận hành không lệch nhau; (b) consumer nạp mô hình theo alias `champion` trên MLflow và tự đổi khi alias đổi, nên thay mô hình không cần triển khai lại.*⟩

## 3.2 Đặc trưng của mô hình đề xuất

### 3.2.1. Thu thập và xử lý dữ liệu

⟨*Nguồn: `ml/README.md`, `ml/data_dictionary.md`, `docs/design/02_9_thiet_ke_giai_thuat.md` mục 2.9.1.*⟩

⟨*Nội dung: nguồn MIMIC-III Demo và giấy phép; mapping itemid (gộp 220050/220051, 676, 615/224690; loại 677/679); làm sạch (đổi °F sang °C, lọc `error = 1`, `stopped = "D/C'd"`, giá trị ngoài khoảng hợp lệ); dựng lưới 1 giờ lấy trung vị; forward-fill có giới hạn và lý do **không** nội suy.*⟩

### 3.2.2. Kỹ thuật đặc trưng

⟨*Bảng 3.1 (tập đặc trưng) và Bảng 3.2 (thang NEWS2 rút gọn) — nguồn `02_9` mục 2.9.2.*⟩

⟨*Nội dung: NEWS2 rút gọn 5 thông số (0–15 điểm) và quy tắc một thông số đạt 3 điểm; đặc trưng cửa sổ 6 giờ; baseline cá nhân lũy tiến 24 giờ và điểm z so với baseline; nhãn dự báo `y_t = max` mức rủi ro trong (t, t+4]. Nhấn mạnh tính nhân quả: đặc trưng tại t chỉ dùng dữ liệu ≤ t, có unit test kiểm chứng.*⟩

![Luồng xử lý dữ liệu streaming đến cảnh báo](figures/activity_streaming.png){width="10cm"}

**Hình 3.2** Luồng xử lý dữ liệu streaming đến cảnh báo

![Tuần tự dự đoán realtime và phát cảnh báo](figures/sequence_realtime.png){width="15cm"}

**Hình 3.3** Tuần tự dự đoán realtime và phát cảnh báo

### 3.2.3. Kiến trúc hai mô hình

⟨*Nguồn: `02_9` mục 2.9.2 (rủi ro) và 2.9.3 (bất thường).*⟩

⟨*Mô hình rủi ro: so sánh Random Forest, Logistic Regression, XGBoost và baseline persistence; cách chọn ngưỡng τ_critical trên dự đoán out-of-fold GroupKFold của train ∪ validation với mục tiêu Recall CRITICAL 0,80.*⟩

⟨*Mô hình bất thường: LSTM-Autoencoder trên cửa sổ 12 giờ × 6 kênh điểm z; bước căn giữa cửa sổ theo kênh và lý do (ngưỡng ổn định hơn nhiều giữa các bệnh nhân); chuyển lỗi tái tạo sang điểm 0–1 bằng ECDF; điểm bất thường sớm nhất chỉ có ở giờ thứ 16 (6 giờ baseline + cửa sổ 12 giờ).*⟩

![Luồng đăng nhập và mở kết nối realtime](figures/activity_dang_nhap.png){width="8cm"}

**Hình 3.4** Luồng đăng nhập và mở kết nối realtime

![Tuần tự đăng nhập và mở WebSocket](figures/sequence_dang_nhap.png){width="14cm"}

**Hình 3.5** Tuần tự đăng nhập và mở kết nối WebSocket

![Biểu đồ lớp](figures/class_diagram.png){width="15cm"}

**Hình 3.6** Biểu đồ lớp của hệ thống

⟨*Thuyết minh biểu đồ lớp và thiết kế giao diện — nguồn `02_5_class.md`, `02_8_thiet_ke_giao_dien.md`.*⟩

![Kiến trúc thông tin và điều hướng giao diện](figures/ia_navigation.png){width="15cm"}

**Hình 3.10** Kiến trúc thông tin và điều hướng giao diện

### 3.2.4. Đánh giá mô hình và vòng vận hành MLOps

⟨*Nguồn: `02_9` mục 2.9.4 (drift), 2.9.5 (Champion–Challenger), `02_10` mục 2.10.3 (quality gate).*⟩

⟨*Nội dung: chỉ số đánh giá và lý do chọn Macro F1 + Recall CRITICAL (dữ liệu mất cân bằng); quality gate ba điều kiện; phát hiện drift bằng PSI với ngưỡng hiệu chỉnh theo từng đặc trưng; cơ chế chống vòng lặp retrain (cooldown 1 giờ, không trigger khi đang chạy).*⟩

![Luồng phát hiện drift và huấn luyện lại mô hình](figures/activity_drift.png){width="9cm"}

**Hình 3.7** Luồng phát hiện drift và huấn luyện lại mô hình

![Tuần tự phát hiện drift và thông báo Admin](figures/sequence_drift.png){width="15cm"}

**Hình 3.8** Tuần tự phát hiện drift và thông báo người quản trị

![Tuần tự kích hoạt huấn luyện lại thủ công](figures/sequence_retrain.png){width="15cm"}

**Hình 3.9** Tuần tự kích hoạt huấn luyện lại mô hình thủ công

\newpage

# CHƯƠNG 4 THỰC NGHIỆM

## 4.1 Dữ liệu

⟨*Nguồn: `ml/README.md`, `docs/report/ghi_chu_bao_cao.md` mục 3.2.*⟩

**Bảng 4.1** Quy mô dữ liệu sau tiền xử lý

| Chỉ tiêu | Giá trị |
|---|---|
| Bộ dữ liệu | MIMIC-III Clinical Database Demo v1.4 (ODbL v1.0) |
| Số bệnh nhân trong bộ dữ liệu | 100 |
| Số bệnh nhân có dữ liệu sinh hiệu dùng được | 98 |
| Số đợt ICU sau tiền xử lý | 132 |
| Số giờ dữ liệu trên lưới 1 giờ | 14.138 |
| Nhóm phát lại (stream) | 20 bệnh nhân, 1.834 giờ |

**Bảng 4.2** Chia dữ liệu theo bệnh nhân (`ml/splits/subject_split.json`, seed 42)

| Nhóm | Số bệnh nhân | Mục đích |
|---|---|---|
| train | 48 | Huấn luyện mô hình |
| validation | 15 | Chọn siêu tham số, theo dõi quá khớp |
| test | 15 | **Chỉ** dùng cho quality gate |
| stream | 20 | Phát lại mô phỏng bệnh nhân đang nằm viện |

⟨*Nêu rõ: file chia nhóm là cố định, không tạo lại, để mọi lần huấn luyện lại đều so sánh trên cùng một tập kiểm tra.*⟩

## 4.2 Xử lý dữ liệu

⟨*Mô tả pipeline tiền xử lý đã chạy thật và các tệp sinh ra (`hourly.parquet`, `stream_replay.parquet`, `summary.json`); thống kê tỷ lệ thiếu dữ liệu theo từng thông số; phân bố nhãn ba mức và mức độ mất cân bằng.*⟩

## 4.3 Công nghệ sử dụng

**Bảng 4.3** Công nghệ và phiên bản sử dụng

| Lớp | Công nghệ (phiên bản) |
|---|---|
| Streaming | Apache Kafka (Confluent `cp-kafka` 7.6.1, Zookeeper 7.6.1), client `confluent-kafka` 2.15.1 |
| Cơ sở dữ liệu | PostgreSQL 16 + TimescaleDB 2.30.0, SQLAlchemy 2.0.49, Alembic 1.15.1 |
| Học máy | scikit-learn 1.3.2, XGBoost 3.0.0, TensorFlow 2.21.0 / Keras 3.13.1, SHAP 0.51.0, SciPy 1.16.2 |
| MLOps | MLflow 3.11.1 (tracking + registry, alias `champion`), Apache Airflow 2.9.3 (LocalExecutor) |
| Backend | FastAPI 0.135.3, Uvicorn 0.34.0, Pydantic 2.12.5, PyJWT 2.12.1, bcrypt 4.2.1 |
| Frontend | React 19.2, TypeScript 7.0, Vite 8.2, Tailwind CSS 4.3, Base UI 1.8, React Router 7.18 |
| Hạ tầng | Docker Compose, Prometheus, Grafana |

⟨*Thuyết minh lý do chọn: Kafka (giữ thứ tự theo bệnh nhân bằng key, cho phép mở rộng bằng partition), TimescaleDB (hypertable cho dữ liệu chuỗi thời gian), MLflow (alias `champion` thay cho stage `Production` đã lỗi thời), Airflow (điều phối job định kỳ).*⟩

## 4.4 Cách đánh giá

⟨*Nguồn: `docs/design/02_10_thiet_ke_test.md`.*⟩

⟨*Nội dung: bốn tầng kiểm thử (unit, integration, model evaluation/quality gate, phi chức năng); chỉ số của từng mô hình; baseline persistence làm mốc so sánh.*⟩

**Bảng 4.4** Tiêu chí quality gate

| Mô hình | Tiêu chí đạt |
|---|---|
| Dự báo rủi ro (h = 4) | Macro F1 ≥ 0,60 và cao hơn baseline persistence; Recall CRITICAL ≥ 0,75 tại τ_critical; không kém champion hiện tại ở cả hai chỉ số |
| Phát hiện bất thường | AUROC ≥ 0,75 trên tập kiểm tra có 10% cửa sổ bị tiêm bất thường; AUROC không kém champion |

⟨**Bắt buộc nêu**: *ngưỡng Recall CRITICAL được hạ từ 0,80 xuống 0,75 sau khi đã xem kết quả trên tập kiểm tra, và gate của mô hình bất thường được đổi từ Precision/Recall ≥ 0,7 sang AUROC sau khi xem kết quả lần đầu. Tập kiểm tra của cả hai mô hình đã được dùng hai lần. Chi tiết lý do ở `02_10` mục 2.10.3.*⟩

## 4.5 Kết quả đạt được

### 4.5.1. Mô hình dự báo rủi ro

**Bảng 4.5** So sánh các thuật toán (cross-validation trên train ∪ validation)

| Thuật toán | Macro F1 (CV) |
|---|---|
| Random Forest (được chọn) | 0,622 |
| Logistic Regression | 0,618 |
| XGBoost | 0,608 |
| Baseline persistence | 0,565 |

**Bảng 4.6** Kết quả `risk_classifier` v2 (Random Forest, τ_critical = 0,22)

| Tập dữ liệu | Macro F1 | Recall CRITICAL | Precision CRITICAL |
|---|---|---|---|
| Out-of-fold (63 bệnh nhân) | 0,591 | 0,807 | 0,395 |
| Validation | 0,623 | 0,849 | 0,498 |
| **Test** | **0,623** | **0,790** (249/315) | 0,391 |
| Baseline persistence (test) | 0,547 | 0,308 | — |

⟨*Nhận xét: mô hình vượt persistence rõ rệt ở Recall CRITICAL (0,790 so với 0,308) — đúng mục tiêu của hệ thống cảnh báo sớm. Nêu thêm kết quả với h = 1: mô hình đạt Macro F1 0,578 < persistence 0,621, tức ở tầm 1 giờ persistence rất khó thắng vì sinh hiệu tự tương quan mạnh; đây là lý do chọn h = 4.*⟩

![Ma trận nhầm lẫn trên tập kiểm tra](../../ml/reports/fig_risk_confusion.png){width="12cm"}

**Hình 4.1** Ma trận nhầm lẫn của mô hình dự báo rủi ro trên tập kiểm tra

![Mức đóng góp đặc trưng cho lớp CRITICAL](../../ml/reports/fig_risk_shap_critical.png){width="14cm"}

**Hình 4.2** Mức đóng góp đặc trưng (SHAP) cho lớp CRITICAL

⟨*Nhận xét SHAP: `news2_max_6h`, `news2_score`, `respiratory_rate_mean_6h`, `heart_rate` đứng đầu — phù hợp với lý luận lâm sàng, và cho thấy mô hình dùng cả lịch sử 6 giờ chứ không chỉ trạng thái hiện tại.*⟩

### 4.5.2. Mô hình phát hiện bất thường

**Bảng 4.7** Kết quả `anomaly_detector` trên tập kiểm tra (10% cửa sổ bị tiêm bất thường)

| Chỉ số | Giá trị |
|---|---|
| AUROC | 0,864 |
| Precision tại τ = 0,99 | 0,727 |
| Recall tại τ = 0,99 | 0,167 |
| F1 tại τ = 0,99 | 0,271 |
| Tỷ lệ gắn cờ nhầm | 0,7% |
| Recall theo loại: spike / level shift / drift | 0,25 / 0,19 / 0,06 |

![Phân bố điểm bất thường](../../ml/reports/fig_anomaly_scores.png){width="14cm"}

**Hình 4.3** Phân bố điểm bất thường trên cửa sổ bình thường và cửa sổ bị tiêm bất thường

⟨*Nhận xét: Recall thấp tại ngưỡng p99 là đánh đổi có chủ ý để giữ tỷ lệ báo nhầm ở mức 0,7%. Bằng chứng bổ sung trên dữ liệu thật (không tiêm): tỷ lệ gắn cờ tăng theo mức NEWS2 — NORMAL 0,6%, WARNING 17,4%, CRITICAL 34,8%; AUROC phân biệt cửa sổ CRITICAL với NORMAL đạt 0,837.*⟩

### 4.5.3. Kết quả chạy end-to-end tầng streaming

**Bảng 4.8** Kết quả chạy end-to-end (20 bệnh nhân, 1.834 giờ dữ liệu)

| Chỉ tiêu | Kết quả |
|---|---|
| Bản ghi sinh hiệu ghi vào cơ sở dữ liệu | 1.834 / 1.834 |
| Bản ghi dự đoán | 1.834 |
| Message trên `predictions-stream` | 1.834 |
| Số giờ được dự báo CRITICAL | 507 |
| Số cảnh báo sinh ra | 28 (19 RISK, 9 ANOMALY) |
| Cảnh báo OPEN trùng | 0 |
| Thời gian xử lý mỗi message | 130–190 ms (đặc trưng ~45 ms, Random Forest ~12 ms, LSTM-AE ~64 ms) |

⟨*Nhận xét: tỷ lệ 28 cảnh báo cho 507 giờ CRITICAL là minh chứng định lượng cho cơ chế chống bão cảnh báo.*⟩

### 4.5.4. Kết quả vòng vận hành MLOps

⟨*Bảng 4.9 — nguồn `docs/report/ghi_chu_bao_cao.md` mục 3.4(d). Nội dung: hiệu chỉnh ngưỡng drift theo từng đặc trưng; kịch bản phát lại sạch (không drift); kịch bản `--drift` (phát hiện drift SpO₂, tự kích hoạt retrain, thông báo người quản trị); cơ chế cooldown chặn retrain lặp; kết quả 4 challenger đều bị gate từ chối hoặc chỉ bằng điểm champion.*⟩

⟨*Lưu ý khi viết: các mốc giờ trong ghi chú (15:00, 15:06, 15:14) là giờ UTC, còn giao diện hiển thị giờ địa phương UTC+7 (22:00, 22:06, 22:14). Phải thống nhất một hệ giờ giữa phần chữ và ảnh chụp.*⟩

### 4.5.5. Kết quả kiểm thử phi chức năng

**Bảng 4.10** Độ trễ đầu–cuối từ lúc producer phát tới lúc dashboard nhận qua WebSocket

| Nhóm mẫu | n | p50 (s) | p95 (s) | p99 (s) | max (s) |
|---|---|---|---|---|---|
| 20 bệnh nhân phát đồng thời, tốc độ mặc định | 220 | 0,71 | **1,30** | 1,51 | 1,63 |
| Toàn bộ mẫu | 388 | 0,74 | 1,52 | 1,87 | 2,33 |
| Cửa sổ đã đủ 12 giờ (có chạy LSTM-AE) | 80 | 0,95 | 1,75 | 2,16 | 2,25 |

⟨*Nhận xét: đạt ngưỡng thiết kế p95 < 2 giây; ba lần chạy độc lập cho p95 của kịch bản 20 bệnh nhân là 1,30 / 1,48 / 1,62 giây. Phần lớn độ trễ là hàng đợi trong một nhịp phát vì consumer xử lý tuần tự (~70 ms/message), nên khoảng 28 bệnh nhân mỗi nhịp là chạm ngưỡng 2 giây với một consumer.*⟩

⟨*Chịu lỗi: giết cứng consumer giữa luồng dữ liệu → dựng lại trạng thái từ cơ sở dữ liệu, đủ bản ghi, không giờ trùng, không cảnh báo trùng. Tắt backend giữa lúc phát lại → bật lại đọc tiếp từ offset đã lưu, cảnh báo sinh ra trong lúc đó vẫn được xử lý và ghi `notification_logs` đúng người được phân công.*⟩

**Bảng 4.11** Số lượng kiểm thử tự động

| Thành phần | Số test |
|---|---|
| `packages/common` (đặc trưng dùng chung) | 99 |
| `ml` (dữ liệu, mô hình, gate, drift) | 61 |
| `services/streaming` | 27 |
| `services/backend` (cơ sở dữ liệu thật) | 34 |
| `services/frontend` (Vitest) | 23 |
| `tests/e2e` (hệ thống thật) | 10 |
| **Tổng** | **254** |

### 4.5.6. Giao diện hệ thống

![Màn hình đăng nhập](../../images/1_login.png){width="15cm"}

**Hình 4.4** Màn hình đăng nhập

![Danh sách bệnh nhân](../../images/2_patient_list.png){width="15cm"}

**Hình 4.5** Danh sách bệnh nhân được phân công, sắp theo mức rủi ro dự báo

![Chi tiết bệnh nhân](../../images/3_patient_detail.png){width="15cm"}

**Hình 4.6** Chi tiết bệnh nhân: dự báo rủi ro 4 giờ tới, NEWS2 và biểu đồ sinh hiệu

![Danh sách cảnh báo](../../images/4_alerts.png){width="15cm"}

**Hình 4.7** Danh sách cảnh báo và trạng thái xử lý

![Phạm vi xem theo phân công](../../images/5_patients_bs_an.png){width="15cm"}

**Hình 4.8** Phạm vi xem theo phân công: bác sĩ chỉ thấy bệnh nhân mình phụ trách

![Quản lý tài khoản](../../images/6_admin_user.png){width="15cm"}

**Hình 4.9** Quản lý tài khoản người dùng

![Phân công bệnh nhân](../../images/7__admin_asignments.png){width="15cm"}

**Hình 4.10** Phân công bệnh nhân cho bác sĩ và điều dưỡng

![Cấu hình ngưỡng cảnh báo](../../images/8_admin_thresholds.png){width="15cm"}

**Hình 4.11** Cấu hình ngưỡng cảnh báo

![Giám sát mô hình](../../images/9_admin_models.png){width="15cm"}

**Hình 4.12** Giám sát mô hình: kết luận quality gate của từng phiên bản và biểu đồ drift

\newpage

# CHƯƠNG 5 KẾT LUẬN

## 5.1 Kết luận

### 5.1.1. Kết quả đạt được

⟨*Nguồn: `docs/report/ghi_chu_bao_cao.md` mục 4.*⟩

- Xây dựng được pipeline hoàn chỉnh từ dữ liệu ICU thật tới dashboard realtime, chạy thật trên Docker Compose.
- Hai mô hình đều qua quality gate và thắng baseline persistence trên tập kiểm tra cố định.
- Vòng vận hành MLOps khép kín: phát hiện drift tự động kích hoạt huấn luyện lại, quality gate chặn mô hình kém, đổi mô hình đang dùng chỉ bằng cách đổi alias.
- Phân quyền theo phân công xuyên suốt REST, WebSocket và email.
- Đạt ngưỡng phi chức năng p95 < 2 giây và chịu được sự cố dừng đột ngột của consumer lẫn backend.

### 5.1.2. Hạn chế

⟨*Nguồn: `docs/report/ghi_chu_bao_cao.md` mục 3.5 — 16 hạn chế, trong đó những mục bắt buộc công khai:*⟩

1. ⟨*Tập kiểm tra của cả hai mô hình đã dùng hai lần; ngưỡng quality gate được hiệu chỉnh sau khi xem kết quả kiểm tra.*⟩
2. ⟨*Recall của mô hình bất thường thấp tại τ = 0,99; bất thường dùng để đánh giá là bất thường tổng hợp, không phải bất thường lâm sàng thật.*⟩
3. ⟨*Thiên lệch chọn mẫu: cả 100 bệnh nhân trong bộ Demo đều đã tử vong về sau; tập kiểm tra chỉ 15 bệnh nhân nên khoảng tin cậy rộng.*⟩
4. ⟨*Nhãn là proxy (NEWS2 rút gọn), không phải chẩn đoán lâm sàng.*⟩
5. ⟨*Streaming là phát lại dữ liệu lịch sử, drift là drift tiêm nhân tạo.*⟩
6. ⟨*Ngưỡng PSI 0,25 thông dụng không dùng được ở quy mô này; ngưỡng hiệu chỉnh chưa được kiểm chứng trên dữ liệu vận hành thật.*⟩
7. ⟨*Retrain trên drift mô phỏng không cải thiện được mô hình; độ trễ chỉ đo với một consumer trên một máy.*⟩

## 5.2. Hướng phát triển

⟨*Nguồn: `docs/report/ghi_chu_bao_cao.md` mục 4.*⟩

- ⟨*Dùng MIMIC-III/IV đầy đủ hoặc eICU (cần hoàn thành CITI và DUA) để có tập kiểm tra lớn hơn và có bệnh nhân sống sót.*⟩
- ⟨*Phát hiện drift theo từng bệnh nhân, hoặc kiểm định có tính đến tương quan trong cùng bệnh nhân, thay cho PSI gộp.*⟩
- ⟨*Mở rộng thông lượng bằng nhiều consumer cùng group và đo lại độ trễ.*⟩
- ⟨*Bổ sung nhãn lâm sàng thật (biến cố chuyển nặng, can thiệp) thay cho nhãn proxy.*⟩
- ⟨*Nâng cấp giao diện và bổ sung theo dõi hiệu năng mô hình theo thời gian trên dữ liệu vận hành.*⟩

\newpage

# TÀI LIỆU THAM KHẢO

⟨*Định dạng theo mẫu: `[n] Tác giả (Năm). Tên bài. Tên tạp chí/hội nghị, trang.` Nguồn nền đã có ở `docs/report/ghi_chu_bao_cao.md` mục 5 — cần bổ sung và kiểm tra lại toàn bộ trước khi nộp. Bắt buộc có: trích dẫn MIMIC-III của Johnson và cộng sự, tài liệu NEWS2 của Royal College of Physicians, tài liệu PSI/drift, tài liệu LSTM-Autoencoder.*⟩

\newpage

# LÀM VIỆC NHÓM

⟨*Bảng phân công công việc giữa các thành viên và tiến độ theo tuần. Nếu đồ án làm một mình thì bỏ mục này (và bỏ khỏi mục lục).*⟩

\newpage

# TỰ ĐÁNH GIÁ

⟨*Tự đánh giá mức độ hoàn thành theo từng yêu cầu của đề bài.*⟩
