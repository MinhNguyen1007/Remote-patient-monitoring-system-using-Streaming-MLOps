from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.db.models import AlertStatusEnum, AlertTypeEnum, RiskLevelEnum


class AlertOut(BaseModel):
    id: UUID
    patient_id: UUID
    patient_display_name: str
    alert_type: AlertTypeEnum
    status: AlertStatusEnum
    created_at: datetime
    prediction_id: UUID
    prediction_recorded_at: datetime
    hour_index: int | None
    news2_score: int | None
    risk_level: RiskLevelEnum | None
    risk_score: float | None
    anomaly_score: float | None
    acknowledged_by: UUID | None
    acknowledged_at: datetime | None
    resolved_by: UUID | None
    resolved_at: datetime | None
    resolution_note: str | None


class ResolveRequest(BaseModel):
    note: str = Field(min_length=1, max_length=2000)


class OpenAlertCount(BaseModel):
    open: int
