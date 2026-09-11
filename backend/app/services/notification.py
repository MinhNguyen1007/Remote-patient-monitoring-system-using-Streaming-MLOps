"""Gửi email cảnh báo (UC11) tới bác sĩ/điều dưỡng được phân công và ghi notification_logs.

Backend là nơi duy nhất gửi email. Chạy trong thread riêng (không chặn event loop). Nếu đã có log SENT cho cặp
(alert, người nhận) thì bỏ qua, để khi backend đọc lại sự kiện cũ sau khi khởi động lại không gửi trùng.
"""

import logging
import smtplib
import uuid
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import NotificationLog, Patient, User

log = logging.getLogger(__name__)

TYPE_LABELS = {"RISK": "Nguy cơ nguy kịch trong 4 giờ tới", "ANOMALY": "Diễn biến bất thường so với baseline"}


class EmailSender(Protocol):
    def send(self, to: str, subject: str, body: str) -> None: ...


class LogEmailSender:
    """EMAIL_DELIVERY=log: chỉ ghi log (mặc định khi phát triển, tránh gửi email thật ngoài ý muốn)."""

    def send(self, to: str, subject: str, body: str) -> None:
        log.info("[email:log] tới %s — %s", to, subject)


class SmtpEmailSender:
    def __init__(self, settings: Settings):
        self.settings = settings

    def send(self, to: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"] = self.settings.alert_email_from
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=15) as smtp:
            smtp.starttls()
            if self.settings.smtp_user:
                smtp.login(self.settings.smtp_user, self.settings.smtp_password)
            smtp.send_message(message)


def make_email_sender(settings: Settings) -> EmailSender:
    return SmtpEmailSender(settings) if settings.email_delivery == "smtp" else LogEmailSender()


@dataclass(frozen=True)
class Recipient:
    user_id: UUID
    email: str
    full_name: str


def staff_recipients(db: Session, user_ids) -> list[Recipient]:
    users = db.scalars(select(User).where(User.id.in_(list(user_ids)), User.is_active)).all()
    return [Recipient(u.id, u.email, u.full_name) for u in users]


def compose_alert_email(event: dict, patient: Patient, frontend_base_url: str) -> tuple[str, str]:
    label = TYPE_LABELS.get(event["alert_type"], event["alert_type"])
    subject = f"[RPM] {event['alert_type']} — {patient.display_name}: {label}"
    risk_score = event.get("risk_score")
    lines = [
        f"Bệnh nhân: {patient.display_name} (mã MIMIC {patient.mimic_subject_id})",
        f"Loại cảnh báo: {label}",
        f"Thời điểm: {event['prediction_recorded_at']} (giờ dữ liệu thứ {event.get('hour_index')})",
        f"NEWS2 hiện tại: {event.get('news2_score')}",
        f"Mức rủi ro dự báo: {event.get('risk_level')}"
        + ("" if risk_score is None else f" (xác suất nguy kịch {risk_score:.2f})"),
    ]
    if event.get("anomaly_score") is not None:
        lines.append(f"Điểm bất thường: {event['anomaly_score']:.3f}")
    lines += ["", f"Mở chi tiết bệnh nhân: {frontend_base_url.rstrip('/')}/patients/{patient.id}"]
    return subject, "\n".join(lines)


def notify_alert(db: Session, event: dict, recipients: list[Recipient], sender: EmailSender, frontend_base_url: str) -> int:
    """Gửi email cho từng người nhận chưa có log SENT; trả về số email gửi thành công."""
    alert_id = UUID(event["alert_id"])
    patient = db.get(Patient, UUID(event["patient_id"]))
    if patient is None:
        return 0
    already_sent = set(
        db.scalars(
            select(NotificationLog.recipient_user_id).where(
                NotificationLog.alert_id == alert_id, NotificationLog.status == "SENT"
            )
        )
    )
    subject, body = compose_alert_email(event, patient, frontend_base_url)
    sent = 0
    for recipient in recipients:
        if recipient.user_id in already_sent:
            continue
        try:
            sender.send(recipient.email, subject, body)
            status, error = "SENT", None
            sent += 1
        except Exception as exc:  # lỗi SMTP không được làm dừng listener
            status, error = "FAILED", str(exc)[:1000]
            log.warning("gửi email tới %s thất bại: %s", recipient.email, exc)
        db.add(
            NotificationLog(
                id=uuid.uuid4(), alert_id=alert_id, recipient_user_id=recipient.user_id,
                channel="EMAIL", status=status, error_message=error,
            )
        )
    db.commit()
    return sent
