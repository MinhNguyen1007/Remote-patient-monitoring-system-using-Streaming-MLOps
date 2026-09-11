"""Cấu hình backend từ biến môi trường (.env.example). Biến đặt trong shell được ưu tiên hơn file .env."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    # --- JWT ---
    backend_secret_key: str = "changeme-generate-a-random-secret"
    backend_jwt_algorithm: str = "HS256"
    backend_access_token_expire_minutes: int = 60
    backend_cors_origins: str = "http://localhost:5173"

    # --- Kafka (Event Listener) ---
    kafka_bootstrap_servers: str = "localhost:29092"
    kafka_topic_predictions: str = "predictions-stream"
    kafka_topic_alerts: str = "alerts-stream"
    # Sự kiện của DAG drift_check / retrain_pipeline (Giai đoạn G)
    kafka_topic_mlops: str = "mlops-events"
    backend_kafka_group: str = "rpm-backend"
    kafka_listener_enabled: bool = True

    # --- Email (UC11) ---
    # "log": chỉ ghi log, không gửi thật (mặc định an toàn khi phát triển); "smtp": gửi qua SMTP
    email_delivery: str = "log"
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    alert_email_from: str = "rpm@example.com"
    frontend_base_url: str = "http://localhost:5173"

    # --- Airflow (UC10) & MLflow (đọc τ_critical của champion) ---
    airflow_api_url: str = "http://localhost:8080/api/v1"
    airflow_www_user: str = "admin"
    airflow_www_password: str = "changeme"
    retrain_dag_id: str = "retrain_pipeline"
    mlflow_tracking_uri: str = "http://localhost:5000"

    # --- Ngưỡng mặc định khi alert_settings chưa có bản ghi (cùng biến consumer dùng để seed) ---
    # Kiểu str vì DEFAULT_RISK_CRITICAL_THRESHOLD để trống nghĩa là "dùng τ của champion"
    default_risk_critical_threshold: str = ""
    default_anomaly_threshold: float = 0.99
    default_alert_cooldown_hours: int = 4

    # --- Tài khoản Admin đầu tiên (seed khi chưa có Admin nào) ---
    admin_email: str = "admin@rpm.local"
    admin_password: str = "admin12345"
    admin_full_name: str = "Quản trị viên"

    @property
    def default_risk_threshold(self) -> float | None:
        return float(self.default_risk_critical_threshold) if self.default_risk_critical_threshold.strip() else None

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
