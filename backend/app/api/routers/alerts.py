"""UC06 Lịch sử cảnh báo (Bác sĩ, Điều dưỡng) và UC07 Xác nhận/xử lý cảnh báo (chỉ Bác sĩ).

Vòng đời: OPEN → ACKNOWLEDGED (bác sĩ đã nhận) → RESOLVED (đã xử lý, kèm ghi chú). Chuyển trạng thái sai thứ tự → 409.
Sau mỗi lần chuyển, trạng thái mới được đẩy qua WebSocket tới mọi người cùng phụ trách bệnh nhân.
"""

from datetime import datetime, timezone
from uuid import UUID

from anyio.from_thread import run as run_in_event_loop
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import assigned_patient_ids, require_doctor, require_staff
from app.db import queries
from app.db.models import Alert, AlertStatusEnum, AlertTypeEnum, User
from app.db.session import get_db
from app.events.dispatcher import ALERT_UPDATE
from app.schemas.alerts import AlertOut, OpenAlertCount, ResolveRequest

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut])
def list_alerts(
    status_filter: AlertStatusEnum | None = Query(default=None, alias="status"),
    alert_type: AlertTypeEnum | None = Query(default=None, alias="type"),
    patient_id: UUID | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
):
    ids = assigned_patient_ids(db, user)
    if patient_id is not None:
        if patient_id not in ids:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Bệnh nhân không được phân công cho bạn")
        ids = [patient_id]
    return queries.alert_rows(db, ids, status_filter, alert_type, limit, offset)


@router.get("/open-count", response_model=OpenAlertCount)
def open_count(db: Session = Depends(get_db), user: User = Depends(require_staff)) -> OpenAlertCount:
    """Số cảnh báo đang mở của các bệnh nhân được phân công (badge trên sidebar)."""
    ids = assigned_patient_ids(db, user)
    count = db.scalar(
        select(func.count()).select_from(Alert).where(Alert.patient_id.in_(ids), Alert.status == AlertStatusEnum.OPEN)
    ) if ids else 0
    return OpenAlertCount(open=count or 0)


def assigned_alert(db: Session, alert_id: UUID, user: User) -> Alert:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy cảnh báo")
    if alert.patient_id not in assigned_patient_ids(db, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Bệnh nhân không được phân công cho bạn")
    return alert


def publish_update(request: Request, db: Session, alert: Alert) -> AlertOut:
    """Trả trạng thái mới và đẩy qua WebSocket tới người cùng phụ trách (endpoint đồng bộ chạy trong worker thread)."""
    out = queries.alert_rows(db, [alert.patient_id], alert_id=alert.id)[0]
    dispatcher = getattr(request.app.state, "dispatcher", None)
    if dispatcher is not None:
        run_in_event_loop(dispatcher.handle, ALERT_UPDATE, out.model_dump(mode="json"))
    return out


@router.post("/{alert_id}/acknowledge", response_model=AlertOut)
def acknowledge(alert_id: UUID, request: Request, db: Session = Depends(get_db), user: User = Depends(require_doctor)):
    alert = assigned_alert(db, alert_id, user)
    if alert.status != AlertStatusEnum.OPEN:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Chỉ xác nhận được cảnh báo OPEN (hiện tại: {alert.status.value})")
    alert.status, alert.acknowledged_by, alert.acknowledged_at = AlertStatusEnum.ACKNOWLEDGED, user.id, datetime.now(timezone.utc)
    db.commit()
    return publish_update(request, db, alert)


@router.post("/{alert_id}/resolve", response_model=AlertOut)
def resolve(alert_id: UUID, body: ResolveRequest, request: Request, db: Session = Depends(get_db),
            user: User = Depends(require_doctor)):
    alert = assigned_alert(db, alert_id, user)
    if alert.status != AlertStatusEnum.ACKNOWLEDGED:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Phải xác nhận trước khi xử lý (hiện tại: {alert.status.value})"
        )
    alert.status, alert.resolved_by, alert.resolved_at = AlertStatusEnum.RESOLVED, user.id, datetime.now(timezone.utc)
    alert.resolution_note = body.note
    db.commit()
    return publish_update(request, db, alert)
