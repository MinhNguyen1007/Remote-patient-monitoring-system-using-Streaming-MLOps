"""Tạo 3 topic nếu chưa có (producer và consumer đều gọi lúc khởi động, không phụ thuộc auto-create của broker).

Nhiều partition vẫn giữ thứ tự theo bệnh nhân vì message có key = mã bệnh nhân (cùng key → cùng partition).
"""

import logging

from confluent_kafka import KafkaException
from confluent_kafka.admin import AdminClient, NewTopic

from config import Settings

log = logging.getLogger("kafka_topics")
PARTITIONS = 3


def ensure_topics(settings: Settings, timeout: float = 30.0) -> None:
    admin = AdminClient({"bootstrap.servers": settings.kafka_bootstrap})
    existing = set(admin.list_topics(timeout=timeout).topics)
    wanted = [settings.topic_vitals, settings.topic_predictions, settings.topic_alerts]
    missing = [NewTopic(t, num_partitions=PARTITIONS, replication_factor=1) for t in wanted if t not in existing]
    for topic, future in admin.create_topics(missing).items() if missing else ():
        try:
            future.result()
            log.info("đã tạo topic %s (%d partition)", topic, PARTITIONS)
        except KafkaException as exc:
            if "TOPIC_ALREADY_EXISTS" not in str(exc):
                raise
