# 1. Giới thiệu và mô tả bài toán

## 1.1. Bối cảnh và động lực

Giám sát bệnh nhân tại các khoa hồi sức tích cực (ICU) hoặc bệnh nhân mãn tính điều trị tại nhà đòi hỏi việc theo dõi liên tục các chỉ số sinh tồn (vital signs) để phát hiện sớm dấu hiệu chuyển biến xấu. Trong thực tế lâm sàng, các thang điểm cảnh báo sớm như NEWS2 (National Early Warning Score) đã được sử dụng để chuẩn hóa việc đánh giá mức độ nguy hiểm dựa trên vitals, nhưng việc tính toán và theo dõi thủ công theo chu kỳ (mỗi vài giờ) không đáp ứng được yêu cầu phát hiện tức thời khi tình trạng bệnh nhân thay đổi nhanh giữa các lần đo.

Sự phát triển của các nền tảng xử lý luồng dữ liệu thời gian thực (streaming) như Apache Kafka và các kỹ thuật MLOps (Machine Learning Operations) cho phép xây dựng một hệ thống giám sát liên tục, tự động: dữ liệu vitals được thu thập liên tục, đưa qua mô hình học máy để đánh giá rủi ro và phát hiện bất thường ngay khi dữ liệu vừa phát sinh, đồng thời hệ thống có khả năng tự giám sát chất lượng mô hình (model drift) và huấn luyện lại khi cần — thay vì một mô hình tĩnh được huấn luyện một lần rồi triển khai mãi mãi.

## 1.2. Phát biểu bài toán

Xây dựng một **hệ thống giám sát bệnh nhân từ xa** có khả năng:

1. Tiếp nhận dữ liệu chỉ số sinh tồn (nhịp tim - HR, độ bão hòa oxy - SpO2, huyết áp tâm thu/tâm trương, nhiệt độ cơ thể, nhịp thở) theo thời gian thực từ nhiều bệnh nhân song song, mô phỏng qua nền tảng streaming (Apache Kafka).
2. Áp dụng mô hình học máy để **dự báo sớm mức độ rủi ro** (bình thường / cảnh báo / nguy kịch) của bệnh nhân trong vài giờ tới, dựa trên lịch sử vitals đến thời điểm hiện tại — thay vì chỉ phân loại tình trạng tức thời.
3. Áp dụng mô hình học sâu để **phát hiện bất thường** (anomaly detection) trong chuỗi thời gian vitals của từng bệnh nhân so với baseline của chính họ.
4. Khi phát hiện rủi ro cao, hệ thống phải **cảnh báo tức thời** tới bác sĩ/điều dưỡng được phân công qua dashboard thời gian thực (WebSocket) và qua email, đồng thời không gửi lặp lại cảnh báo trùng cho cùng một đợt nguy kịch.
5. Cung cấp giao diện web cho bác sĩ/điều dưỡng theo dõi danh sách bệnh nhân được phân công, chi tiết vitals, lịch sử cảnh báo; và cho quản trị viên quản lý người dùng, phân công bệnh nhân, cấu hình ngưỡng cảnh báo và theo dõi chất lượng mô hình.
6. Vận hành theo vòng đời MLOps: theo dõi thực nghiệm và phiên bản mô hình (MLflow), phát hiện data drift, tự động kích hoạt huấn luyện lại (Apache Airflow) hoặc để quản trị viên kích hoạt thủ công, và chỉ thay mô hình đang chạy khi mô hình mới vượt qua quality gate.

## 1.3. Phạm vi đề tài

- **Trong phạm vi**: toàn bộ pipeline từ mô phỏng nguồn dữ liệu (replay dữ liệu ICU thật từ bộ dữ liệu công khai MIMIC-III Clinical Database Demo) → streaming (Kafka) → suy luận mô hình → lưu trữ (PostgreSQL/TimescaleDB) → API & thời gian thực (FastAPI, WebSocket) → giao diện web (React) → vòng lặp MLOps (MLflow, drift detection, Airflow retrain). Triển khai bằng Docker Compose trên môi trường cục bộ.
- **Ngoài phạm vi** (đề cập ở mục Hướng phát triển): triển khai thật lên hạ tầng cloud (AWS/GCP), tích hợp thiết bị IoT y tế thật, các quy định pháp lý về dữ liệu y tế (HIPAA/GDPR) ở mức triển khai sản xuất thực tế.

## 1.4. Đối tượng người dùng

| Vai trò | Mô tả |
|---|---|
| Quản trị viên (Admin) | Quản lý tài khoản người dùng, phân công bệnh nhân cho bác sĩ/điều dưỡng, cấu hình ngưỡng cảnh báo, theo dõi tình trạng mô hình (drift report, phiên bản model), kích hoạt huấn luyện lại |
| Bác sĩ | Theo dõi bệnh nhân được phân công, xem chi tiết vitals/rủi ro, xác nhận và xử lý cảnh báo |
| Điều dưỡng | Theo dõi vitals thời gian thực của bệnh nhân được phân công, nhận cảnh báo; không có quyền xử lý cảnh báo, cấu hình hệ thống hay mô hình |

## 1.5. Ý nghĩa thực tiễn

Đề tài mô phỏng đầy đủ một hệ thống MLOps cấp production thu nhỏ, thể hiện được năng lực thiết kế kiến trúc phần mềm theo hướng thực tế doanh nghiệp: tách bạch giữa luồng dữ liệu thời gian thực và luồng huấn luyện/vận hành mô hình offline, có cơ chế giám sát và tự phục hồi (drift detection → retrain), thay vì một ứng dụng dự đoán đơn thuần không có vòng đời quản lý mô hình.
