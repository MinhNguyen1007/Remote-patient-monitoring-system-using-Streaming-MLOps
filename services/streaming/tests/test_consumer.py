import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import numpy as np
import pytest

from rpm_streaming.consumer.alerting import AlertHistory
from rpm_streaming.config import Settings
from rpm_streaming.consumer.main import StreamProcessor
from rpm_streaming.kafka.messages import VitalsMessage
from rpm_streaming.consumer.model_service import ANOMALY_MODEL, RISK_MODEL, LoadedModel
from rpm_streaming.storage.repository import AlertSettingsRow
from rpm_common.features import RISK_FEATURE_COLUMNS
from rpm_common.itemids import VITALS

T0 = datetime(2026, 9, 11, tzinfo=timezone.utc)
NORMAL = {"heart_rate": 75.0, "spo2": 98.0, "respiratory_rate": 16.0, "systolic_bp": 120.0, "diastolic_bp": 70.0,
          "temperature": 37.0}
CRITICAL = {"heart_rate": 135.0, "spo2": 90.0, "respiratory_rate": 26.0, "systolic_bp": 88.0, "diastolic_bp": 50.0,
            "temperature": 39.5}
SETTINGS = Settings(
    kafka_bootstrap="", topic_vitals="vitals", topic_predictions="predictions", topic_alerts="alerts",
    mlflow_uri="", postgres_dsn="", seconds_per_data_hour=0, default_risk_threshold=None,
    default_anomaly_threshold=0.99, default_cooldown_hours=4, model_refresh_seconds=60,
    settings_refresh_seconds=30, consumer_group="test",
)


class FakeRepo:
    """Mô phỏng các bảng mà consumer dùng, với cùng ngữ nghĩa truy vấn như Repository."""

    def __init__(self):
        self.patients, self.vitals, self.predictions, self.alerts = {}, [], [], []
        self.fail_next_save = False

    def upsert_patient(self, subject_id, icustay_id, age, gender):
        return self.patients.setdefault(subject_id, uuid4())

    def load_vitals(self, patient_id):
        return [v for v in self.vitals if v["patient_id"] == patient_id]

    def alert_settings(self, defaults):
        return defaults

    def alert_history(self, patient_id):
        history = {}
        for alert_type in ("RISK", "ANOMALY"):
            rows = [a for a in self.alerts if a["patient_id"] == patient_id and a["alert_type"] == alert_type]
            if rows:
                hours = [v["hour_index"] for v in self.vitals for a in rows if v["recorded_at"] == a["prediction_recorded_at"]]
                history[alert_type] = AlertHistory(any(a["status"] == "OPEN" for a in rows), max(hours))
        return history

    def save_hour(self, vital, prediction, alerts):
        if self.fail_next_save:
            self.fail_next_save = False
            raise RuntimeError("DB tạm thời lỗi")
        self.vitals.append(vital)
        self.predictions.append(prediction)
        self.alerts.extend(a | {"status": "OPEN"} for a in alerts)


class NewsRisk:
    """Model rủi ro giả: CRITICAL khi NEWS2 hiện tại ≥ 7."""

    feature_names_in_ = np.array(RISK_FEATURE_COLUMNS)

    def predict_proba(self, X):
        critical = float(X["news2_score"].iloc[0] >= 7)
        return np.array([[1 - critical, 0.0, critical]])


def make_processor(anomaly_score=None):
    models = SimpleNamespace(
        risk=LoadedModel(RISK_MODEL, "2", uuid4(), NewsRisk(), tau_critical=0.5),
        anomaly=None if anomaly_score is None else LoadedModel(
            ANOMALY_MODEL, "2", uuid4(), SimpleNamespace(predict=lambda w: np.array([anomaly_score]))
        ),
    )
    published = []
    repo = FakeRepo()
    processor = StreamProcessor(repo, models, lambda t, k, v: published.append((t, k, json.loads(v))), SETTINGS)
    return processor, repo, published


