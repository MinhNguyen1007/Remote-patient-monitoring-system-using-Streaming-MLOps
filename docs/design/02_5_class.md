# 2.5. Biểu đồ Lớp (Class Diagram)

```mermaid
classDiagram
    class User {
        +UUID id
        +string full_name
        +string email
        +string password_hash
        +RoleEnum role
        +bool is_active
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
        +string display_name
        +string gender
        +int age
        +int mimic_subject_id
        +int mimic_icustay_id
        +datetime admitted_at
    }

    class PatientAssignment {
        +UUID id
        +UUID patient_id
        +UUID user_id
        +UUID assigned_by
        +datetime assigned_at
    }

    class VitalRecord {
        +UUID patient_id
        +datetime recorded_at
        +int hour_index
        +float heart_rate
        +float spo2
        +float respiratory_rate
        +float systolic_bp
        +float diastolic_bp
        +float temperature
    }

    class Prediction {
        +UUID id
        +UUID patient_id
        +datetime recorded_at
        +datetime predicted_at
        +int news2_score
        +RiskLevelEnum risk_level
        +float risk_score
        +float anomaly_score
        +bool is_anomaly
        +UUID risk_model_version_id
        +UUID anomaly_model_version_id
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
        +datetime prediction_recorded_at
        +AlertTypeEnum alert_type
        +AlertStatusEnum status
        +datetime created_at
        +UUID acknowledged_by
        +datetime acknowledged_at
        +UUID resolved_by
        +datetime resolved_at
        +string resolution_note
        +acknowledge(user_id)
        +resolve(user_id, note)
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
        +UUID recipient_user_id
        +string channel
        +datetime sent_at
        +string status
        +string error_message
    }

    class AlertSettings {
        +UUID id
        +float risk_critical_threshold
        +float anomaly_threshold
        +int cooldown_hours
        +UUID updated_by
        +datetime updated_at
    }

    class ModelVersion {
        +UUID id
        +string model_name
        +string mlflow_version
        +string mlflow_run_id
        +GateStatusEnum gate_status
        +bool is_champion
        +TriggerEnum trigger
        +UUID drift_report_id
        +string dag_run_id
        +json metrics
        +datetime trained_at
    }

    class GateStatusEnum {
        <<enumeration>>
        PROMOTED
        REJECTED
    }

    class TriggerEnum {
        <<enumeration>>
        INITIAL
        DRIFT
        MANUAL
    }

    class DriftReport {
        +UUID id
        +datetime run_at
        +datetime window_start
        +datetime window_end
        +int n_records
        +UUID reference_model_version_id
        +float max_psi
        +json feature_stats
        +bool drift_detected
        +bool triggered_retrain
        +string dag_run_id
    }

    User "1" --> "0..*" PatientAssignment : được phân công (Bác sĩ/Điều dưỡng)
    Patient "1" --> "0..*" PatientAssignment : có người phụ trách
    Patient "1" --> "0..*" VitalRecord : có nhiều bản ghi
    VitalRecord "1" --> "0..*" Prediction : sinh ra
    Prediction "1" --> "0..2" Alert : có thể tạo (tối đa 1 mỗi loại)
    Patient "1" --> "0..*" Alert : thuộc về
    User "0..1" <-- "0..*" Alert : xác nhận/xử lý
    Alert "1" --> "0..*" NotificationLog : ghi log gửi
    NotificationLog "0..*" --> "1" User : người nhận
    Prediction "0..*" --> "1" ModelVersion : model rủi ro
    Prediction "0..*" --> "0..1" ModelVersion : model bất thường
    DriftReport "0..*" --> "1" ModelVersion : so với reference của
    DriftReport "0..1" <-- "0..*" ModelVersion : được kích hoạt bởi
    AlertSettings "0..*" --> "0..1" User : cập nhật bởi (Admin)
```

**Ghi chú thiết kế:**
- `Patient` là bệnh nhân **đang được giám sát**. Mỗi `Patient` ứng với 1 bệnh nhân MIMIC thuộc nhóm `stream` (`mimic_subject_id`) và đúng 1 đợt ICU được phát lại (`mimic_icustay_id`), xem mục 2.9.1(g).
  - MIMIC đã phi định danh (không có tên, ngày sinh bị dịch chuyển), nên chỉ lưu `display_name` giả lập (vd `BN-10006`) và `age` tính sẵn.
- `PatientAssignment` là quan hệ nhiều–nhiều giữa bệnh nhân và người dùng có role `DOCTOR` hoặc `NURSE`, do Admin quản lý (UC13). Nó quyết định 3 việc:
  - (1) ai được xem bệnh nhân,
  - (2) ai nhận sự kiện WebSocket,
  - (3) ai nhận email cảnh báo.
- `Prediction` tách khỏi `VitalRecord`, để một bản ghi vitals có thể được **tái dự đoán** khi có model mới mà không sửa dữ liệu gốc.
  - Vì vậy quan hệ là `1 — 0..*`. Luồng chính tạo đúng 1 prediction cho mỗi bản ghi.
  - Mỗi prediction ghi rõ **version của cả 2 model** đã dùng. `anomaly_model_version_id` để trống khi chưa đủ cửa sổ 12 giờ.
- `news2_score` là điểm NEWS2 rút gọn **hiện tại** (tính bằng luật), hiển thị cạnh `risk_level`. `risk_level` là mức rủi ro **dự báo trong h giờ tới** của mô hình học máy (mục 2.9.2).
- `Alert` tách khỏi `Prediction` vì không phải prediction nào cũng sinh cảnh báo. Một prediction có thể sinh tối đa 2 cảnh báo (1 `RISK` và 1 `ANOMALY`) khi cả hai điều kiện cùng xảy ra.
  - Trạng thái: `OPEN → ACKNOWLEDGED` (Bác sĩ đã nhận) → `RESOLVED` (Bác sĩ đã xử lý xong).
- `AlertSettings` lưu các ngưỡng Admin cấu hình (UC08). `risk_critical_threshold` để trống nghĩa là dùng ngưỡng khuyến nghị gắn kèm model champion.
- `ModelVersion` là bản sao metadata của MLflow Model Registry (không lưu trọng số model trong DB nghiệp vụ). Mọi challenger đều được ghi lại kể cả khi bị từ chối (`gate_status = REJECTED`). Mỗi `model_name` có đúng 1 version `is_champion = true`.
- `DriftReport` là **1 lần chạy** kiểm tra drift. PSI/KS chi tiết của từng đặc trưng nằm trong `feature_stats`. Nó tham chiếu version champion có phân phối được dùng làm mốc so sánh. Các version được huấn luyện do lần drift này kích hoạt trỏ ngược lại qua `drift_report_id`.
