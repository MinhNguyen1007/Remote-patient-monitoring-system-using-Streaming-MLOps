# 2. Phân tích - Thiết kế

## Giới thiệu về quy trình thiết kế

Quy trình thiết kế hệ thống được thực hiện theo hướng tiếp cận hướng đối tượng (Object-Oriented Analysis & Design) kết hợp tư duy thiết kế hệ thống dữ liệu lớn theo thời gian thực, gồm các bước tuần tự:

1. **Phân tích yêu cầu chức năng** → xây dựng Sơ đồ chức năng tổng quát (2.1) để xác định các module lớn của hệ thống và luồng tương tác giữa chúng.
2. **Phân tích nghiệp vụ theo góc nhìn người dùng** → xây dựng Biểu đồ Use Case (2.2) để xác định actor và các chức năng mà mỗi actor có thể thực hiện.
3. **Mô hình hóa hành vi nghiệp vụ** → Biểu đồ hoạt động (2.3) mô tả luồng xử lý từng use case quan trọng, và Biểu đồ trình tự (2.4) mô tả tương tác giữa các thành phần kỹ thuật (Kafka, backend, model, DB, dashboard) theo thời gian.
4. **Mô hình hóa cấu trúc dữ liệu và hệ thống** → Biểu đồ lớp (2.5) xác định các entity/class chính và quan hệ giữa chúng ở mức thiết kế phần mềm; Biểu đồ luồng dữ liệu/Database diagram (2.6) và Biểu đồ ER (2.7) xác định cấu trúc lưu trữ vật lý và quan hệ dữ liệu.
5. **Thiết kế giao diện** (2.8) dựa trên các use case và luồng hoạt động đã xác định, đảm bảo mọi chức năng trong Use Case đều có màn hình tương ứng.
6. **Thiết kế giải thuật** (2.9) cho các mô hình học máy/học sâu dùng trong hệ thống, gắn với dữ liệu và luồng xử lý đã thiết kế ở các bước trên.
7. **Thiết kế kiểm thử** (2.10) được xây dựng song song, ánh xạ trực tiếp tới từng chức năng/luồng đã thiết kế để đảm bảo mọi thành phần đều có tiêu chí kiểm tra tương ứng trước khi hiện thực.

Cách tiếp cận "thiết kế trước, hiện thực sau" giúp đảm bảo mã nguồn được viết bám sát kiến trúc đã hoạch định, tránh phát sinh chắp vá giữa chừng — đúng theo quy trình phát triển phần mềm chuẩn trong môi trường doanh nghiệp.

Toàn bộ sơ đồ trong tài liệu được vẽ bằng cú pháp **Mermaid**, dạng văn bản có thể versioning cùng mã nguồn (đặt tại `docs/design/`), sau đó xuất ra hình ảnh để chèn vào báo cáo Word.
