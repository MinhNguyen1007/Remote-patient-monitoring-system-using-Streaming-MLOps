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


# ------------------------------------------------------------------ Giai đoạn G: sự kiện MLOps (topic mlops-events)


def drift_report(db, drift_detected=True):
    import uuid

    from app.db.models import DriftReport

    report = DriftReport(id=uuid.uuid4(), n_records=446, max_psi=0.82, drift_detected=drift_detected,
                         feature_stats={"spo2": {"psi": 0.82, "threshold": 0.745, "drifted": True}})
    db.add(report)
    db.commit()
    return report


def drift_event(report, notify=True, triggered=True) -> dict:
    return {"type": "drift_report", "drift_report_id": str(report.id), "n_records": 446, "max_psi": 0.82,
            "drift_detected": True, "drifted_features": ["spo2"], "feature_psi": {"spo2": 0.82},
            "thresholds": {"spo2": 0.745}, "triggered_retrain": triggered, "retrain_dag_run_id": "drift__1",
            "retrain_blocked_reason": None, "notify_admin": notify}


def test_drift_event_reaches_only_admins_and_emails_active_admins_once(client, make, db):
    admin, locked_admin, doctor = make.user("ADMIN"), make.user("ADMIN", active=False), make.user("DOCTOR")
    report = drift_report(db)
    sender = FakeSender()
    dispatcher = use_fakes(client, sender)
    with client.websocket_connect(f"/ws?token={make.token(admin)}") as ws_admin, \
            client.websocket_connect(f"/ws?token={make.token(doctor)}") as ws_doctor:
        ws_admin.receive_json(), ws_doctor.receive_json()
        assert client.portal.call(dispatcher.handle, "mlops", drift_event(report)) == 1
        message = ws_admin.receive_json()
        assert message["type"] == "drift_report" and message["data"]["drifted_features"] == ["spo2"]
        ws_doctor.send_text("ping")
        assert ws_doctor.receive_text() == "pong"

    # Mọi Admin đang hoạt động (gồm Admin seed lúc khởi động app), không gửi tài khoản bị khóa hay bác sĩ
    recipients = {to for to, _, _ in sender.sent}
    assert admin.email in recipients and len(recipients) == len(sender.sent) == 2
    assert locked_admin.email not in recipients and doctor.email not in recipients
    subject, body = sender.sent[0][1], sender.sent[0][2]
    assert "spo2" in subject and "drift__1" in body and "/admin/models" in body
    logs = db.scalars(select(NotificationLog)).all()
    assert {(row.drift_report_id, row.alert_id, row.status) for row in logs} == {(report.id, None, "SENT")}
    assert admin.id in {row.recipient_user_id for row in logs} and len(logs) == 2

    # Đọc lại sự kiện cũ (backend khởi động lại) không gửi trùng
    client.portal.call(dispatcher.handle, "mlops", drift_event(report))
    assert len(sender.sent) == 2


def test_continuing_drift_without_notify_flag_sends_no_email(client, make, db):
    make.user("ADMIN")
    sender = FakeSender()
    dispatcher = use_fakes(client, sender)
    client.portal.call(dispatcher.handle, "mlops", drift_event(drift_report(db), notify=False, triggered=False))
    assert sender.sent == []


def test_retrain_completed_is_pushed_to_admins_without_email(client, make):
    admin = make.user("ADMIN")
    sender = FakeSender()
    dispatcher = use_fakes(client, sender)
    event = {"type": "retrain_completed", "dag_run_id": "manual__1", "trigger": "MANUAL",
             "results": [{"model_name": "risk_classifier", "status": "REJECTED", "version": "5"}]}
    with client.websocket_connect(f"/ws?token={make.token(admin)}") as ws:
        ws.receive_json()
        assert client.portal.call(dispatcher.handle, "mlops", event) == 1
        assert ws.receive_json()["type"] == "retrain_completed"
    assert sender.sent == []
    assert client.portal.call(dispatcher.handle, "mlops", {"type": "unknown"}) == 0
