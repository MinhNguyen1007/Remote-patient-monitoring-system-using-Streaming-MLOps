"""02_10 mục 2.10.2 — Sự kiện → WebSocket + Email (mock SMTP), WebSocket từ chối token sai."""

import pytest
from sqlalchemy import select
from starlette.websockets import WebSocketDisconnect

from app.db.models import NotificationLog


class FakeSender:
    def __init__(self, fail_for: set[str] = frozenset()):
        self.sent, self.fail_for = [], fail_for

    def send(self, to, subject, body):
        if to in self.fail_for:
            raise ConnectionError("SMTP từ chối")
        self.sent.append((to, subject, body))


class InlineExecutor:
    """Chạy job email ngay (thay thread pool) để test xác định."""

    def submit(self, fn, *args):
        return fn(*args)

    def shutdown(self, wait=True):
        pass


def use_fakes(client, sender):
    dispatcher = client.app.state.dispatcher
    dispatcher.email_sender, dispatcher.executor = sender, InlineExecutor()
    return dispatcher


def prediction_event(patient) -> dict:
    return {"prediction_id": "p1", "patient_id": str(patient.id), "hour_index": 3, "risk_level": "WARNING",
            "risk_score": 0.2, "news2_score": 5, "anomaly_score": None}


def alert_event(patient, alert) -> dict:
    return {"alert_id": str(alert.id), "patient_id": str(patient.id), "alert_type": "RISK", "status": "OPEN",
            "prediction_recorded_at": alert.prediction_recorded_at.isoformat(), "hour_index": 5, "news2_score": 9,
            "risk_level": "CRITICAL", "risk_score": 0.7, "anomaly_score": None}


def test_websocket_rejects_missing_or_invalid_token(client):
    for url in ("/ws", "/ws?token=bad-token"):
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect(url) as ws:
                ws.receive_json()
        assert exc.value.code == 1008


def test_prediction_reaches_only_assigned_staff(client, make):
    nurse, outsider = make.user("NURSE"), make.user("NURSE")
    patient = make.patient(1)
    make.assign(patient, nurse)
    dispatcher = use_fakes(client, FakeSender())
    with client.websocket_connect(f"/ws?token={make.token(nurse)}") as ws_nurse, \
            client.websocket_connect(f"/ws?token={make.token(outsider)}") as ws_outsider:
        assert ws_nurse.receive_json()["type"] == "connected"
        assert ws_outsider.receive_json()["type"] == "connected"
        delivered = client.portal.call(dispatcher.handle, "prediction", prediction_event(patient))
        assert delivered == 1
        message = ws_nurse.receive_json()
        assert message["type"] == "prediction" and message["data"]["risk_level"] == "WARNING"
        # Người không được phân công không có sự kiện nào đang chờ: tin kế tiếp là pong
        ws_outsider.send_text("ping")
        assert ws_outsider.receive_text() == "pong"


def test_alert_emails_go_to_active_assigned_staff_and_are_logged_once(client, make, db):
    doctor, nurse, locked = make.user("DOCTOR"), make.user("NURSE"), make.user("NURSE", active=False)
    outsider = make.user("DOCTOR")
    patient = make.patient(1)
    for user in (doctor, nurse, locked):
        make.assign(patient, user)
    alert = make.alert(make.record(patient, 5, "CRITICAL", 0.7, news2=9))
    sender = FakeSender(fail_for={nurse.email})
    dispatcher = use_fakes(client, sender)

    client.portal.call(dispatcher.handle, "alert", alert_event(patient, alert))
    assert [to for to, _, _ in sender.sent] == [doctor.email]
    subject, body = sender.sent[0][1], sender.sent[0][2]
    assert "BN-1" in subject and f"/patients/{patient.id}" in body
    logs = {row.recipient_user_id: row.status for row in db.scalars(select(NotificationLog))}
    assert logs == {doctor.id: "SENT", nurse.id: "FAILED"}
    assert outsider.id not in logs and locked.id not in logs

    # Backend đọc lại sự kiện cũ sau khi khởi động lại: không gửi trùng cho người đã nhận
    client.portal.call(dispatcher.handle, "alert", alert_event(patient, alert))
    assert [to for to, _, _ in sender.sent] == [doctor.email]


def test_alert_status_change_is_pushed_to_co_assigned_staff(client, make):
    doctor, nurse = make.user("DOCTOR"), make.user("NURSE")
    patient = make.patient(1)
    make.assign(patient, doctor)
    make.assign(patient, nurse)
    alert = make.alert(make.record(patient, 5, "CRITICAL", 0.7))
    use_fakes(client, FakeSender())
    with client.websocket_connect(f"/ws?token={make.token(nurse)}") as ws:
        ws.receive_json()
        assert client.post(f"/alerts/{alert.id}/acknowledge", headers=make.headers(doctor)).status_code == 200
        message = ws.receive_json()
        assert message["type"] == "alert_update" and message["data"]["status"] == "ACKNOWLEDGED"
