"""Stream consumer: vitals-stream → đặc trưng → 2 mô hình → DB + predictions-stream / alerts-stream.

Luồng theo docs/design/02_3 mục 2.3.1 và 02_4 mục 2.4.1:
  1. cập nhật state bệnh nhân (dựng lại từ DB nếu consumer vừa khởi động);
  2. tính đặc trưng + NEWS2 bằng rpm_common; dự báo rủi ro; nếu đủ cửa sổ 12 giờ thì chấm điểm bất thường;
  3. quyết định cảnh báo (chống trùng: OPEN + cooldown giờ dữ liệu);
  4. ghi vital_record + prediction + alert trong một transaction;
  5. publish prediction (luôn luôn) và alert (nếu có);
  6. commit offset Kafka sau khi đã ghi DB (at-least-once; bản ghi giờ đã có trong DB được bỏ qua khi nhận lại).

Chạy từ gốc repo (host):
  KAFKA_BOOTSTRAP_SERVERS=localhost:29092 MLFLOW_TRACKING_URI=http://localhost:5000 POSTGRES_HOST=localhost \\
  .venv\\Scripts\\python -m rpm_streaming.consumer
"""

try:  # nạp DLL TensorFlow trước sklearn/scipy (lỗi DLL trên Windows khi nạp sau)
    import tensorflow  # noqa: F401
except ImportError:
    pass

import argparse
import logging
import signal
import time
import uuid
from datetime import datetime, timezone

import pandas as pd

from rpm_streaming.consumer.alerting import alerts_to_create, effective_risk_threshold
from rpm_streaming.config import Settings, load_settings
from rpm_streaming.kafka.topics import ensure_topics
from rpm_streaming.kafka.messages import VitalsMessage, event_json
from rpm_streaming.consumer.model_service import ModelService, predict_anomaly, predict_risk
from rpm_streaming.consumer.patient_state import PatientState
from rpm_streaming.storage.repository import AlertSettingsRow, Repository
from rpm_common.itemids import VITALS
from rpm_common.news2 import RISK_CRITICAL, RISK_LEVELS

log = logging.getLogger("consumer")
MAX_ATTEMPTS = 3


