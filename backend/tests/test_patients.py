"""UC04, UC05 — chỉ bệnh nhân được phân công; bệnh nhân khác → 403, không tồn tại → 404."""

import uuid


def test_list_shows_only_assigned_patients_sorted_by_risk(client, make):
    nurse = make.user("NURSE")
    low, high, other = make.patient(1), make.patient(2), make.patient(3)
    make.assign(low, nurse)
    make.assign(high, nurse)
    make.record(low, 0, "NORMAL", 0.05)
    make.record(high, 0, "WARNING", 0.10)
    make.record(high, 1, "CRITICAL", 0.60, news2=8)
    make.alert(make.record(other, 0, "CRITICAL", 0.9))

    body = client.get("/patients", headers=make.headers(nurse)).json()
    assert [p["display_name"] for p in body] == ["BN-2", "BN-1"]
    assert body[0]["latest"]["risk_level"] == "CRITICAL" and body[0]["latest"]["hour_index"] == 1
    assert body[0]["latest"]["news2_score"] == 8 and body[0]["open_alerts"] == 0


def test_patient_without_records_has_no_latest_state(client, make):
    doctor = make.user("DOCTOR")
    patient = make.patient(1)
    make.assign(patient, doctor)
    body = client.get(f"/patients/{patient.id}", headers=make.headers(doctor)).json()
    assert body["latest"] is None and body["open_alerts"] == 0


def test_unassigned_patient_is_403_and_unknown_patient_is_404(client, make):
    doctor = make.user("DOCTOR")
    other = make.patient(1)
    headers = make.headers(doctor)
    for suffix in ("", "/timeline", "/alerts"):
        assert client.get(f"/patients/{other.id}{suffix}", headers=headers).status_code == 403
    assert client.get(f"/patients/{uuid.uuid4()}", headers=headers).status_code == 404
    assert client.get("/patients/not-a-uuid", headers=headers).status_code == 422


def test_timeline_returns_last_hours_in_time_order_with_missing_vitals(client, make):
    nurse = make.user("NURSE")
    patient = make.patient(1)
    make.assign(patient, nurse)
    for hour in range(5):
        make.record(patient, hour, heart_rate=None if hour == 3 else 80.0 + hour, anomaly_score=0.5 if hour >= 4 else None)
    body = client.get(f"/patients/{patient.id}/timeline?hours=3", headers=make.headers(nurse)).json()
    assert [p["hour_index"] for p in body] == [2, 3, 4]
    assert body[1]["heart_rate"] is None and body[2]["anomaly_score"] == 0.5
    assert client.get(f"/patients/{patient.id}/timeline?hours=0", headers=make.headers(nurse)).status_code == 422
