"""Sự kiện MLOps trên Kafka topic `mlops-events` (Airflow → backend) — docs/design/02_4 mục 2.4.3.

Backend là nơi duy nhất gửi email và đẩy WebSocket: DAG chỉ publish sự kiện, backend gửi tới Admin.
- `drift_report`: sau mỗi lần kiểm tra drift có ghi báo cáo; `notify_admin = true` thì backend gửi email.
- `retrain_completed`: khi DAG retrain_pipeline kết thúc, kèm kết quả quality gate của từng mô hình.
"""

import json
import math
import os
from datetime import date, datetime
from uuid import UUID

from rpm_ml.storage.db import load_env

DRIFT_REPORT = "drift_report"
RETRAIN_COMPLETED = "retrain_completed"


def to_jsonable(value):
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        value = value.item()
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def publish(event: dict) -> None:
    """Gửi 1 sự kiện và chờ broker xác nhận; lỗi thì raise để task Airflow báo thất bại."""
    from confluent_kafka import Producer

    load_env()
    topic = os.environ.get("KAFKA_TOPIC_MLOPS", "mlops-events")
    producer = Producer({"bootstrap.servers": os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092")})
    errors = []
    producer.produce(
        topic,
        key=event["type"],
        value=json.dumps(to_jsonable(event), ensure_ascii=False),
        on_delivery=lambda err, _msg: err and errors.append(err),
    )
    if producer.flush(15) > 0 or errors:
        raise RuntimeError(f"không gửi được sự kiện {event['type']} lên {topic}: {errors or 'hết thời gian chờ'}")
