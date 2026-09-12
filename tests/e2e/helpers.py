"""Tiện ích dùng chung cho bộ test E2E (Giai đoạn H) — docs/design/02_10 mục 2.10.2, 2.10.4.

Khác với unit test của từng service, bộ này chạy trên **hệ thống thật**: Kafka, PostgreSQL/TimescaleDB, MLflow
(docker compose) cộng với stream consumer và backend do chính bộ test khởi động dưới dạng tiến trình con — nhờ vậy
test có thể giết/khởi động lại chúng để kiểm tra khả năng chịu lỗi (2.10.4).
"""

import json
import os
import socket
import subprocess
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

import httpx

DEFAULT_TIMEOUT = 90.0


def wait_until(condition, timeout: float = DEFAULT_TIMEOUT, interval: float = 0.5, message: str = ""):
    """Chờ `condition()` trả giá trị đúng (truthy) và trả lại giá trị đó; hết giờ thì AssertionError."""
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = condition()
        if last:
            return last
        time.sleep(interval)
    raise AssertionError(f"quá {timeout:g}s vẫn chưa thỏa điều kiện: {message or condition} (giá trị cuối: {last!r})")


def port_open(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout):
            return True
    except OSError:
        return False


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


# --------------------------------------------------------------------------------- tiến trình con (consumer/backend)


