"""Truy vấn đọc dùng chung cho API (UC04–UC06).

`predictions` và `vital_records` nối theo cặp (patient_id, recorded_at). Một bản ghi vitals có thể có nhiều
prediction khi tái dự đoán bằng model mới (02_5), nên luôn lấy prediction mới nhất theo `predicted_at`.
"""

from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.db.models import Alert, AlertStatusEnum, Patient, Prediction, RiskLevelEnum, VitalRecord
from app.schemas.alerts import AlertOut
from app.schemas.patients import LatestState

VITAL_COLUMNS = ("heart_rate", "spo2", "respiratory_rate", "systolic_bp", "diastolic_bp", "temperature")
# Giới hạn forward-fill (giờ dữ liệu) — phải trùng rpm_common.grid.FFILL_LIMIT_HOURS (có test kiểm tra)
FFILL_LIMIT_HOURS = {"heart_rate": 2, "spo2": 2, "respiratory_rate": 2, "systolic_bp": 2, "diastolic_bp": 2, "temperature": 6}
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
    """Giờ mới nhất của mỗi bệnh nhân. Vitals là giá trị **hiện hành**: giá trị đo gần nhất còn trong giới hạn
    forward-fill (giống giá trị mô hình đang dùng và `vitals_filled` trong sự kiện realtime), không phải chỉ số đo
    đúng giờ đó — giờ không đo sẽ hiện "—" trên dashboard dù vừa đo 1 giờ trước."""
    if not patient_ids:
        return {}
    rows = db.execute(
        select(Prediction, VitalRecord)
        .join(VitalRecord, _JOIN)
        .where(Prediction.patient_id.in_(patient_ids))
        .order_by(Prediction.patient_id, Prediction.recorded_at.desc(), Prediction.predicted_at.desc())
        .distinct(Prediction.patient_id)
    ).all()
    states = {p.patient_id: _state(p, v) for p, v in rows}
    if not states:
        return states
    max_limit = max(FFILL_LIMIT_HOURS.values())
    window = or_(*(
        and_(VitalRecord.patient_id == pid, VitalRecord.hour_index >= state.hour_index - max_limit)
        for pid, state in states.items()
    ))
    recent = db.execute(
        select(VitalRecord).where(window).order_by(VitalRecord.patient_id, VitalRecord.hour_index.desc())
    ).scalars()
    for record in recent:
        state = states[record.patient_id]
        age = state.hour_index - record.hour_index
        if age <= 0 or age > max_limit:
            continue
        for column in VITAL_COLUMNS:
            if getattr(state, column) is None and age <= FFILL_LIMIT_HOURS[column]:
                value = getattr(record, column)
                if value is not None:
                    setattr(state, column, value)
    return states


RECENT_HOURS = 12


def recent_risk_levels(db: Session, patient_ids: list[UUID], hours: int = RECENT_HOURS) -> dict[UUID, list[RiskLevelEnum]]:
    """Mức rủi ro dự báo của `hours` giờ gần nhất mỗi bệnh nhân, sắp cũ → mới."""
    if not patient_ids:
        return {}
    ranked = (
        select(
            Prediction.patient_id,
            Prediction.recorded_at,
            Prediction.risk_level,
            func.row_number()
            .over(partition_by=Prediction.patient_id, order_by=(Prediction.recorded_at.desc(), Prediction.predicted_at.desc()))
            .label("rn"),
        )
        .where(Prediction.patient_id.in_(patient_ids))
        .subquery()
    )
    rows = db.execute(
        select(ranked.c.patient_id, ranked.c.risk_level)
        .where(ranked.c.rn <= hours)
        .order_by(ranked.c.patient_id, ranked.c.recorded_at)
    ).all()
    levels: dict[UUID, list[RiskLevelEnum]] = {}
    for patient_id, level in rows:
        levels.setdefault(patient_id, []).append(level)
    return levels


def news2_components(state: LatestState | None) -> dict[str, int | None] | None:
    """Điểm NEWS2 từng thông số — cùng bảng ngưỡng với pipeline (rpm_common.news2), không tự cài lại."""
    if state is None:
        return None
    from rpm_common.news2 import NEWS2_PARAMS, score_parameter

    result = {}
    for param in NEWS2_PARAMS:
        value = getattr(state, param)
        result[param] = None if value is None else int(score_parameter(param, [value])[0])
    return result


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
