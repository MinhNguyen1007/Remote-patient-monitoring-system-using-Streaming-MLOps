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
    # Mức rủi ro dự báo của tối đa 12 giờ gần nhất, cũ → mới (dải "rủi ro 12 giờ qua" trên dashboard)
    recent_risk_levels: list[RiskLevelEnum] = []


class PatientDetail(PatientSummary):
    # Điểm NEWS2 (0–3) từng thông số tại giờ mới nhất, tính bằng rpm_common.news2 trên vitals hiện hành
    news2_components: dict[str, int | None] | None = None


class TimelinePoint(LatestState):
    """Một giờ dữ liệu cho biểu đồ vitals, risk-timeline và điểm bất thường (UC05)."""
