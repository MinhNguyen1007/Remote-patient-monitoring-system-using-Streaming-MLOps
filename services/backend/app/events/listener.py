"""Kafka Event Listener của backend: đọc predictions-stream, alerts-stream, mlops-events → EventDispatcher.

Chạy trong một thread nền (confluent-kafka là thư viện đồng bộ); mỗi sự kiện được đưa sang event loop của FastAPI.
- Group riêng `rpm-backend`, commit offset sau khi đã xử lý: backend tắt rồi bật lại sẽ đọc tiếp từ offset cũ,
  không mất cảnh báo (02_10 mục 2.10.4). Email không bị gửi trùng nhờ kiểm tra notification_logs.
- Lần đầu chạy (chưa có offset) bắt đầu từ `latest`, để không gửi lại email cho các cảnh báo cũ trong topic.
"""

import asyncio
import json
import logging
import threading

from app.core.config import Settings
from app.events.dispatcher import ALERT, MLOPS, PREDICTION, EventDispatcher

log = logging.getLogger(__name__)
# Cùng số partition với services/streaming (rpm_streaming/kafka/topics.py) (key = mã bệnh nhân giữ thứ tự theo bệnh nhân)
STREAM_PARTITIONS = 3


class KafkaEventListener:
    def __init__(self, settings: Settings, dispatcher: EventDispatcher, loop: asyncio.AbstractEventLoop):
        self.settings = settings
        self.dispatcher = dispatcher
        self.loop = loop
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="kafka-listener", daemon=True)
        self.topics = {
            settings.kafka_topic_predictions: PREDICTION,
            settings.kafka_topic_alerts: ALERT,
            settings.kafka_topic_mlops: MLOPS,
        }

    def start(self) -> None:
        self._thread.start()

    def stop(self, timeout: float = 10.0) -> None:
        self._stop.set()
        self._thread.join(timeout)

    def ensure_topics(self) -> None:
        """Tạo trước các topic đang nghe nếu chưa có.

        Nếu subscribe vào topic chưa tồn tại, consumer chỉ thấy topic sau lần làm mới metadata (mặc định 5 phút) rồi
        bắt đầu từ `latest` — sự kiện đầu tiên (vd drift_report đầu tiên do DAG tạo ra topic) sẽ bị bỏ lỡ.
        mlops-events dùng 1 partition để giữ đúng thứ tự sự kiện; 2 topic của streaming dùng 3 như consumer tạo.
        """
        from confluent_kafka import KafkaException
        from confluent_kafka.admin import AdminClient, NewTopic

        admin = AdminClient({"bootstrap.servers": self.settings.kafka_bootstrap_servers})
        existing = set(admin.list_topics(timeout=15).topics)
        missing = [
            NewTopic(topic, num_partitions=1 if kind == MLOPS else STREAM_PARTITIONS, replication_factor=1)
            for topic, kind in self.topics.items()
            if topic not in existing
        ]
        for topic, future in admin.create_topics(missing).items() if missing else ():
            try:
                future.result()
                log.info("đã tạo topic %s", topic)
            except KafkaException as exc:
                if "TOPIC_ALREADY_EXISTS" not in str(exc):
                    raise

    def _run(self) -> None:
        from confluent_kafka import Consumer

        try:
            self.ensure_topics()
        except Exception:
            log.exception("không tạo trước được topic Kafka; vẫn subscribe (topic sẽ được tạo tự động)")
        consumer = Consumer(
            {
                "bootstrap.servers": self.settings.kafka_bootstrap_servers,
                "group.id": self.settings.backend_kafka_group,
                "auto.offset.reset": "latest",
                "enable.auto.commit": False,
                # Dự phòng khi không tạo trước được topic (Kafka chưa sẵn sàng lúc backend khởi động)
                "allow.auto.create.topics": True,
                "topic.metadata.refresh.interval.ms": 30000,
            }
        )
        consumer.subscribe(list(self.topics))
        log.info("Kafka listener đang nghe %s", list(self.topics))
        try:
            while not self._stop.is_set():
                msg = consumer.poll(1.0)
                if msg is None:
                    continue
                if msg.error():
                    log.warning("lỗi Kafka: %s", msg.error())
                    continue
                try:
                    payload = json.loads(msg.value())
                    future = asyncio.run_coroutine_threadsafe(
                        self.dispatcher.handle(self.topics[msg.topic()], payload), self.loop
                    )
                    future.result(timeout=30)
                except Exception:
                    log.exception("không xử lý được sự kiện từ %s", msg.topic())
                consumer.commit(message=msg, asynchronous=True)
        finally:
            consumer.close()
            log.info("Kafka listener đã dừng")
