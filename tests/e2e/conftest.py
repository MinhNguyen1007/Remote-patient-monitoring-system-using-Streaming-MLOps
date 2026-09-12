"""Fixture cho bộ test E2E (Giai đoạn H) — docs/design/02_10 mục 2.10.2 và 2.10.4.

Yêu cầu trước khi chạy (xem README.md cùng thư mục):
  docker compose up -d postgres zookeeper kafka mlflow
  + đã có `risk_classifier@champion` trên MLflow và `ml/data/processed/stream_replay.parquet`.

⚠ Bộ test **xóa dữ liệu phát lại** trong `rpm_db` khi bắt đầu phiên (đúng như `rpm_streaming.storage.reset_demo`:
patients, vital_records, predictions, alerts, notification_logs, patient_assignments). Giữ nguyên users,
model_versions, alert_settings, drift_reports.
"""

import os
import sys
import time
import uuid
from pathlib import Path

import psycopg2
import psycopg2.extras
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import (  # noqa: E402
    Api, KafkaTap, ManagedProcess, Replay, free_port, port_open, seek_group_to_end, wait_until,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON = REPO_ROOT / ".venv" / "Scripts" / ("python.exe" if os.name == "nt" else "python")
if not PYTHON.exists():
    PYTHON = REPO_ROOT / ".venv" / "bin" / "python"
REPLAY_FILE = REPO_ROOT / "ml" / "data" / "processed" / "stream_replay.parquet"

KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092")
MLFLOW_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000")
POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "localhost")
TOPIC_VITALS = os.environ.get("KAFKA_TOPIC_VITALS", "vitals-stream")
TOPIC_PREDICTIONS = os.environ.get("KAFKA_TOPIC_PREDICTIONS", "predictions-stream")
TOPIC_ALERTS = os.environ.get("KAFKA_TOPIC_ALERTS", "alerts-stream")

# Bảng bị xóa đầu phiên — giống rpm_streaming.storage.reset_demo
DEMO_TABLES = ("notification_logs", "alerts", "predictions", "vital_records", "patient_assignments", "patients")

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@rpm.local")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin12345")
STAFF_PASSWORD = "e2e-password-123"


# ------------------------------------------------------------------------------------- hạ tầng & môi trường


@pytest.fixture(scope="session")
def env() -> dict:
    """Biến môi trường chung cho các tiến trình con (host dùng localhost thay cho hostname trong mạng docker)."""
    from dotenv import dotenv_values

    values = {k: v for k, v in dotenv_values(REPO_ROOT / ".env").items() if v is not None}
    values.update(
        POSTGRES_HOST=POSTGRES_HOST,
        KAFKA_BOOTSTRAP_SERVERS=KAFKA_BOOTSTRAP,
        MLFLOW_TRACKING_URI=MLFLOW_URI,
    )
    return values


@pytest.fixture(scope="session", autouse=True)
def infra(env) -> None:
    """Bỏ qua cả bộ test (kèm hướng dẫn) nếu hạ tầng chưa chạy — bộ này không tự dựng docker compose."""
    missing = []
    for label, host, port in (
        ("PostgreSQL", POSTGRES_HOST, int(env.get("POSTGRES_PORT", "5432"))),
        ("Kafka", *KAFKA_BOOTSTRAP.split(":")),
        ("MLflow", MLFLOW_URI.split("//")[1].split(":")[0], int(MLFLOW_URI.rsplit(":", 1)[1])),
    ):
        if not port_open(host, int(port)):
            missing.append(f"{label} ({host}:{port})")
    if missing:
        pytest.skip(
            "chưa chạy: " + ", ".join(missing) + " — cần `docker compose up -d postgres zookeeper kafka mlflow`",
            allow_module_level=True,
        )
    if not REPLAY_FILE.exists():
        pytest.skip(f"thiếu {REPLAY_FILE} — chạy `python -m rpm_ml.data.preprocess` trước", allow_module_level=True)
    if not PYTHON.exists():
        pytest.skip(f"thiếu {PYTHON} — tạo .venv theo README", allow_module_level=True)


@pytest.fixture(scope="session")
def dsn(env) -> str:
    return (
        f"host={POSTGRES_HOST} port={env.get('POSTGRES_PORT', '5432')} dbname={env['POSTGRES_DB']} "
        f"user={env['POSTGRES_USER']} password={env['POSTGRES_PASSWORD']}"
    )


@pytest.fixture(scope="session")
def db(dsn):
    """Kết nối đọc dữ liệu để khẳng định kết quả (autocommit: luôn thấy dữ liệu consumer vừa ghi)."""
    psycopg2.extras.register_uuid()
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    yield Db(conn)
    conn.close()


