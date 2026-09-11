"""Test backend chạy trên database riêng `rpm_test` trong container PostgreSQL/TimescaleDB (schema tạo bằng Alembic).

Cần `docker compose up -d postgres`; không kết nối được thì bỏ qua toàn bộ test backend.
Biến môi trường phải đặt trước khi import app (engine SQLAlchemy tạo lúc import).
"""

import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ["POSTGRES_DB"] = "rpm_test"
os.environ["KAFKA_LISTENER_ENABLED"] = "false"
os.environ["EMAIL_DELIVERY"] = "log"
os.environ["BACKEND_SECRET_KEY"] = "test-secret-key-that-is-long-enough-for-hs256"
os.environ["ADMIN_EMAIL"] = "admin@test.local"
os.environ["ADMIN_PASSWORD"] = "admin-pass-123"
os.environ["DEFAULT_RISK_CRITICAL_THRESHOLD"] = ""

import psycopg2  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR.parent / ".env", override=False)

TABLES = (
    "notification_logs", "alerts", "predictions", "vital_records", "patient_assignments", "patients",
    "alert_settings", "model_versions", "drift_reports", "users",
)
T0 = datetime(2026, 9, 11, 8, 0, tzinfo=timezone.utc)


def _connect(dbname: str):
    return psycopg2.connect(
        host=os.environ["POSTGRES_HOST"], port=os.environ.get("POSTGRES_PORT", "5432"), dbname=dbname,
        user=os.environ["POSTGRES_USER"], password=os.environ["POSTGRES_PASSWORD"], connect_timeout=3,
    )


@pytest.fixture(scope="session", autouse=True)
def test_database():
    try:
        admin_conn = _connect(os.environ.get("POSTGRES_MAINTENANCE_DB", "postgres"))
    except psycopg2.OperationalError as exc:
        pytest.skip(f"không kết nối được PostgreSQL ({exc}); chạy docker compose up -d postgres")
    admin_conn.autocommit = True
    with admin_conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = 'rpm_test'")
        if cur.fetchone() is None:
            cur.execute("CREATE DATABASE rpm_test")
    admin_conn.close()
    with _connect("rpm_test") as conn, conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")

    from alembic import command
    from alembic.config import Config

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "app" / "alembic"))
    command.upgrade(config, "head")
    yield


@pytest.fixture(autouse=True)
def clean_tables(test_database):
    with _connect("rpm_test") as conn, conn.cursor() as cur:
        cur.execute(f"TRUNCATE {', '.join(TABLES)} CASCADE")
    yield


@pytest.fixture
def client(monkeypatch):
    from fastapi.testclient import TestClient

    import app.api.routers.admin as admin_router
    from app.main import app

    # Không gọi MLflow thật: τ_critical của champion cố định cho test
    monkeypatch.setattr(admin_router, "champion_tau_critical", lambda uri: 0.22)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db():
    from app.db.session import SessionLocal

    with SessionLocal() as session:
        yield session


class Factory:
    """Tạo dữ liệu mẫu trực tiếp trong DB."""

    def __init__(self, db):
        self.db = db
        self._model_version = None

    def user(self, role: str, email: str | None = None, password: str = "password-123", active: bool = True):
        from app.core.security import hash_password
        from app.db.models import RoleEnum, User

        user = User(id=uuid.uuid4(), full_name=f"{role.title()} Test", email=email or f"{uuid.uuid4().hex[:8]}@t.local",
                    password_hash=hash_password(password), role=RoleEnum(role), is_active=active)
        self.db.add(user)
        self.db.commit()
        return user

    def token(self, user) -> str:
        from app.core.security import create_access_token

        return create_access_token(user.id, user.role.value)

    def headers(self, user) -> dict:
        return {"Authorization": f"Bearer {self.token(user)}"}

    def patient(self, subject_id: int):
        from app.db.models import Patient

        patient = Patient(id=uuid.uuid4(), display_name=f"BN-{subject_id}", gender="F", age=70,
                          mimic_subject_id=subject_id, mimic_icustay_id=subject_id * 10)
        self.db.add(patient)
        self.db.commit()
        return patient

    def assign(self, patient, user):
        from app.db.models import PatientAssignment

        self.db.add(PatientAssignment(id=uuid.uuid4(), patient_id=patient.id, user_id=user.id))
        self.db.commit()

    def model_version(self):
        from app.db.models import GateStatusEnum, ModelVersion, TriggerEnum

        if self._model_version is None:
            self._model_version = ModelVersion(
                id=uuid.uuid4(), model_name="risk_classifier", mlflow_version="2", mlflow_run_id="run",
                gate_status=GateStatusEnum.PROMOTED, is_champion=True, trigger=TriggerEnum.INITIAL,
                metrics={"test_macro_f1": 0.623},
            )
            self.db.add(self._model_version)
            self.db.commit()
        return self._model_version

    def record(self, patient, hour: int, risk_level: str = "NORMAL", risk_score: float = 0.1, news2: int | None = 2,
               anomaly_score: float | None = None, heart_rate: float | None = 80.0):
        from app.db.models import Prediction, VitalRecord

        recorded_at = T0 + timedelta(hours=hour)
        self.db.add(VitalRecord(patient_id=patient.id, recorded_at=recorded_at, hour_index=hour, heart_rate=heart_rate,
                                spo2=97.0, respiratory_rate=16.0, systolic_bp=120.0, diastolic_bp=70.0, temperature=37.0))
        prediction = Prediction(
            id=uuid.uuid4(), recorded_at=recorded_at, patient_id=patient.id, predicted_at=recorded_at, news2_score=news2,
            risk_level=risk_level, risk_score=risk_score, anomaly_score=anomaly_score,
            is_anomaly=None if anomaly_score is None else anomaly_score >= 0.99,
            risk_model_version_id=self.model_version().id,
        )
        self.db.add(prediction)
        self.db.commit()
        return prediction

    def alert(self, prediction, alert_type: str = "RISK", status: str = "OPEN"):
        from app.db.models import Alert

        alert = Alert(id=uuid.uuid4(), patient_id=prediction.patient_id, prediction_id=prediction.id,
                      prediction_recorded_at=prediction.recorded_at, alert_type=alert_type, status=status)
        self.db.add(alert)
        self.db.commit()
        return alert


@pytest.fixture
def make(db):
    return Factory(db)