class StreamProcessor:
    """Xử lý từng message; không phụ thuộc Kafka để có thể kiểm thử với repo/model giả."""

    def __init__(self, repo, models: ModelService, publish, settings: Settings, clock=time.monotonic):
        self.repo = repo
        self.models = models
        self.publish = publish
        self.settings = settings
        self.clock = clock
        self.states: dict[int, PatientState] = {}
        self.defaults = AlertSettingsRow(
            settings.default_risk_threshold, settings.default_anomaly_threshold, settings.default_cooldown_hours
        )
        self.alert_settings: AlertSettingsRow | None = None
        self._settings_checked = float("-inf")

    def current_alert_settings(self) -> AlertSettingsRow:
        """Đọc lại alert_settings định kỳ để thay đổi của Admin (UC08) có hiệu lực mà không cần khởi động lại."""
        if self.alert_settings is None or self.clock() - self._settings_checked >= self.settings.settings_refresh_seconds:
            self.alert_settings = self.repo.alert_settings(self.defaults)
            self._settings_checked = self.clock()
        return self.alert_settings

    def state_for(self, message: VitalsMessage) -> PatientState:
        state = self.states.get(message.subject_id)
        if state is None:
            patient_id = self.repo.upsert_patient(message.subject_id, message.icustay_id, message.age, message.gender)
            gender_male = None if message.gender is None else float(message.gender == "M")
            state = PatientState(patient_id, message.subject_id, message.icustay_id, message.age, gender_male)
            for row in self.repo.load_vitals(patient_id):
                state.append(row["hour_index"], row["recorded_at"], {v: row[v] for v in VITALS})
            if state.rows:
                log.info("dựng lại state BN-%s từ %d giờ trong DB", message.subject_id, len(state.rows))
            self.states[message.subject_id] = state
        return state

    def handle(self, message: VitalsMessage) -> dict | None:
        state = self.state_for(message)
        if state.last_hour_index is not None and message.hour_index <= state.last_hour_index:
            log.warning("bỏ qua BN-%s giờ %d (đã có tới giờ %d)", message.subject_id, message.hour_index, state.last_hour_index)
            return None

        recorded_at = message.recorded_at_dt
        state.append(message.hour_index, recorded_at, message.vitals)
        try:
            result = self._predict_and_save(state, message, recorded_at)
        except Exception:
            state.rows.pop()  # giữ state khớp với DB khi ghi thất bại
            raise
        return result

    def _predict_and_save(self, state: PatientState, message: VitalsMessage, recorded_at: datetime) -> dict:
        settings = self.current_alert_settings()
        risk_model, anomaly_model = self.models.risk, self.models.anomaly
        features = state.features()
        current = features.iloc[[-1]]
        tau = effective_risk_threshold(settings.risk_critical_threshold, risk_model.tau_critical)
        risk = predict_risk(risk_model, current, tau)
        anomaly_score = predict_anomaly(anomaly_model, state.current_window(features))
        is_anomaly = None if anomaly_score is None else anomaly_score >= settings.anomaly_threshold

        news2 = current["news2_score"].iloc[0]
        now = datetime.now(timezone.utc)
        prediction = {
            "id": uuid.uuid4(),
            "recorded_at": recorded_at,
            "patient_id": state.patient_id,
            "predicted_at": now,
            "news2_score": None if pd.isna(news2) else int(news2),
            "risk_level": RISK_LEVELS[risk.risk_level],
            "risk_score": risk.risk_score,
            "anomaly_score": anomaly_score,
            "is_anomaly": is_anomaly,
            "risk_model_version_id": risk_model.db_id,
            "anomaly_model_version_id": None if anomaly_score is None else anomaly_model.db_id,
        }
        triggered = {"RISK": risk.risk_level == RISK_CRITICAL, "ANOMALY": bool(is_anomaly)}
        new_types = []
        if any(triggered.values()):
            history = self.repo.alert_history(state.patient_id)
            new_types = alerts_to_create(triggered, message.hour_index, history, settings.cooldown_hours)
        alerts = [
            {
                "id": uuid.uuid4(),
                "patient_id": state.patient_id,
                "prediction_id": prediction["id"],
                "prediction_recorded_at": recorded_at,
                "alert_type": alert_type,
                "created_at": now,
            }
            for alert_type in new_types
        ]
        vital = {"patient_id": state.patient_id, "recorded_at": recorded_at, "hour_index": message.hour_index}
        vital |= {v: message.vitals.get(v) for v in VITALS}
        self.repo.save_hour(vital, prediction, alerts)

        event = self._prediction_event(prediction, message, current, risk_model.version, anomaly_model, tau)
        key = str(state.patient_id)
        self.publish(self.settings.topic_predictions, key, event_json(event))
        for alert in alerts:
            self.publish(self.settings.topic_alerts, key, event_json(self._alert_event(alert, event)))
        return {"prediction": prediction, "alerts": alerts}

    @staticmethod
    def _prediction_event(prediction, message, current, risk_version, anomaly_model, tau) -> dict:
        return {
            "prediction_id": prediction["id"],
            "patient_id": prediction["patient_id"],
            "subject_id": message.subject_id,
            "hour_index": message.hour_index,
            "recorded_at": prediction["recorded_at"].isoformat(),
            "predicted_at": prediction["predicted_at"].isoformat(),
            "vitals": message.vitals,
            # Giá trị sau forward-fill có giới hạn (giá trị đang dùng để tính NEWS2/đặc trưng)
            "vitals_filled": {v: current[v].iloc[0] for v in VITALS},
            "news2_score": prediction["news2_score"],
            "risk_level": prediction["risk_level"],
            "risk_score": prediction["risk_score"],
            "tau_critical": tau,
            "anomaly_score": prediction["anomaly_score"],
            "is_anomaly": prediction["is_anomaly"],
            "risk_model_version": risk_version,
            "anomaly_model_version": None if prediction["anomaly_score"] is None else anomaly_model.version,
        }

    @staticmethod
    def _alert_event(alert: dict, prediction_event: dict) -> dict:
        return {
            "alert_id": alert["id"],
            "patient_id": alert["patient_id"],
            "subject_id": prediction_event["subject_id"],
            "alert_type": alert["alert_type"],
            "status": "OPEN",
            "created_at": alert["created_at"].isoformat(),
            "prediction_id": alert["prediction_id"],
            "prediction_recorded_at": alert["prediction_recorded_at"].isoformat(),
            "hour_index": prediction_event["hour_index"],
            "news2_score": prediction_event["news2_score"],
            "risk_level": prediction_event["risk_level"],
            "risk_score": prediction_event["risk_score"],
            "anomaly_score": prediction_event["anomaly_score"],
        }


