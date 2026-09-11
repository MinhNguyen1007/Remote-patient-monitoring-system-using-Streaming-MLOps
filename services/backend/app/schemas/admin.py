from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.db.models import GateStatusEnum, RoleEnum, TriggerEnum
from app.schemas.common import ORMModel
from app.schemas.patients import PatientOut


class AssignmentCreate(BaseModel):
    patient_id: UUID
    user_id: UUID


class AssignmentOut(BaseModel):
    id: UUID
    patient_id: UUID
    user_id: UUID
    user_full_name: str
    user_role: RoleEnum
    assigned_by: UUID | None
    assigned_at: datetime


class AdminPatientOut(PatientOut):
    assignments: list[AssignmentOut]


class AlertSettingsIn(BaseModel):
    # Trống = dùng τ_critical gắn kèm model champion (mục 2.9.6)
    risk_critical_threshold: float | None = Field(default=None, gt=0, lt=1)
    anomaly_threshold: float = Field(gt=0, le=1)
    cooldown_hours: int = Field(ge=0, le=72)


class AlertSettingsOut(BaseModel):
    risk_critical_threshold: float | None
    anomaly_threshold: float
    cooldown_hours: int
    updated_by: UUID | None
    updated_at: datetime | None
    champion_tau_critical: float | None
    effective_risk_threshold: float | None


class ModelVersionOut(ORMModel):
    id: UUID
    model_name: str
    mlflow_version: str
    mlflow_run_id: str
    gate_status: GateStatusEnum
    gate_reasons: str | None = None
    is_champion: bool
    trigger: TriggerEnum
    drift_report_id: UUID | None
    dag_run_id: str | None
    metrics: dict[str, Any] | None
    trained_at: datetime | None


class DriftReportOut(ORMModel):
    id: UUID
    run_at: datetime
    window_start: datetime | None
    window_end: datetime | None
    n_records: int
    reference_model_version_id: UUID | None
    max_psi: float | None
    feature_stats: dict[str, Any] | None
    drift_detected: bool
    triggered_retrain: bool
    dag_run_id: str | None


class RetrainResponse(BaseModel):
    dag_run_id: str
    state: str


class RetrainStatus(BaseModel):
    dag_run_id: str
    state: str
    start_date: datetime | None
    end_date: datetime | None
    conf: dict[str, Any] | None = None
    # Kết quả quality gate của các version do lần chạy này tạo (có khi bước huấn luyện tương ứng xong)
    results: list[ModelVersionOut] = []
