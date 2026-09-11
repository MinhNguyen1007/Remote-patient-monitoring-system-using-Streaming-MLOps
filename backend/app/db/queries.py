"""Truy vấn đọc dùng chung cho API (UC04–UC06).

`predictions` và `vital_records` nối theo cặp (patient_id, recorded_at). Một bản ghi vitals có thể có nhiều
prediction khi tái dự đoán bằng model mới (02_5), nên luôn lấy prediction mới nhất theo `predicted_at`.
"""

from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.db.models import Alert, AlertStatusEnum, Patient, Prediction, RiskLevelEnum, VitalRecord
from app.schemas.alerts import AlertOut
from app.schemas.patients import LatestState

VITAL_COLUMNS = ("heart_rate", "spo2", "respiratory_rate", "systolic_bp", "diastolic_bp", "temperature")
RISK_ORDER = {RiskLevelEnum.CRITICAL: 0, RiskLevelEnum.WARNING: 1, RiskLevelEnum.NORMAL: 2}

_JOIN = and_(VitalRecord.patient_id == Prediction.patient_id, VitalRecord.recorded_at == Prediction.recorded_at)


def _state(prediction: Prediction, vital: VitalRecord) -> LatestState:
    return LatestState(
        recorded_at=prediction.recorded_at,
        hour_index=vital.hour_index,
        **{c: getattr(vital, c) for c in VITAL_COLUMNS},
        news2_score=prediction.news2_score,
        risk_level=prediction.risk_level,
        risk_score=prediction.risk_score,
        anomaly_score=prediction.anomaly_score,
        is_anomaly=prediction.is_anomaly,
    )


def latest_states(db: Session, patient_ids: list[UUID]) -> dict[UUID, LatestState]:
    if not patient_ids:
        return {}
    rows = db.execute(
        select(Prediction, VitalRecord)
        .join(VitalRecord, _JOIN)
        .where(Prediction.patient_id.in_(patient_ids))
        .order_by(Prediction.patient_id, Prediction.recorded_at.desc(), Prediction.predicted_at.desc())
        .distinct(Prediction.patient_id)
    ).all()
    return {p.patient_id: _state(p, v) for p, v in rows}


def open_alert_counts(db: Session, patient_ids: list[UUID]) -> dict[UUID, int]:
    if not patient_ids:
        return {}
    rows = db.execute(
        select(Alert.patient_id, func.count())
        .where(Alert.patient_id.in_(patient_ids), Alert.status == AlertStatusEnum.OPEN)
        .group_by(Alert.patient_id)
    ).all()
    return dict(rows)


def timeline(db: Session, patient_id: UUID, limit: int) -> list[LatestState]:
    """`limit` giờ dữ liệu gần nhất, sắp theo thời gian tăng dần (cho biểu đồ)."""
    rows = db.execute(
        select(Prediction, VitalRecord)
        .join(VitalRecord, _JOIN)
        .where(Prediction.patient_id == patient_id)
        .order_by(Prediction.recorded_at.desc(), Prediction.predicted_at.desc())
        .distinct(Prediction.recorded_at)
        .limit(limit)
    ).all()
    return [_state(p, v) for p, v in reversed(rows)]


def alert_rows(db: Session, patient_ids: list[UUID], status=None, alert_type=None, limit: int = 100, offset: int = 0,
               alert_id: UUID | None = None) -> list[AlertOut]:
    """Cảnh báo kèm thông tin giờ dữ liệu và prediction đã sinh ra nó, mới nhất trước."""
    if not patient_ids:
        return []
    query = (
        select(Alert, Patient.display_name, Prediction, VitalRecord.hour_index)
        .join(Patient, Patient.id == Alert.patient_id)
        .outerjoin(
            Prediction,
            and_(Prediction.id == Alert.prediction_id, Prediction.recorded_at == Alert.prediction_recorded_at),
        )
        .outerjoin(
            VitalRecord,
            and_(VitalRecord.patient_id == Alert.patient_id, VitalRecord.recorded_at == Alert.prediction_recorded_at),
        )
        .where(Alert.patient_id.in_(patient_ids))
        .order_by(Alert.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if status is not None:
        query = query.where(Alert.status == status)
    if alert_type is not None:
        query = query.where(Alert.alert_type == alert_type)
    if alert_id is not None:
        query = query.where(Alert.id == alert_id)
    result = []
    for alert, display_name, prediction, hour_index in db.execute(query).all():
        result.append(
            AlertOut(
                id=alert.id,
                patient_id=alert.patient_id,
                patient_display_name=display_name,
                alert_type=alert.alert_type,
                status=alert.status,
                created_at=alert.created_at,
                prediction_id=alert.prediction_id,
                prediction_recorded_at=alert.prediction_recorded_at,
                hour_index=hour_index,
                news2_score=prediction.news2_score if prediction else None,
                risk_level=prediction.risk_level if prediction else None,
                risk_score=prediction.risk_score if prediction else None,
                anomaly_score=prediction.anomaly_score if prediction else None,
                acknowledged_by=alert.acknowledged_by,
                acknowledged_at=alert.acknowledged_at,
                resolved_by=alert.resolved_by,
                resolved_at=alert.resolved_at,
                resolution_note=alert.resolution_note,
            )
        )
    return result
