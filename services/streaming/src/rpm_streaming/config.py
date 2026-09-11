"""Cấu hình streaming từ biến môi trường (xem .env.example).

Biến đã đặt trong shell được ưu tiên hơn `.env`. Chạy trên host cần:
KAFKA_BOOTSTRAP_SERVERS=localhost:29092, MLFLOW_TRACKING_URI=http://localhost:5000, POSTGRES_HOST=localhost.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_REPLAY_FILE = REPO_ROOT / "ml" / "data" / "processed" / "stream_replay.parquet"


def optional_float(value: str | None) -> float | None:
    return float(value) if value not in (None, "") else None


@dataclass(frozen=True)
class Settings:
    kafka_bootstrap: str
    topic_vitals: str
    topic_predictions: str
    topic_alerts: str
    mlflow_uri: str
    postgres_dsn: str
    seconds_per_data_hour: float
    default_risk_threshold: float | None
    default_anomaly_threshold: float
    default_cooldown_hours: int
    model_refresh_seconds: float
    settings_refresh_seconds: float
    consumer_group: str


def load_settings() -> Settings:
    load_dotenv(REPO_ROOT / ".env", override=False)
    env = os.environ
    dsn = (
        f"host={env.get('POSTGRES_HOST', 'localhost')} port={env.get('POSTGRES_PORT', '5432')} "
        f"dbname={env['POSTGRES_DB']} user={env['POSTGRES_USER']} password={env['POSTGRES_PASSWORD']}"
    )
    return Settings(
        kafka_bootstrap=env.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092"),
        topic_vitals=env.get("KAFKA_TOPIC_VITALS", "vitals-stream"),
        topic_predictions=env.get("KAFKA_TOPIC_PREDICTIONS", "predictions-stream"),
        topic_alerts=env.get("KAFKA_TOPIC_ALERTS", "alerts-stream"),
        mlflow_uri=env.get("MLFLOW_TRACKING_URI", "http://localhost:5000"),
        postgres_dsn=dsn,
        seconds_per_data_hour=float(env.get("REPLAY_SECONDS_PER_DATA_HOUR", "5")),
        default_risk_threshold=optional_float(env.get("DEFAULT_RISK_CRITICAL_THRESHOLD")),
        default_anomaly_threshold=float(env.get("DEFAULT_ANOMALY_THRESHOLD") or 0.99),
        default_cooldown_hours=int(env.get("DEFAULT_ALERT_COOLDOWN_HOURS") or 4),
        model_refresh_seconds=float(env.get("MODEL_REFRESH_SECONDS", "60")),
        settings_refresh_seconds=float(env.get("ALERT_SETTINGS_REFRESH_SECONDS", "30")),
        consumer_group=env.get("KAFKA_CONSUMER_GROUP", "rpm-stream-consumer"),
    )