def process_with_retry(processor: StreamProcessor, message: VitalsMessage) -> dict | None:
    """Thử lại lỗi tạm thời (DB/MLflow); hết lượt thì ném lỗi để tiến trình dừng mà chưa commit offset."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return processor.handle(message)
        except Exception:
            if attempt == MAX_ATTEMPTS:
                raise
            log.exception("lỗi xử lý BN-%s giờ %d, thử lại lần %d", message.subject_id, message.hour_index, attempt + 1)
            processor.states.pop(message.subject_id, None)  # dựng lại state từ DB ở lần thử sau
            time.sleep(attempt)


def run(settings: Settings) -> None:
    import mlflow
    from confluent_kafka import Consumer, KafkaException, Producer
    from mlflow import MlflowClient

    mlflow.set_tracking_uri(settings.mlflow_uri)
    ensure_topics(settings)
    repo = Repository(settings.postgres_dsn)
    models = ModelService(MlflowClient(), repo.sync_champion, settings.model_refresh_seconds)
    models.refresh_if_due()
    producer = Producer({"bootstrap.servers": settings.kafka_bootstrap, "linger.ms": 5})
    consumer = Consumer(
        {
            "bootstrap.servers": settings.kafka_bootstrap,
            "group.id": settings.consumer_group,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )
    consumer.subscribe([settings.topic_vitals])

    def publish(topic: str, key: str, value: bytes) -> None:
        producer.produce(topic, key=key, value=value)

    processor = StreamProcessor(repo, models, publish, settings)
    running = True

    def stop(*_):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    log.info("consumer sẵn sàng: %s → %s, %s", settings.topic_vitals, settings.topic_predictions, settings.topic_alerts)
    processed = 0
    try:
        while running:
            models.refresh_if_due()
            producer.poll(0)
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().fatal():
                    raise KafkaException(msg.error())
                log.warning("lỗi Kafka: %s", msg.error())
                continue
            started = time.perf_counter()
            message = VitalsMessage.from_json(msg.value())
            result = process_with_retry(processor, message)
            consumer.commit(message=msg, asynchronous=True)
            processed += 1
            if result is not None:
                p = result["prediction"]
                log.info(
                    "BN-%s giờ %d: NEWS2=%s risk=%s (%.3f) anomaly=%s alerts=%s | %.0f ms",
                    message.subject_id, message.hour_index, p["news2_score"],
                    p["risk_level"], p["risk_score"],
                    "—" if p["anomaly_score"] is None else f"{p['anomaly_score']:.3f}",
                    [a["alert_type"] for a in result["alerts"]] or "-", 1000 * (time.perf_counter() - started),
                )
    finally:
        log.info("dừng consumer sau %d message", processed)
        producer.flush(10)
        consumer.close()
        repo.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    run(load_settings())


if __name__ == "__main__":
    main()
