"""02_10 mục 2.10.1 — Auth & phân quyền."""

from app.core.security import create_access_token


def test_first_admin_is_seeded_and_can_log_in(client):
    response = client.post("/auth/login", json={"email": "admin@test.local", "password": "admin-pass-123"})
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["role"] == "ADMIN" and body["token_type"] == "bearer" and body["expires_in"] > 0
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.json()["email"] == "admin@test.local"


def test_wrong_password_unknown_email_and_locked_account_all_get_401(client, make):
    make.user("DOCTOR", email="doc@t.local", password="right-pass-1")
    make.user("NURSE", email="locked@t.local", password="right-pass-1", active=False)
    for email, password in [("doc@t.local", "wrong-pass"), ("nobody@t.local", "right-pass-1"), ("locked@t.local", "right-pass-1")]:
        response = client.post("/auth/login", json={"email": email, "password": password})
        assert response.status_code == 401
        assert response.json()["detail"] == "Email hoặc mật khẩu không đúng"


def test_login_email_is_case_insensitive(client, make):
    make.user("DOCTOR", email="doc@t.local", password="right-pass-1")
    assert client.post("/auth/login", json={"email": "DOC@T.local", "password": "right-pass-1"}).status_code == 200


def test_missing_invalid_or_expired_token_is_401(client, make):
    user = make.user("DOCTOR")
    expired = create_access_token(user.id, "DOCTOR", expires_minutes=-1)
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer not-a-jwt"}).status_code == 401
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401


def test_token_of_deactivated_user_stops_working(client, make, db):
    user = make.user("NURSE")
    headers = make.headers(user)
    assert client.get("/auth/me", headers=headers).status_code == 200
    user.is_active = False
    db.commit()
    assert client.get("/auth/me", headers=headers).status_code == 401


def test_role_without_permission_gets_403(client, make):
    nurse, doctor = make.user("NURSE"), make.user("DOCTOR")
    admin = make.user("ADMIN")
    assert client.get("/users", headers=make.headers(nurse)).status_code == 403
    assert client.get("/admin/models", headers=make.headers(doctor)).status_code == 403
    # Admin không theo dõi bệnh nhân (02_2): không xem danh sách bệnh nhân của Bác sĩ/Điều dưỡng
    assert client.get("/patients", headers=make.headers(admin)).status_code == 403


def test_websocket_token_is_redacted_from_server_logs():
    import logging

    from app.main import RedactTokenFilter

    record = logging.LogRecord("uvicorn.error", logging.INFO, __file__, 1, '%s - "WebSocket %s" [accepted]',
                               ("127.0.0.1", "/ws?token=eyJhbGciOi.secret.sig&x=1"), None)
    RedactTokenFilter().filter(record)
    assert "secret" not in record.getMessage() and "token=***&x=1" in record.getMessage()