class ManagedProcess:
    """Tiến trình con ghi log ra file, chờ được tới lúc "sẵn sàng", giết cứng và bật lại được.

    Dùng cho stream consumer và backend: 2.10.4 yêu cầu tắt/bật giữa chừng lúc đang replay.
    """

    def __init__(self, name: str, args: list[str], cwd: Path, env: dict, log_path: Path, ready_marker: str):
        self.name = name
        self.args = args
        self.cwd = cwd
        self.env = env
        self.log_path = log_path
        self.ready_marker = ready_marker
        self.process: subprocess.Popen | None = None
        self._log_file = None
        self._runs = 0

    # Trẻ con chạy trên Windows: ép UTF-8 để log tiếng Việt không vỡ khi stdout bị chuyển hướng vào file.
    def _child_env(self) -> dict:
        env = {**os.environ, **self.env}
        env.update(PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
        return env

    def start(self, ready_timeout: float = 180.0) -> "ManagedProcess":
        assert self.process is None, f"{self.name} đang chạy"
        self._runs += 1
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log_file = self.log_path.open("a", encoding="utf-8")
        self._log_file.write(f"\n===== {self.name} lần chạy {self._runs} @ {datetime.now().isoformat()} =====\n")
        self._log_file.flush()
        self.process = subprocess.Popen(
            self.args, cwd=str(self.cwd), env=self._child_env(),
            stdout=self._log_file, stderr=subprocess.STDOUT,
        )
        self.wait_ready(ready_timeout)
        return self

    def wait_ready(self, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise AssertionError(f"{self.name} thoát sớm (mã {self.process.returncode}):\n{self.tail()}")
            if self.ready_marker in self.log_text():
                return
            time.sleep(0.5)
        raise AssertionError(f"{self.name} không sẵn sàng sau {timeout:g}s:\n{self.tail()}")

    def log_text(self) -> str:
        if not self.log_path.exists():
            return ""
        return self.log_path.read_text(encoding="utf-8", errors="replace")

    def tail(self, lines: int = 40) -> str:
        return "\n".join(self.log_text().splitlines()[-lines:])

    def log_since_last_start(self) -> str:
        marker = f"===== {self.name} lần chạy {self._runs} @"
        text = self.log_text()
        return text[text.rfind(marker):] if marker in text else text

    def kill(self) -> None:
        """Giết cứng (Windows: TerminateProcess) — mô phỏng sự cố, không cho dọn dẹp."""
        if self.process is None:
            return
        self.process.kill()
        self.process.wait(timeout=30)
        self.process = None
        self._log_file.close()
        self._log_file = None

    def stop(self, timeout: float = 30.0) -> None:
        if self.process is None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=10)
        self.process = None
        self._log_file.close()
        self._log_file = None

    def restart(self, ready_timeout: float = 180.0) -> None:
        self.kill()
        self.start(ready_timeout)


# ------------------------------------------------------------------------------------------------ Kafka


class KafkaTap:
    """Consumer tạm (group riêng mỗi lần dùng) để đọc message do hệ thống sinh ra trong lúc test."""

    def __init__(self, bootstrap: str, topics: list[str]):
        from confluent_kafka import Consumer

        self.consumer = Consumer(
            {
                "bootstrap.servers": bootstrap,
                "group.id": f"e2e-tap-{uuid.uuid4()}",
                "auto.offset.reset": "latest",
                "enable.auto.commit": False,
            }
        )
        self.consumer.subscribe(topics)
        self._await_assignment()

    def _await_assignment(self, timeout: float = 60.0) -> None:
        """Chỉ bắt đầu test sau khi đã được gán partition, nếu không message đầu tiên sẽ lọt mất."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.consumer.poll(0.5)
            if self.consumer.assignment():
                return
        raise AssertionError("Kafka tap không được gán partition")

    def poll_messages(self, seconds: float) -> list[dict]:
        """Đọc tất cả message tới trong `seconds` giây."""
        deadline = time.monotonic() + seconds
        out = []
        while time.monotonic() < deadline:
            msg = self.consumer.poll(0.5)
            if msg is not None and not msg.error():
                out.append({"topic": msg.topic(), "key": msg.key().decode(), "value": json.loads(msg.value())})
        return out

    def collect_until(self, predicate, timeout: float = DEFAULT_TIMEOUT) -> list[dict]:
        """Đọc tới khi `predicate(danh sách đã đọc)` đúng; hết giờ thì AssertionError kèm những gì đã đọc."""
        deadline = time.monotonic() + timeout
        out = []
        while time.monotonic() < deadline:
            msg = self.consumer.poll(0.5)
            if msg is not None and not msg.error():
                out.append({"topic": msg.topic(), "key": msg.key().decode(), "value": json.loads(msg.value())})
                if predicate(out):
                    return out
        raise AssertionError(f"quá {timeout:g}s chưa nhận đủ message Kafka (đã nhận {len(out)})")

    def close(self) -> None:
        self.consumer.close()


def seek_group_to_end(bootstrap: str, group: str, topic: str) -> None:
    """Đặt offset đã commit của `group` về cuối topic.

    Stream consumer dùng `auto.offset.reset=earliest` (để không bỏ sót message khi chết giữa chừng). Với một group
    mới tinh, điều đó có nghĩa là đọc lại toàn bộ lịch sử topic — không phải thứ ta muốn ở đầu mỗi phiên test, nhất
    là sau khi DB vừa bị dọn. Commit sẵn offset cuối cho group để consumer bắt đầu từ message mới.
    """
    from confluent_kafka import Consumer, TopicPartition

    consumer = Consumer({"bootstrap.servers": bootstrap, "group.id": group, "enable.auto.commit": False})
    try:
        metadata = consumer.list_topics(topic, timeout=30)
        partitions = list(metadata.topics[topic].partitions) if topic in metadata.topics else []
        ends = []
        for partition in partitions:
            _, high = consumer.get_watermark_offsets(TopicPartition(topic, partition), timeout=30, cached=False)
            ends.append(TopicPartition(topic, partition, high))
        if ends:
            consumer.commit(offsets=ends, asynchronous=False)
    finally:
        consumer.close()


class Replay:
    """Phát lại dữ liệu thật từ `stream_replay.parquet`, nhớ giờ kế tiếp của từng bệnh nhân.

    Consumer bỏ qua giờ đã có (`hour_index <= giờ cuối`), nên mỗi lần phát phải nối tiếp giờ trước đó. Con trỏ giờ
    dùng chung cả phiên test: mỗi test chọn tập bệnh nhân riêng và cứ phát tiếp từ chỗ đang đứng.
    """

    def __init__(self, bootstrap: str, topic: str, replay_file: Path):
        from confluent_kafka import Producer

        from rpm_streaming.producer.replay import load_replay

        self.stays = load_replay(replay_file)
        self.subjects = sorted(self.stays)
        self.cursor = {subject: 0 for subject in self.subjects}
        self.producer = Producer({"bootstrap.servers": bootstrap, "linger.ms": 5, "acks": "all"})
        self.topic = topic

    def take(self, count: int, offset: int = 0) -> list[int]:
        """`count` bệnh nhân bắt đầu từ vị trí `offset` (mỗi test dùng một khoảng riêng để không giẫm chân nhau)."""
        chosen = self.subjects[offset : offset + count]
        assert len(chosen) == count, f"chỉ có {len(self.subjects)} bệnh nhân trong file replay"
        return chosen

    def publish_tick(self, subjects: list[int], drift: bool = False, on_publish=None) -> list:
        """Phát một nhịp (một giờ dữ liệu) cho từng bệnh nhân; trả về các message đã gửi."""
        from rpm_streaming.producer.replay import build_message

        recorded_at = datetime.now(timezone.utc)
        messages = []
        for subject in subjects:
            stay = self.stays[subject]
            step = self.cursor[subject]
            if step >= len(stay):
                continue
            message = build_message(stay.iloc[step], recorded_at, drift)
            if on_publish is not None:
                on_publish(message)
            self.producer.produce(self.topic, key=message.key, value=message.to_json())
            self.cursor[subject] = step + 1
            messages.append(message)
        self.producer.flush(30)
        return messages

    def publish_hours(self, subjects: list[int], hours: int, drift: bool = False) -> list:
        out = []
        for _ in range(hours):
            out.extend(self.publish_tick(subjects, drift=drift))
        return out


# ------------------------------------------------------------------------------------------------ backend


class Api:
    """Client REST của backend E2E; `login` trả về một client con đã gắn sẵn Bearer token."""

    def __init__(self, base_url: str, token: str | None = None):
        self.base_url = base_url
        self.token = token
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        self.client = httpx.Client(base_url=base_url, headers=headers, timeout=30.0)

    def login(self, email: str, password: str) -> "Api":
        response = httpx.post(f"{self.base_url}/auth/login", json={"email": email, "password": password}, timeout=30.0)
        response.raise_for_status()
        return Api(self.base_url, response.json()["access_token"])

    def get(self, path: str, **kwargs) -> httpx.Response:
        return self.client.get(path, **kwargs)

    def post(self, path: str, **kwargs) -> httpx.Response:
        return self.client.post(path, **kwargs)

    def put(self, path: str, **kwargs) -> httpx.Response:
        return self.client.put(path, **kwargs)

    def close(self) -> None:
        self.client.close()


class WsClient:
    """Client WebSocket đọc nền: mọi sự kiện được ghi kèm thời điểm nhận (để đo độ trễ đầu–cuối, 2.10.4)."""

    def __init__(self, ws_url: str, token: str):
        from websockets.sync.client import connect

        self.connection = connect(f"{ws_url}/ws?token={token}", open_timeout=30)
        self.events: deque = deque()
        self._error: BaseException | None = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        self.wait_for(lambda event: event["type"] == "connected", timeout=30)

    def _read_loop(self) -> None:
        while not self._stop.is_set():
            try:
                raw = self.connection.recv(timeout=1.0)
            except TimeoutError:
                continue
            except Exception as exc:  # kết nối đóng hoặc lỗi đọc
                if not self._stop.is_set():
                    self._error = exc
                return
            if isinstance(raw, str) and raw.startswith("{"):
                self.events.append((time.time(), json.loads(raw)))

    def received(self, event_type: str | None = None) -> list[dict]:
        return [event for _, event in list(self.events) if event_type is None or event["type"] == event_type]

    def timed(self, event_type: str) -> list[tuple[float, dict]]:
        return [(at, event) for at, event in list(self.events) if event["type"] == event_type]

    def wait_for(self, predicate, timeout: float = DEFAULT_TIMEOUT) -> dict:
        found = wait_until(
            lambda: next((event for _, event in list(self.events) if predicate(event)), None),
            timeout=timeout, interval=0.2, message="sự kiện WebSocket",
        )
        return found

    def close(self) -> None:
        self._stop.set()
        try:
            self.connection.close()
        except Exception:
            pass
        self._thread.join(timeout=5)


def ws_rejects(ws_url: str, token: str) -> bool:
    """True nếu server từ chối token (đóng với mã 1008) — dùng cho test đăng nhập/WebSocket (2.4.2)."""
    from websockets.exceptions import InvalidStatus, WebSocketException
    from websockets.sync.client import connect

    try:
        connection = connect(f"{ws_url}/ws?token={token}", open_timeout=30)
    except (InvalidStatus, WebSocketException):
        return True
    try:
        connection.recv(timeout=10)
        return False
    except Exception:
        return True
    finally:
        connection.close()