class Db:
    def __init__(self, conn):
        self.conn = conn

    def rows(self, sql: str, params: tuple = ()) -> list[dict]:
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]

    def one(self, sql: str, params: tuple = ()):
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            return row[0] if row else None

    def execute(self, sql: str, params: tuple = ()) -> None:
        with self.conn.cursor() as cur:
            cur.execute(sql, params)

    def patient_id(self, subject_id: int):
        return self.one("SELECT id FROM patients WHERE mimic_subject_id = %s", (subject_id,))


@pytest.fixture(scope="session", autouse=True)
def clean_demo_data(db, infra) -> None:
    """Xóa dữ liệu phát lại trước khi bắt đầu (consumer chưa chạy ở thời điểm này)."""
    db.execute(f"TRUNCATE {', '.join(DEMO_TABLES)}")


# ------------------------------------------------------------------------------------ tiến trình hệ thống


@pytest.fixture(scope="session")
def session_id() -> str:
    """Hậu tố duy nhất cho mỗi lần chạy bộ test.

    Group Kafka phải mới mỗi phiên: dùng lại group cũ nghĩa là backend/consumer nối tiếp offset của lần chạy trước
    và phải tiêu thụ hết message tồn từ những lần đó trước khi thấy message của phiên này.
    """
    return uuid.uuid4().hex[:8]


@pytest.fixture(scope="session")
def logs_dir() -> Path:
    """Log của tiến trình con; xóa log cũ để các khẳng định dựa trên log chỉ thấy nội dung của phiên này."""
    path = REPO_ROOT / "tests" / "e2e" / ".logs"
    path.mkdir(parents=True, exist_ok=True)
    for old in path.glob("*.log"):
        old.unlink(missing_ok=True)
    return path


@pytest.fixture(scope="session")
def consumer(env, logs_dir, session_id, clean_demo_data) -> ManagedProcess:
    """Stream consumer thật (nạp champion từ MLflow). Làm mới alert_settings/model nhanh hơn mặc định để test ngắn."""
    seek_group_to_end(KAFKA_BOOTSTRAP, f"rpm-stream-consumer-e2e-{session_id}", TOPIC_VITALS)
    process = ManagedProcess(
        name="stream-consumer",
        args=[str(PYTHON), "-m", "rpm_streaming.consumer"],
        cwd=REPO_ROOT,
        env={
            **env,
            "KAFKA_CONSUMER_GROUP": f"rpm-stream-consumer-e2e-{session_id}",
            "ALERT_SETTINGS_REFRESH_SECONDS": "1",
            "MODEL_REFRESH_SECONDS": "5",
        },
        log_path=logs_dir / "stream-consumer.log",
        ready_marker="consumer sẵn sàng",
    )
    process.start(ready_timeout=300)
    yield process
    process.stop()


@pytest.fixture(scope="session")
def backend_port() -> int:
    return free_port()


@pytest.fixture(scope="session")
def backend(env, logs_dir, backend_port, session_id, clean_demo_data) -> ManagedProcess:
    """Backend thật trên cổng riêng (không đụng cổng 8000 của container), group Kafka riêng cho mỗi phiên.

    Group mới bắt đầu từ `latest` (auto.offset.reset của listener) nên không phải tiêu thụ lại sự kiện của những
    phiên trước; trong phiên, group vẫn giữ nguyên qua các lần khởi động lại (test 2.10.4 dòng 2 dựa vào điều đó).
    """
    process = ManagedProcess(
        name="backend",
        args=[str(PYTHON), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(backend_port)],
        cwd=REPO_ROOT / "services" / "backend",
        env={**env, "BACKEND_KAFKA_GROUP": f"rpm-backend-e2e-{session_id}", "EMAIL_DELIVERY": "log"},
        log_path=logs_dir / "backend.log",
        ready_marker="Application startup complete",
    )
    process.start(ready_timeout=180)
    yield process
    process.stop()


@pytest.fixture(scope="session")
def api_url(backend_port) -> str:
    return f"http://127.0.0.1:{backend_port}"


@pytest.fixture(scope="session")
def ws_url(backend_port) -> str:
    return f"ws://127.0.0.1:{backend_port}"


@pytest.fixture(scope="session")
def admin(backend, api_url) -> Api:
    """Đăng nhập Admin (tài khoản được backend seed lúc khởi động)."""
    api = Api(api_url)
    return wait_until(lambda: _try_login(api, ADMIN_EMAIL, ADMIN_PASSWORD), timeout=60, message="đăng nhập Admin")


def _try_login(api: Api, email: str, password: str):
    try:
        return api.login(email, password)
    except Exception:
        return None


# --------------------------------------------------------------------------------------------- phát lại


