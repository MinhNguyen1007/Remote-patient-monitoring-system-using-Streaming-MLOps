"""SQLAlchemy models khớp docs/design/02_5_class.md và 02_7_erd.md.

- `vital_records`, `predictions` là hypertable TimescaleDB (tạo trong migration): khóa chính chứa `recorded_at`.
- Tham chiếu **vào** hypertable (`predictions → vital_records`, `alerts → predictions`) là tham chiếu logic,
  không tạo khóa ngoại; consumer ghi 3 bảng trong cùng một transaction.
- Enum lưu dạng chuỗi kèm CHECK constraint (không dùng kiểu ENUM riêng của PostgreSQL) để migration đơn giản.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class RoleEnum(str, enum.Enum):
    ADMIN = "ADMIN"
    DOCTOR = "DOCTOR"
    NURSE = "NURSE"


class RiskLevelEnum(str, enum.Enum):
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AlertTypeEnum(str, enum.Enum):
    RISK = "RISK"
    ANOMALY = "ANOMALY"


class AlertStatusEnum(str, enum.Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class GateStatusEnum(str, enum.Enum):
    PROMOTED = "PROMOTED"
    REJECTED = "REJECTED"


class TriggerEnum(str, enum.Enum):
    INITIAL = "INITIAL"
    DRIFT = "DRIFT"
    MANUAL = "MANUAL"


def str_enum(enum_class: type[enum.Enum], name: str) -> Enum:
    return Enum(
        enum_class,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=16,
        values_callable=lambda members: [m.value for m in members],
    )


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


TIMESTAMPTZ = DateTime(timezone=True)
JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    full_name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[RoleEnum] = mapped_column(str_enum(RoleEnum, "user_role"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default=func.now())


class Patient(Base):
    """Bệnh nhân đang được giám sát = 1 bệnh nhân MIMIC nhóm `stream` + đúng 1 đợt ICU được phát lại."""

    __tablename__ = "patients"

    id: Mapped[uuid.UUID] = uuid_pk()
    display_name: Mapped[str] = mapped_column(String(100))
    gender: Mapped[str | None] = mapped_column(String(1))
    age: Mapped[int | None] = mapped_column(Integer)
    mimic_subject_id: Mapped[int] = mapped_column(Integer, unique=True)
    mimic_icustay_id: Mapped[int] = mapped_column(Integer, unique=True)
    admitted_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default=func.now())


class PatientAssignment(Base):
    __tablename__ = "patient_assignments"
    __table_args__ = (UniqueConstraint("patient_id", "user_id", name="uq_patient_assignments_patient_user"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"))
    # Role DOCTOR hoặc NURSE — kiểm tra ở tầng ứng dụng
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    assigned_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default=func.now())


class VitalRecord(Base):
    """Giá trị đo theo giờ **như nhận từ producer** (chưa forward-fill; giờ không đo thì để trống).

    Giữ giá trị gốc để consumer dựng lại đặc trưng giống hệt lúc huấn luyện khi khởi động lại.
    """

    __tablename__ = "vital_records"

    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), primary_key=True)
    recorded_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, primary_key=True)
    hour_index: Mapped[int] = mapped_column(Integer)
    heart_rate: Mapped[float | None] = mapped_column(Float)
    spo2: Mapped[float | None] = mapped_column(Float)
    respiratory_rate: Mapped[float | None] = mapped_column(Float)
    systolic_bp: Mapped[float | None] = mapped_column(Float)
    diastolic_bp: Mapped[float | None] = mapped_column(Float)
    temperature: Mapped[float | None] = mapped_column(Float)


class ModelVersion(Base):
    """Bản sao metadata của MLflow Model Registry (không lưu trọng số)."""

    __tablename__ = "model_versions"
    __table_args__ = (UniqueConstraint("model_name", "mlflow_version", name="uq_model_versions_name_version"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    model_name: Mapped[str] = mapped_column(String(64))
    mlflow_version: Mapped[str] = mapped_column(String(16))
    mlflow_run_id: Mapped[str] = mapped_column(String(64))
    gate_status: Mapped[GateStatusEnum] = mapped_column(str_enum(GateStatusEnum, "gate_status"))
    # Lý do bị quality gate từ chối, nối bằng "; " (trống khi đạt) — do DAG retrain_pipeline ghi
    gate_reasons: Mapped[str | None] = mapped_column(Text)
    is_champion: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    trigger: Mapped[TriggerEnum] = mapped_column(str_enum(TriggerEnum, "model_trigger"))
    drift_report_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("drift_reports.id", ondelete="SET NULL", use_alter=True, name="fk_model_versions_drift_report")
    )
    dag_run_id: Mapped[str | None] = mapped_column(String(250))
    metrics: Mapped[dict | None] = mapped_column(JSON_TYPE)
    trained_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)


class DriftReport(Base):
    __tablename__ = "drift_reports"

    id: Mapped[uuid.UUID] = uuid_pk()
    run_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default=func.now())
    window_start: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)
    window_end: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)
    n_records: Mapped[int] = mapped_column(Integer)
    reference_model_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("model_versions.id", ondelete="SET NULL")
    )
    max_psi: Mapped[float | None] = mapped_column(Float)
    feature_stats: Mapped[dict | None] = mapped_column(JSON_TYPE)
    drift_detected: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    triggered_retrain: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    dag_run_id: Mapped[str | None] = mapped_column(String(250))


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (Index("ix_predictions_patient_recorded", "patient_id", "recorded_at"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    recorded_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, primary_key=True)
    # Cùng (patient_id, recorded_at) tham chiếu logic tới vital_records
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"))
    predicted_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default=func.now())
    # Điểm NEWS2 rút gọn hiện tại; trống khi giờ đó chưa đủ 5 thông số
    news2_score: Mapped[int | None] = mapped_column(Integer)
    risk_level: Mapped[RiskLevelEnum] = mapped_column(str_enum(RiskLevelEnum, "risk_level"))
    risk_score: Mapped[float] = mapped_column(Float)
    anomaly_score: Mapped[float | None] = mapped_column(Float)
    is_anomaly: Mapped[bool | None] = mapped_column(Boolean)
    risk_model_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("model_versions.id"))
    anomaly_model_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("model_versions.id"))


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (Index("ix_alerts_patient_type_status", "patient_id", "alert_type", "status"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"))
    # Tham chiếu logic tới predictions (hypertable)
    prediction_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    prediction_recorded_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ)
    alert_type: Mapped[AlertTypeEnum] = mapped_column(str_enum(AlertTypeEnum, "alert_type"))
    status: Mapped[AlertStatusEnum] = mapped_column(
        str_enum(AlertStatusEnum, "alert_status"), default=AlertStatusEnum.OPEN, server_default="OPEN"
    )
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default=func.now())
    acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    acknowledged_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    resolved_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)
    resolution_note: Mapped[str | None] = mapped_column(Text)


class NotificationLog(Base):
    """Log gửi email: cảnh báo tới bác sĩ/điều dưỡng, hoặc thông báo drift tới Admin (đúng 1 trong 2 khóa ngoại)."""

    __tablename__ = "notification_logs"
    __table_args__ = (
        CheckConstraint("(alert_id IS NULL) <> (drift_report_id IS NULL)", name="ck_notification_logs_one_subject"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    alert_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("alerts.id", ondelete="CASCADE"))
    drift_report_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("drift_reports.id", ondelete="CASCADE", name="fk_notification_logs_drift_report")
    )
    recipient_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    channel: Mapped[str] = mapped_column(String(16), default="EMAIL", server_default="EMAIL")
    sent_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default=func.now())
    status: Mapped[str] = mapped_column(String(16))
    error_message: Mapped[str | None] = mapped_column(Text)


class AlertSettings(Base):
    __tablename__ = "alert_settings"

    id: Mapped[uuid.UUID] = uuid_pk()
    # Trống = dùng τ_critical gắn kèm model champion (tag `tau_critical`)
    risk_critical_threshold: Mapped[float | None] = mapped_column(Float)
    anomaly_threshold: Mapped[float] = mapped_column(Float)
    cooldown_hours: Mapped[int] = mapped_column(Integer)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, server_default=func.now())
