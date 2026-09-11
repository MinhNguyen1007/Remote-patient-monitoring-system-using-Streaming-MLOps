"""UC04 Danh sách bệnh nhân được phân công & mức rủi ro, UC05 chi tiết vitals realtime — Bác sĩ, Điều dưỡng."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import assigned_patient_ids, get_assigned_patient, require_staff
from app.db import queries
from app.db.models import Patient, User
from app.db.session import get_db
from app.schemas.alerts import AlertOut
from app.schemas.patients import PatientOut, PatientSummary, TimelinePoint

router = APIRouter(prefix="/patients", tags=["patients"])


def summaries(db: Session, patients: list[Patient]) -> list[PatientSummary]:
    ids = [p.id for p in patients]
    latest, open_counts = queries.latest_states(db, ids), queries.open_alert_counts(db, ids)
    items = [
        PatientSummary(
            **PatientOut.model_validate(p).model_dump(), latest=latest.get(p.id), open_alerts=open_counts.get(p.id, 0)
        )
        for p in patients
    ]
    # Rủi ro cao nhất lên đầu, cùng mức thì xác suất nguy kịch cao hơn lên trước (02_8)
    return sorted(
        items,
        key=lambda s: (
            queries.RISK_ORDER.get(s.latest.risk_level, 3) if s.latest else 3,
            -(s.latest.risk_score if s.latest else 0.0),
            s.display_name,
        ),
    )


@router.get("", response_model=list[PatientSummary])
def list_patients(db: Session = Depends(get_db), user: User = Depends(require_staff)):
    ids = assigned_patient_ids(db, user)
    patients = db.scalars(select(Patient).where(Patient.id.in_(ids))).all() if ids else []
    return summaries(db, list(patients))


@router.get("/{patient_id}", response_model=PatientSummary)
def get_patient(patient: Patient = Depends(get_assigned_patient), db: Session = Depends(get_db)):
    return summaries(db, [patient])[0]


@router.get("/{patient_id}/timeline", response_model=list[TimelinePoint])
def get_timeline(
    hours: int = Query(default=48, ge=1, le=1000, description="số giờ dữ liệu gần nhất"),
    patient: Patient = Depends(get_assigned_patient),
    db: Session = Depends(get_db),
):
    return [TimelinePoint(**point.model_dump()) for point in queries.timeline(db, patient.id, hours)]


@router.get("/{patient_id}/alerts", response_model=list[AlertOut])
def get_patient_alerts(
    limit: int = Query(default=100, ge=1, le=500),
    patient: Patient = Depends(get_assigned_patient),
    db: Session = Depends(get_db),
):
    return queries.alert_rows(db, [patient.id], limit=limit)
