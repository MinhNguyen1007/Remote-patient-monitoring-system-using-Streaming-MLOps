# 2.5. Biểu đồ Lớp (Class Diagram)

```mermaid
classDiagram
    class User {
        +UUID id
        +string full_name
        +string email
        +string password_hash
        +RoleEnum role
        +datetime created_at
        +verifyPassword(plain) bool
    }

    class RoleEnum {
        <<enumeration>>
        ADMIN
        DOCTOR
        NURSE
    }

    class Patient {
        +UUID id
        +string full_name
        +date dob
        +string gender
        +datetime admitted_at
        +UUID assigned_doctor_id
    }

    class VitalRecord {
        +UUID id
        +UUID patient_id
        +datetime recorded_at
        +float heart_rate
        +float spo2
        +float systolic_bp
        +float diastolic_bp
        +float temperature
        +float respiratory_rate
    }

    class Prediction {
        +UUID id
        +UUID vital_record_id
        +RiskLevelEnum risk_level
        +float risk_score
        +float anomaly_score
        +string model_version
        +datetime predicted_at
    }

    class RiskLevelEnum {
        <<enumeration>>
        NORMAL
        WARNING
        CRITICAL
    }

    class Alert {
        +UUID id
        +UUID patient_id
        +UUID prediction_id
        +AlertTypeEnum alert_type
        +AlertStatusEnum status
        +datetime created_at
        +UUID acknowledged_by
        +datetime acknowledged_at
        +acknowledge(user_id)
    }

    class AlertTypeEnum {
        <<enumeration>>
        RISK
        ANOMALY
    }

    class AlertStatusEnum {
        <<enumeration>>
        OPEN
        ACKNOWLEDGED
        RESOLVED
    }

    class NotificationLog {
        +UUID id
        +UUID alert_id
        +string channel
        +datetime sent_at
        +string status
    }

    class ModelVersion {
        +UUID id
        +string name
        +string version
        +string stage
        +json metrics
        +datetime trained_at
        +string mlflow_run_id
    }

    class DriftReport {
        +UUID id
        +string feature_name
        +float psi_score
        +datetime detected_at
        +bool triggered_retrain
    }

    User "1" --> "0..*" Patient : phụ trách (Bác sĩ)
    Patient "1" --> "*" VitalRecord : có nhiều bản ghi
    VitalRecord "1" --> "0..1" Prediction : sinh ra
    Prediction "1" --> "0..1" Alert : có thể tạo
    Alert "1" --> "*" NotificationLog : ghi log gửi
    User "1" --> "*" Alert : xác nhận (acknowledged_by)
    Prediction "*" --> "1" ModelVersion : dùng model version
    DriftReport ..> ModelVersion : kích hoạt tạo mới
```

**Ghi chú thiết kế:**
- `Prediction` tách khỏi `VitalRecord` để một bản ghi vitals có thể được tái dự đoán khi có model mới mà không cần sửa dữ liệu gốc.
- `Alert` tách khỏi `Prediction` vì không phải mọi prediction đều sinh alert (chỉ khi vượt ngưỡng); quan hệ 0..1 phản ánh đúng điều này (khớp với activity diagram 2.3.1).
- `ModelVersion` ánh xạ trực tiếp tới MLflow Model Registry (không lưu trọng số model trong DB nghiệp vụ, chỉ lưu metadata tham chiếu) — tách biệt hạ tầng lưu trữ model khỏi DB nghiệp vụ.
