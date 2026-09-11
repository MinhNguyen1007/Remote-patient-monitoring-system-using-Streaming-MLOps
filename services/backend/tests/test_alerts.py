"""UC06, UC07 — lịch sử cảnh báo và vòng đời OPEN → ACKNOWLEDGED → RESOLVED (02_10 mục 2.10.1)."""


def setup_alert(make, alert_type="RISK"):
    doctor, nurse = make.user("DOCTOR"), make.user("NURSE")
    patient = make.patient(1)
    make.assign(patient, doctor)
    make.assign(patient, nurse)
    alert = make.alert(make.record(patient, 5, "CRITICAL", 0.7, news2=9), alert_type)
    return doctor, nurse, patient, alert


def test_valid_lifecycle_open_acknowledged_resolved(client, make):
    doctor, _, _, alert = setup_alert(make)
    headers = make.headers(doctor)
    acked = client.post(f"/alerts/{alert.id}/acknowledge", headers=headers).json()
    assert acked["status"] == "ACKNOWLEDGED" and acked["acknowledged_by"] == str(doctor.id)
    resolved = client.post(f"/alerts/{alert.id}/resolve", json={"note": "Đã xử trí"}, headers=headers).json()
    assert resolved["status"] == "RESOLVED" and resolved["resolution_note"] == "Đã xử trí"
    assert resolved["hour_index"] == 5 and resolved["risk_level"] == "CRITICAL" and resolved["news2_score"] == 9


def test_invalid_transitions_are_409(client, make):
    doctor, _, _, alert = setup_alert(make)
    headers = make.headers(doctor)
    assert client.post(f"/alerts/{alert.id}/resolve", json={"note": "x"}, headers=headers).status_code == 409
    assert client.post(f"/alerts/{alert.id}/acknowledge", headers=headers).status_code == 200
    assert client.post(f"/alerts/{alert.id}/acknowledge", headers=headers).status_code == 409
    client.post(f"/alerts/{alert.id}/resolve", json={"note": "x"}, headers=headers)
    assert client.post(f"/alerts/{alert.id}/resolve", json={"note": "x"}, headers=headers).status_code == 409


def test_resolve_requires_a_note(client, make):
    doctor, _, _, alert = setup_alert(make)
    client.post(f"/alerts/{alert.id}/acknowledge", headers=make.headers(doctor))
    assert client.post(f"/alerts/{alert.id}/resolve", json={"note": ""}, headers=make.headers(doctor)).status_code == 422


def test_only_assigned_doctor_can_change_status(client, make):
    _, nurse, _, alert = setup_alert(make)
    other_doctor = make.user("DOCTOR")
    assert client.post(f"/alerts/{alert.id}/acknowledge", headers=make.headers(nurse)).status_code == 403
    assert client.post(f"/alerts/{alert.id}/acknowledge", headers=make.headers(other_doctor)).status_code == 403


def test_list_filters_and_open_count_are_scoped_to_assignments(client, make):
    doctor, nurse, patient, risk_alert = setup_alert(make)
    make.alert(make.record(patient, 6, "WARNING", 0.2, anomaly_score=0.995), "ANOMALY")
    other = make.patient(2)
    make.alert(make.record(other, 0, "CRITICAL", 0.9))
    headers = make.headers(nurse)

    assert len(client.get("/alerts", headers=headers).json()) == 2
    anomaly = client.get("/alerts?type=ANOMALY", headers=headers).json()
    assert [a["alert_type"] for a in anomaly] == ["ANOMALY"] and anomaly[0]["anomaly_score"] == 0.995
    assert client.get("/alerts/open-count", headers=headers).json() == {"open": 2}
    client.post(f"/alerts/{risk_alert.id}/acknowledge", headers=make.headers(doctor))
    assert client.get("/alerts?status=OPEN", headers=headers).json()[0]["alert_type"] == "ANOMALY"
    assert client.get("/alerts/open-count", headers=headers).json() == {"open": 1}
    assert client.get(f"/alerts?patient_id={other.id}", headers=headers).status_code == 403
    assert client.get("/alerts?status=DONE", headers=headers).status_code == 422
