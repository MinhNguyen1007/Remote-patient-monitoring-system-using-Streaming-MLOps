from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.db.models import RiskLevelEnum
from app.schemas.common import ORMModel


class LatestState(BaseModel):
    """Bản ghi giờ mới nhất: vitals đo được + kết quả dự đoán."""

    recorded_at: datetime
    hour_index: int
    heart_rate: float | None
    spo2: float | None
    respiratory_rate: float | None
    systolic_bp: float | None
    diastolic_bp: float | None
    temperature: float | None
    news2_score: int | None
    risk_level: RiskLevelEnum
    risk_score: float
    anomaly_score: float | None
    is_anomaly: bool | None


class PatientOut(ORMModel):
    id: UUID
    display_name: str
    gender: str | None
    age: int | None
    mimic_subject_id: int
    mimic_icustay_id: int
    admitted_at: datetime


class PatientSummary(PatientOut):
    latest: LatestState | None
    open_alerts: int


class TimelinePoint(LatestState):
    """Một giờ dữ liệu cho biểu đồ vitals, risk-timeline và điểm bất thường (UC05)."""