@pytest.fixture(scope="session")
def replay(consumer) -> Replay:
    """Producer dùng chung; con trỏ giờ chung cả phiên (xem docstring lớp Replay)."""
    return Replay(KAFKA_BOOTSTRAP, TOPIC_VITALS, REPLAY_FILE)


@pytest.fixture
def tap():
    """Đọc trực tiếp các topic do consumer publish; đóng sau mỗi test."""
    taps = []

    def make(topics: list[str]) -> KafkaTap:
        instance = KafkaTap(KAFKA_BOOTSTRAP, topics)
        taps.append(instance)
        return instance

    yield make
    for instance in taps:
        instance.close()


# --------------------------------------------------------------------------------------- tài khoản nhân viên


@pytest.fixture
def make_staff(admin, db):
    """Tạo bác sĩ/điều dưỡng mới (email duy nhất) và phân công bệnh nhân qua API Admin (UC03, UC13)."""
    created = []

    def make(role: str = "DOCTOR", patient_ids: list = ()) -> dict:
        email = f"e2e-{role.lower()}-{uuid.uuid4().hex[:8]}@rpm.local"
        response = admin.post(
            "/users",
            json={"email": email, "full_name": f"E2E {role}", "password": STAFF_PASSWORD, "role": role},
        )
        assert response.status_code in (200, 201), response.text
        user = response.json()
        for patient_id in patient_ids:
            assigned = admin.post("/admin/assignments", json={"user_id": user["id"], "patient_id": str(patient_id)})
            assert assigned.status_code in (200, 201), assigned.text
        created.append(user)
        return {**user, "password": STAFF_PASSWORD}

    yield make
    # Xóa hẳn (không chỉ khóa): mỗi lần chạy tạo tài khoản mới, để lại thì bảng users đầy tài khoản rác.
    # notification_logs và patient_assignments của họ cũng đi theo (ON DELETE CASCADE) — đều là dữ liệu test.
    for user in created:
        db.execute("DELETE FROM patient_assignments WHERE user_id = %s", (user["id"],))
        db.execute("DELETE FROM users WHERE id = %s", (user["id"],))


@pytest.fixture
def force_critical(admin, db):
    """Hạ ngưỡng rủi ro qua API Admin (UC08) để mọi giờ đều thành CRITICAL, rồi trả lại như cũ.

    Cho phép test luồng cảnh báo một cách tất định mà không phải đi tìm giờ thật vượt ngưỡng.
    """
    before = admin.get("/admin/alert-settings")
    assert before.status_code == 200, before.text
    original = before.json()

    def apply(threshold: float = 1e-6) -> None:
        """Ngưỡng phải thuộc (0, 1) theo schema API; 1e-6 nhỏ hơn mọi risk_score thực tế."""
        response = admin.put(
            "/admin/alert-settings",
            json={
                "risk_critical_threshold": threshold,
                "anomaly_threshold": original["anomaly_threshold"],
                "cooldown_hours": original["cooldown_hours"],
            },
        )
        assert response.status_code == 200, response.text
        # Consumer đọc lại alert_settings mỗi ALERT_SETTINGS_REFRESH_SECONDS (đặt 1 giây cho bộ test): chờ để giờ
        # phát ngay sau đây chắc chắn dùng ngưỡng mới.
        time.sleep(3)

    yield apply
    admin.put(
        "/admin/alert-settings",
        json={
            "risk_critical_threshold": original["risk_critical_threshold"],
            "anomaly_threshold": original["anomaly_threshold"],
            "cooldown_hours": original["cooldown_hours"],
        },
    )
    time.sleep(3)  # để test sau không phát giờ đầu tiên khi consumer vẫn còn giữ ngưỡng cũ


@pytest.fixture
def alert_slate(db):
    """Xóa ảnh hưởng của cảnh báo cũ với một bệnh nhân và cho biết cần phát bao nhiêu giờ mới có cảnh báo tiếp theo.

    Consumer chỉ tạo cảnh báo mới khi không còn cảnh báo OPEN cùng loại **và** đã qua cooldown (tính bằng giờ dữ
    liệu). Test nào cần thấy một cảnh báo mới đều phải đi qua đây.
    """

    def prepare(patient_id) -> tuple[set[str], int]:
        db.execute(
            "UPDATE alerts SET status = 'RESOLVED', resolved_at = now() WHERE patient_id = %s AND status <> 'RESOLVED'",
            (patient_id,),
        )
        existing = {str(row["id"]) for row in db.rows("SELECT id FROM alerts WHERE patient_id = %s", (patient_id,))}
        cooldown = db.one("SELECT cooldown_hours FROM alert_settings ORDER BY updated_at DESC LIMIT 1")
        return existing, (cooldown or 0) + 1

    return prepare
