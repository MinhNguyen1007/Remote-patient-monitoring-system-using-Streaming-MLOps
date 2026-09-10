# 2.3. Biểu đồ hoạt động (Activity Diagram)

## 2.3.1. Luồng xử lý dữ liệu streaming → cảnh báo (UC12, UC11)

```mermaid
flowchart TD
    Start([Bắt đầu]) --> A[Producer đọc bản ghi vitals tiếp theo của bệnh nhân]
    A --> B[Đẩy message vào Kafka topic vitals-stream]
    B --> C[Consumer nhận message]
    C --> D[Tính feature: rolling mean/std, NEWS2-score thành phần]
    D --> E[Model phân loại rủi ro dự đoán risk_level]
    D --> F[Model LSTM-Autoencoder tính reconstruction error]
    E --> G{risk_level == nguy kịch<br/>HOẶC anomaly_score > ngưỡng?}
    F --> G
    G -- Không --> H[Lưu kết quả vào DB]
    G -- Có --> I[Tạo bản ghi Alert, lưu vào DB]
    I --> J[Đẩy Alert qua WebSocket tới Dashboard]
    I --> K[Gửi email cảnh báo tới bác sĩ/điều dưỡng phụ trách]
    J --> L([Kết thúc])
    K --> L
    H --> L
```

## 2.3.2. Luồng đăng nhập (UC01)

```mermaid
flowchart TD
    Start([Bắt đầu]) --> A[Người dùng nhập email/mật khẩu]
    A --> B[Backend kiểm tra thông tin đăng nhập]
    B --> C{Hợp lệ?}
    C -- Không --> D[Trả lỗi, yêu cầu nhập lại]
    D --> A
    C -- Có --> E[Sinh JWT token kèm role]
    E --> F[Trả token về client, lưu phiên đăng nhập]
    F --> G[Điều hướng vào Dashboard theo đúng quyền của role]
    G --> End([Kết thúc])
```

## 2.3.3. Luồng phát hiện drift → huấn luyện lại (UC09, UC10)

```mermaid
flowchart TD
    Start([Bắt đầu - chạy định kỳ/kích hoạt thủ công]) --> A[Lấy mẫu dữ liệu streaming gần nhất từ DB]
    A --> B[So sánh phân phối feature hiện tại với phân phối lúc train bằng PSI/KS-test]
    B --> C{Vượt ngưỡng drift?}
    C -- Không --> D[Ghi log: không phát hiện drift]
    D --> End1([Kết thúc])
    C -- Có --> E[Tạo Drift Report, cảnh báo Admin]
    E --> F{Admin xác nhận kích hoạt retrain?}
    F -- Không --> End2([Kết thúc, chỉ lưu report])
    F -- Có --> G[Airflow DAG trigger: chạy lại training pipeline]
    G --> H[Huấn luyện model mới trên dữ liệu cập nhật]
    H --> I[Đánh giá model mới trên tập validation]
    I --> J{Chất lượng model mới >= model hiện tại?}
    J -- Không --> K[Giữ nguyên model cũ, ghi log lý do từ chối]
    K --> End3([Kết thúc])
    J -- Có --> L[Đăng ký phiên bản mới vào MLflow Registry, gắn nhãn Production]
    L --> M[Service suy luận nạp model mới]
    M --> End4([Kết thúc])
```
