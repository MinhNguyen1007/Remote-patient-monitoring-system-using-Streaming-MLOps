"""E2E: sự kiện → WebSocket + Email, đăng nhập + WebSocket — 02_10 mục 2.10.2 dòng 2 và 3 (Sequence 2.4.1, 2.4.2).

Chuỗi thật đầy đủ: producer → consumer → Kafka → Kafka listener của backend → EventDispatcher → WebSocket của
người **được phân công** + email (EMAIL_DELIVERY=log) + notification_logs.
"""

import httpx
import pytest

from helpers import WsClient, wait_until, ws_rejects


@pytest.fixture(scope="module")
def subjects(replay) -> list[int]:
    return replay.take(2, offset=2)


@pytest.fixture(scope="module")
def patients(replay, consumer, db, subjects) -> dict[int, str]:
    """Phát giờ đầu để bệnh nhân có mặt trong DB (phân công cần patient_id)."""
    replay.publish_tick(subjects)
    return {
        subject: wait_until(lambda s=subject: db.patient_id(s), message=f"bệnh nhân {subject}")
        for subject in subjects
    }


def test_login_rejects_wrong_password_and_websocket_rejects_bad_token(api_url, ws_url, make_staff, patients, subjects):
    """2.4.2: đăng nhập sai → 401; WebSocket với token sai/rỗng → bị đóng (1008)."""
    from helpers import Api

    doctor = make_staff("DOCTOR", [patients[subjects[0]]])
    api = Api(api_url)

    with pytest.raises(httpx.HTTPStatusError) as wrong:
        api.login(doctor["email"], "sai-mat-khau")
    assert wrong.value.response.status_code == 401

    session = api.login(doctor["email"], doctor["password"])
    me = session.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["role"] == "DOCTOR"

    assert ws_rejects(ws_url, "khong-phai-jwt")
    assert ws_rejects(ws_url, "")


def test_events_reach_assigned_staff_only(replay, consumer, backend, db, ws_url, api_url, make_staff,
                                          patients, subjects, force_critical, alert_slate):
    """Prediction + alert chỉ tới WebSocket của người được phân công; người không được phân công không nhận gì."""
    from helpers import Api

    watched, other = subjects[0], subjects[1]
    assigned = make_staff("DOCTOR", [patients[watched]])
    unassigned = make_staff("NURSE", [patients[other]])

    api = Api(api_url)
    assigned_ws = WsClient(ws_url, api.login(assigned["email"], assigned["password"]).token)
    unassigned_ws = WsClient(ws_url, api.login(unassigned["email"], unassigned["password"]).token)
    try:
        force_critical()
        seen, hours_needed = alert_slate(patients[watched])
        hours = [m.hour_index for m in replay.publish_hours([watched], hours_needed)]

        prediction = assigned_ws.wait_for(
            lambda e: e["type"] == "prediction" and e["data"]["hour_index"] == hours[0]
        )
        assert prediction["data"]["subject_id"] == watched
        assert prediction["data"]["patient_id"] == str(patients[watched])

        alert = assigned_ws.wait_for(
            lambda e: e["type"] == "alert" and e["data"]["alert_id"] not in seen
        )
        assert alert["data"]["alert_type"] == "RISK"
        assert alert["data"]["subject_id"] == watched
        alert_id = alert["data"]["alert_id"]

        # Người không được phân công: không có sự kiện nào của bệnh nhân này
        for event in unassigned_ws.received():
            assert event["type"] == "connected" or event["data"].get("subject_id") != watched, event

        # Email (EMAIL_DELIVERY=log) chỉ ghi log, nhưng notification_logs phải đúng danh sách người nhận
        logs = wait_until(
            lambda: db.rows("SELECT * FROM notification_logs WHERE alert_id = %s", (alert_id,)) or None,
            message="notification_logs của cảnh báo",
        )
        assert {str(row["recipient_user_id"]) for row in logs} == {assigned["id"]}, \
            "chỉ người được phân công mới nhận email"
        assert {row["status"] for row in logs} == {"SENT"}
        assert {row["channel"] for row in logs} == {"EMAIL"}

        # 2.4.1: bác sĩ xác nhận rồi xử lý cảnh báo qua API → mỗi lần đẩy alert_update cho người cùng phụ trách
        # (payload là AlertOut, khóa `id`)
        session = api.login(assigned["email"], assigned["password"])
        for path, expected in (("acknowledge", "ACKNOWLEDGED"), ("resolve", "RESOLVED")):
            body = {"note": "E2E"} if path == "resolve" else None
            response = session.post(f"/alerts/{alert_id}/{path}", json=body)
            assert response.status_code == 200, response.text
            update = assigned_ws.wait_for(
                lambda e, want=expected: e["type"] == "alert_update"
                and e["data"]["id"] == alert_id
                and e["data"]["status"] == want
            )
            assert update["data"]["patient_id"] == str(patients[watched])
        # Sai thứ tự (đã RESOLVED) → 409
        assert session.post(f"/alerts/{alert_id}/acknowledge").status_code == 409
    finally:
        assigned_ws.close()
        unassigned_ws.close()


def test_unassigned_patient_is_forbidden_over_rest(api_url, make_staff, patients, subjects):
    """Phân quyền theo phân công cũng phải đúng ở REST (UC04–05): bệnh nhân khác → 403."""
    from helpers import Api

    doctor = make_staff("DOCTOR", [patients[subjects[0]]])
    session = Api(api_url).login(doctor["email"], doctor["password"])

    listed = session.get("/patients")
    assert listed.status_code == 200
    assert [p["id"] for p in listed.json()] == [str(patients[subjects[0]])]

    forbidden = session.get(f"/patients/{patients[subjects[1]]}")
    assert forbidden.status_code == 403, forbidden.text
