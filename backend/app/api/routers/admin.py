"""Trang quản trị — chỉ Admin: UC13 phân công, UC08 ngưỡng cảnh báo, UC09 giám sát mô hình, UC10 retrain thủ công."""

import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import STAFF_ROLES, require_admin
from app.core.config import get_settings
from app.db.models import AlertSettings, DriftReport, ModelVersion, Patient, PatientAssignment, User
from app.db.session import get_db
from app.schemas.admin import (
    AdminPatientOut,
    AlertSettingsIn,
    AlertSettingsOut,
    AssignmentCreate,
    AssignmentOut,
    DriftReportOut,
    ModelVersionOut,
    RetrainResponse,
    RetrainStatus,
)
from app.schemas.patients import PatientOut
from app.services.airflow_client import AirflowClient, AirflowError
from app.services.mlflow_client import champion_tau_critical

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


# ------------------------------------------------------------------------------------------- UC13 phân công


def assignment_out(assignment: PatientAssignment, user: User) -> AssignmentOut:
    return AssignmentOut(
        id=assignment.id, patient_id=assignment.patient_id, user_id=user.id, user_full_name=user.full_name,
        user_role=user.role, assigned_by=assignment.assigned_by, assigned_at=assignment.assigned_at,
    )


@router.get("/patients", response_model=list[AdminPatientOut])
def list_patients_with_assignments(db: Session = Depends(get_db)):
    patients = db.scalars(select(Patient).order_by(Patient.mimic_subject_id)).all()
    rows = db.execute(select(PatientAssignment, User).join(User, User.id == PatientAssignment.user_id)).all()
    by_patient: dict[UUID, list[AssignmentOut]] = {}
    for assignment, user in rows:
        by_patient.setdefault(assignment.patient_id, []).append(assignment_out(assignment, user))
    return [
        AdminPatientOut(**PatientOut.model_validate(p).model_dump(), assignments=by_patient.get(p.id, []))
        for p in patients
    ]


@router.post("/assignments", response_model=AssignmentOut, status_code=status.HTTP_201_CREATED)
def create_assignment(body: AssignmentCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    if db.get(Patient, body.patient_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy bệnh nhân")
    user = db.get(User, body.user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy người dùng")
    if user.role not in STAFF_ROLES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Chỉ phân công được cho Bác sĩ hoặc Điều dưỡng")
    assignment = PatientAssignment(id=uuid.uuid4(), patient_id=body.patient_id, user_id=user.id, assigned_by=admin.id)
    db.add(assignment)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Người dùng đã được phân công cho bệnh nhân này") from None
    db.refresh(assignment)
    return assignment_out(assignment, user)


@router.delete("/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assignment(assignment_id: UUID, db: Session = Depends(get_db)) -> Response:
    assignment = db.get(PatientAssignment, assignment_id)
    if assignment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy phân công")
    db.delete(assignment)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------------------- UC08 ngưỡng cảnh báo


def settings_out(row: AlertSettings | None, champion_tau: float | None) -> AlertSettingsOut:
    """Chưa có bản ghi nào (consumer chưa chạy lần đầu) thì trả giá trị DEFAULT_* trong .env."""
    defaults = get_settings()
    threshold = row.risk_critical_threshold if row else defaults.default_risk_threshold
    return AlertSettingsOut(
        risk_critical_threshold=threshold,
        anomaly_threshold=row.anomaly_threshold if row else defaults.default_anomaly_threshold,
        cooldown_hours=row.cooldown_hours if row else defaults.default_alert_cooldown_hours,
        updated_by=row.updated_by if row else None,
        updated_at=row.updated_at if row else None,
        champion_tau_critical=champion_tau,
        effective_risk_threshold=threshold if threshold is not None else champion_tau,
    )


@router.get("/alert-settings", response_model=AlertSettingsOut)
def get_alert_settings(db: Session = Depends(get_db)):
    row = db.scalar(select(AlertSettings).order_by(AlertSettings.updated_at.desc()).limit(1))
    return settings_out(row, champion_tau_critical(get_settings().mlflow_tracking_uri))


@router.put("/alert-settings", response_model=AlertSettingsOut)
def update_alert_settings(body: AlertSettingsIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Mỗi lần cập nhật thêm 1 bản ghi (giữ lịch sử); consumer đọc bản ghi mới nhất theo chu kỳ."""
    row = AlertSettings(id=uuid.uuid4(), updated_by=admin.id, **body.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return settings_out(row, champion_tau_critical(get_settings().mlflow_tracking_uri))


# ------------------------------------------------------------------------------- UC09 giám sát mô hình & drift


@router.get("/models", response_model=list[ModelVersionOut])
def list_model_versions(model_name: str | None = None, db: Session = Depends(get_db)):
    query = select(ModelVersion).order_by(ModelVersion.model_name, ModelVersion.trained_at.desc().nullslast())
    if model_name is not None:
        query = query.where(ModelVersion.model_name == model_name)
    return db.scalars(query).all()


@router.get("/drift-reports", response_model=list[DriftReportOut])
def list_drift_reports(limit: int = Query(default=100, ge=1, le=1000), db: Session = Depends(get_db)):
    return db.scalars(select(DriftReport).order_by(DriftReport.run_at.desc()).limit(limit)).all()


# --------------------------------------------------------------------------------- UC10 retrain thủ công


def airflow(request: Request) -> AirflowClient:
    client = getattr(request.app.state, "airflow", None)
    return client if client is not None else AirflowClient(get_settings())


@router.post("/models/retrain", response_model=RetrainResponse, status_code=status.HTTP_202_ACCEPTED)
def trigger_retrain(request: Request, admin: User = Depends(require_admin)) -> RetrainResponse:
    """Trả 202 ngay khi Airflow nhận yêu cầu; giao diện theo dõi bằng GET, không giữ request chờ DAG chạy xong."""
    try:
        run = airflow(request).trigger_retrain({"trigger": "MANUAL", "requested_by": str(admin.id)})
    except AirflowError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from None
    return RetrainResponse(dag_run_id=run["dag_run_id"], state=run.get("state", "queued"))


@router.get("/models/retrain/{dag_run_id}", response_model=RetrainStatus)
def retrain_status(dag_run_id: str, request: Request) -> RetrainStatus:
    try:
        run = airflow(request).get_run(dag_run_id)
    except AirflowError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from None
    return RetrainStatus(
        dag_run_id=run["dag_run_id"], state=run["state"], start_date=run.get("start_date"),
        end_date=run.get("end_date"), conf=run.get("conf"),
    )
