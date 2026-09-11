"""Phân phối sự kiện từ Kafka tới người được phân công — docs/design/02_4 mục 2.4.1.

- `prediction`: đẩy WebSocket tới bác sĩ/điều dưỡng được phân công cho bệnh nhân.
- `alert`: đẩy WebSocket như trên, đồng thời gửi email (thread riêng, không chặn event loop) + ghi notification_logs.
- `alert_update`: khi bác sĩ xác nhận/xử lý cảnh báo qua API, đẩy trạng thái mới cho những người cùng phụ trách.
Admin không theo dõi bệnh nhân nên không nhận sự kiện bệnh nhân.
"""

import asyncio
import logging
from collections.abc import Callable
from concurrent.futures import Executor, ThreadPoolExecutor
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PatientAssignment, RoleEnum, User
from app.services.notification import EmailSender, notify_alert, staff_recipients
from app.services.ws_manager import ConnectionManager

log = logging.getLogger(__name__)

PREDICTION, ALERT, ALERT_UPDATE = "prediction", "alert", "alert_update"


class EventDispatcher:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        manager: ConnectionManager,
        email_sender: EmailSender,
        frontend_base_url: str,
        executor: Executor | None = None,
    ):
        self.session_factory = session_factory
        self.manager = manager
        self.email_sender = email_sender
        self.frontend_base_url = frontend_base_url
        self.executor = executor or ThreadPoolExecutor(max_workers=2, thread_name_prefix="email")

    def assigned_staff(self, patient_id: UUID) -> list[UUID]:
        """Bác sĩ/điều dưỡng đang hoạt động được phân công cho bệnh nhân (đọc mỗi lần để phân công mới có hiệu lực ngay)."""
        with self.session_factory() as db:
            return list(
                db.scalars(
                    select(User.id)
                    .join(PatientAssignment, PatientAssignment.user_id == User.id)
                    .where(
                        PatientAssignment.patient_id == patient_id,
                        User.is_active,
                        User.role.in_([RoleEnum.DOCTOR, RoleEnum.NURSE]),
                    )
                )
            )

    async def handle(self, event_type: str, payload: dict) -> int:
        """Đẩy WebSocket (và gửi email nếu là alert). Trả về số kết nối WebSocket đã nhận."""
        patient_id = UUID(str(payload["patient_id"]))
        user_ids = await asyncio.to_thread(self.assigned_staff, patient_id)
        delivered = await self.manager.send_to_users(user_ids, {"type": event_type, "data": payload})
        if event_type == ALERT and user_ids:
            self.executor.submit(self._send_alert_emails, payload, user_ids)
        return delivered

    def _send_alert_emails(self, payload: dict, user_ids: list[UUID]) -> int:
        try:
            with self.session_factory() as db:
                return notify_alert(
                    db, payload, staff_recipients(db, user_ids), self.email_sender, self.frontend_base_url
                )
        except Exception:
            log.exception("lỗi gửi email cho cảnh báo %s", payload.get("alert_id"))
            return 0
