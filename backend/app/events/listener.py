"""Kafka Event Listener của backend: đọc predictions-stream và alerts-stream rồi chuyển cho EventDispatcher.

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
from app.events.dispatcher import ALERT, PREDICTION, EventDispatcher

log = logging.getLogger(__name__)


class KafkaEventListener:
    def __init__(self, settings: Settings, dispatcher: EventDispatcher, loop: asyncio.AbstractEventLoop):
        self.settings = settings
        self.dispatcher = dispatcher
        self.loop = loop
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="kafka-listener", daemon=True)
        self.topics = {settings.kafka_topic_predictions: PREDICTION, settings.kafka_topic_alerts: ALERT}

    def start(self) -> None:
        self._thread.start()

    def stop(self, timeout: float = 10.0) -> None:
        self._stop.set()
        self._thread.join(timeout)

    def _run(self) -> None:
        from confluent_kafka import Consumer

        consumer = Consumer(
            {
                "bootstrap.servers": self.settings.kafka_bootstrap_servers,
                "group.id": self.settings.backend_kafka_group,
                "auto.offset.reset": "latest",
                "enable.auto.commit": False,
                # Topic do stream consumer tạo; backend có thể khởi động trước
                "allow.auto.create.topics": True,
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
