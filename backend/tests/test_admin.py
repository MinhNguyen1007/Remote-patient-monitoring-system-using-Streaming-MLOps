"""UC03, UC08, UC09, UC10, UC13 — CRUD của Admin: validate 404/422/409 và retrain qua Airflow (mock HTTP)."""

import uuid

import httpx

from app.core.config import get_settings
from app.services.airflow_client import AirflowClient


def test_user_crud_and_validation(client, make):
    admin = make.user("ADMIN")
    headers = make.headers(admin)
    created = client.post("/users", headers=headers, json={
        "full_name": "BS. Mới", "email": "New@T.local", "password": "long-enough", "role": "DOCTOR"})
    assert created.status_code == 201 and created.json()["email"] == "new@t.local"
    duplicate = {"full_name": "X", "email": "new@t.local", "password": "long-enough", "role": "NURSE"}
    assert client.post("/users", headers=headers, json=duplicate).status_code == 409
    assert client.post("/users", headers=headers, json=duplicate | {"email": "bad"}).status_code == 422
    assert client.post("/users", headers=headers, json=duplicate | {"email": "a@b.co", "password": "short"}).status_code == 422
    assert client.post("/users", headers=headers, json=duplicate | {"email": "a@b.co", "role": "PATIENT"}).status_code == 422

    user_id = created.json()["id"]
    locked = client.patch(f"/users/{user_id}", headers=headers, json={"is_active": False}).json()
    assert locked["is_active"] is False
    assert client.get(f"/users/{uuid.uuid4()}", headers=headers).status_code == 404


def test_admin_cannot_lock_or_demote_self(client, make):
    admin = make.user("ADMIN")
    headers = make.headers(admin)
    assert client.patch(f"/users/{admin.id}", headers=headers, json={"is_active": False}).status_code == 409
    assert client.patch(f"/users/{admin.id}", headers=headers, json={"role": "DOCTOR"}).status_code == 409


def test_assignments_only_for_staff_without_duplicates(client, make):
    admin, doctor, other_admin = make.user("ADMIN"), make.user("DOCTOR"), make.user("ADMIN")
    patient = make.patient(1)
    headers = make.headers(admin)
    body = {"patient_id": str(patient.id), "user_id": str(doctor.id)}
    created = client.post("/admin/assignments", headers=headers, json=body)
    assert created.status_code == 201 and created.json()["user_role"] == "DOCTOR"
    assert client.post("/admin/assignments", headers=headers, json=body).status_code == 409
    assert client.post("/admin/assignments", headers=headers,
                       json=body | {"user_id": str(other_admin.id)}).status_code == 422
    assert client.post("/admin/assignments", headers=headers,
                       json=body | {"patient_id": str(uuid.uuid4())}).status_code == 404

    listing = client.get("/admin/patients", headers=headers).json()
    assert listing[0]["assignments"][0]["user_id"] == str(doctor.id)
    # Sau khi được phân công, bác sĩ thấy bệnh nhân; gỡ phân công thì mất quyền (403)
    assert client.get(f"/patients/{patient.id}", headers=make.headers(doctor)).status_code == 200
    assert client.delete(f"/admin/assignments/{created.json()['id']}", headers=headers).status_code == 204
    assert client.get(f"/patients/{patient.id}", headers=make.headers(doctor)).status_code == 403
    assert client.delete(f"/admin/assignments/{created.json()['id']}", headers=headers).status_code == 404


def test_alert_settings_default_to_champion_tau_and_keep_history(client, make, db):
    admin = make.user("ADMIN")
    headers = make.headers(admin)
    current = client.get("/admin/alert-settings", headers=headers).json()
    assert current["risk_critical_threshold"] is None and current["effective_risk_threshold"] == 0.22
    assert current["anomaly_threshold"] == 0.99 and current["cooldown_hours"] == 4

    updated = client.put("/admin/alert-settings", headers=headers,
                         json={"risk_critical_threshold": 0.3, "anomaly_threshold": 0.995, "cooldown_hours": 6}).json()
    assert updated["effective_risk_threshold"] == 0.3 and updated["updated_by"] == str(admin.id)
    for bad in ({"risk_critical_threshold": 1.5, "anomaly_threshold": 0.99, "cooldown_hours": 4},
                {"anomaly_threshold": 0, "cooldown_hours": 4}, {"anomaly_threshold": 0.99, "cooldown_hours": -1}):
        assert client.put("/admin/alert-settings", headers=headers, json=bad).status_code == 422
    from app.db.models import AlertSettings
    assert db.query(AlertSettings).count() == 1


def test_model_versions_listing(client, make):
    make.model_version()
    body = client.get("/admin/models", headers=make.headers(make.user("ADMIN"))).json()
    assert body[0]["model_name"] == "risk_classifier" and body[0]["is_champion"] is True


def airflow_mock(handler) -> AirflowClient:
    return AirflowClient(get_settings(), transport=httpx.MockTransport(handler))


def test_retrain_returns_202_with_dag_run_id_and_status_is_polled(client, make):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path, request.headers.get("authorization", "")))
        if request.method == "POST":
            return httpx.Response(200, json={"dag_run_id": "manual__1", "state": "queued"})
        return httpx.Response(200, json={"dag_run_id": "manual__1", "state": "running", "start_date": None,
                                          "end_date": None, "conf": {"trigger": "MANUAL"}})

    client.app.state.airflow = airflow_mock(handler)
    try:
        headers = make.headers(make.user("ADMIN"))
        started = client.post("/admin/models/retrain", headers=headers)
        assert started.status_code == 202 and started.json() == {"dag_run_id": "manual__1", "state": "queued"}
        assert client.get("/admin/models/retrain/manual__1", headers=headers).json()["state"] == "running"
        assert calls[0][1].endswith("/dags/retrain_pipeline/dagRuns") and calls[0][2].startswith("Basic ")
    finally:
        client.app.state.airflow = None


def test_retrain_reports_502_when_airflow_fails(client, make):
    client.app.state.airflow = airflow_mock(lambda request: httpx.Response(404, json={"title": "DAG not found"}))
    try:
        response = client.post("/admin/models/retrain", headers=make.headers(make.user("ADMIN")))
        assert response.status_code == 502 and "404" in response.json()["detail"]
    finally:
        client.app.state.airflow = None