def message(hour: int, vitals: dict, subject_id: int = 7) -> VitalsMessage:
    return VitalsMessage(subject_id, 70, 65, "F", hour, (T0 + timedelta(hours=hour)).isoformat(), None, vitals)


def test_every_record_is_saved_and_published_even_without_alert():
    processor, repo, published = make_processor()
    for hour in range(3):
        processor.handle(message(hour, NORMAL))
    assert len(repo.vitals) == len(repo.predictions) == 3
    assert [t for t, _, _ in published] == ["predictions"] * 3
    assert published[-1][2]["risk_level"] == "NORMAL" and published[-1][2]["anomaly_score"] is None
    assert repo.predictions[-1]["anomaly_model_version_id"] is None


def test_two_consecutive_critical_records_create_one_alert():
    processor, repo, published = make_processor()
    processor.handle(message(0, NORMAL))
    processor.handle(message(1, CRITICAL))
    processor.handle(message(2, CRITICAL))
    assert [a["alert_type"] for a in repo.alerts] == ["RISK"]
    assert [t for t, _, _ in published].count("alerts") == 1
    assert repo.alerts[0]["prediction_id"] == repo.predictions[1]["id"]


def test_resolved_alert_is_recreated_only_after_cooldown():
    processor, repo, _ = make_processor()
    processor.handle(message(0, CRITICAL))
    repo.alerts[0]["status"] = "RESOLVED"
    for hour in range(1, 6):
        processor.handle(message(hour, CRITICAL))
    # Cảnh báo đầu ở giờ 0, cooldown 4 giờ dữ liệu → cảnh báo tiếp theo ở giờ 4
    assert [v["hour_index"] for v in repo.vitals for a in repo.alerts if a["prediction_recorded_at"] == v["recorded_at"]] == [0, 4]


def test_admin_threshold_override_changes_risk_level():
    processor, repo, _ = make_processor()
    processor.alert_settings = AlertSettingsRow(risk_critical_threshold=1.1, anomaly_threshold=0.99, cooldown_hours=4)
    processor._settings_checked = float("inf")
    processor.handle(message(0, CRITICAL))
    assert repo.predictions[0]["risk_level"] != "CRITICAL" and repo.alerts == []


def test_anomaly_alert_once_window_is_scorable_with_model_version():
    processor, repo, published = make_processor(anomaly_score=0.995)
    rng = np.random.default_rng(1)
    for hour in range(18):
        processor.handle(message(hour, {k: v + rng.normal() for k, v in NORMAL.items()}))
    scored = [p for p in repo.predictions if p["anomaly_score"] is not None]
    assert len(scored) == 2 and all(p["is_anomaly"] for p in scored)  # hour_index 16 và 17
    assert all(p["anomaly_model_version_id"] is not None for p in scored)
    assert [a["alert_type"] for a in repo.alerts] == ["ANOMALY"]


def test_duplicate_hour_is_skipped_and_state_rebuilds_from_db_after_restart():
    processor, repo, _ = make_processor()
    for hour in range(4):
        processor.handle(message(hour, NORMAL))
    assert processor.handle(message(2, NORMAL)) is None
    restarted = StreamProcessor(repo, processor.models, lambda *a: None, SETTINGS)
    assert restarted.handle(message(3, NORMAL)) is None  # đã có trong DB
    restarted.handle(message(4, NORMAL))
    assert [v["hour_index"] for v in repo.vitals] == [0, 1, 2, 3, 4]


def test_failed_save_leaves_state_consistent_with_db():
    processor, repo, _ = make_processor()
    processor.handle(message(0, NORMAL))
    repo.fail_next_save = True
    with pytest.raises(RuntimeError):
        processor.handle(message(1, NORMAL))
    assert processor.states[7].last_hour_index == 0
    processor.handle(message(1, NORMAL))
    assert [v["hour_index"] for v in repo.vitals] == [0, 1]
