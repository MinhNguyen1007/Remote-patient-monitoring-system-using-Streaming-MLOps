"""Kafka producer: phát lại dữ liệu nhóm `stream` như bệnh nhân đang nằm viện — docs/design/02_9 mục 2.9.1(g).

Mọi bệnh nhân bắt đầu cùng lúc; giờ dữ liệu thứ k của mọi bệnh nhân được phát ở nhịp thứ k, mỗi nhịp dài
`REPLAY_SECONDS_PER_DATA_HOUR` giây. Giá trị gửi đi là giá trị đo theo giờ **chưa điền** (`<vital>_obs`).

Chế độ `--drift` (mục 2.9.4): cộng một độ lệch có kiểm soát (HR +15 bpm, SpO2 −3%) vào một nhóm bệnh nhân,
mô phỏng thay đổi thiết bị đo / quần thể bệnh nhân. Message mang cờ `drift_applied` để truy vết.

Chạy từ gốc repo (host): KAFKA_BOOTSTRAP_SERVERS=localhost:29092 .venv\\Scripts\\python -m rpm_streaming.producer
"""

import argparse
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from confluent_kafka import Producer

from rpm_streaming.config import DEFAULT_REPLAY_FILE, load_settings
from rpm_streaming.kafka.topics import ensure_topics
from rpm_streaming.kafka.messages import VitalsMessage
from rpm_common.itemids import VITALS, obs_col

log = logging.getLogger("producer")

DRIFT_SHIFTS = {"heart_rate": 15.0, "spo2": -3.0}
VITAL_LIMITS = {"spo2": (0.0, 100.0)}


def load_replay(path: Path, limit_patients: int | None = None) -> dict[int, pd.DataFrame]:
    """Bảng phát lại theo bệnh nhân, sắp theo giờ; `limit_patients` lấy các bệnh nhân đầu tiên theo subject_id."""
    replay = pd.read_parquet(path).sort_values(["subject_id", "hour_index"])
    subjects = sorted(replay["subject_id"].unique())[:limit_patients]
    return {int(s): replay[replay["subject_id"] == s].reset_index(drop=True) for s in subjects}


def choose_drift_subjects(subjects: list[int], fraction: float, seed: int) -> set[int]:
    if fraction <= 0:
        return set()
    rng = np.random.default_rng(seed)
    count = max(1, int(round(fraction * len(subjects))))
    return {int(s) for s in rng.choice(sorted(subjects), size=count, replace=False)}


def apply_drift(vitals: dict[str, float | None]) -> dict[str, float | None]:
    shifted = dict(vitals)
    for vital, delta in DRIFT_SHIFTS.items():
        if shifted.get(vital) is not None:
            low, high = VITAL_LIMITS.get(vital, (-np.inf, np.inf))
            shifted[vital] = float(np.clip(shifted[vital] + delta, low, high))
    return shifted


def build_message(row: pd.Series, recorded_at: datetime, drift: bool) -> VitalsMessage:
    vitals = {v: (None if pd.isna(row[obs_col(v)]) else float(row[obs_col(v)])) for v in VITALS}
    if drift:
        vitals = apply_drift(vitals)
    gender = None if pd.isna(row["gender_male"]) else ("M" if row["gender_male"] == 1 else "F")
    return VitalsMessage(
        subject_id=int(row["subject_id"]),
        icustay_id=int(row["icustay_id"]),
        age=None if pd.isna(row["age"]) else int(row["age"]),
        gender=gender,
        hour_index=int(row["hour_index"]),
        recorded_at=recorded_at.isoformat(),
        source_charttime=None if pd.isna(row["source_charttime"]) else row["source_charttime"].isoformat(),
        vitals=vitals,
        drift_applied=drift,
    )


def replay(
    producer, topic: str, stays: dict[int, pd.DataFrame], seconds_per_hour: float, drift_subjects: set[int],
    max_hours: int | None = None, clock=time.monotonic, sleep=time.sleep,
) -> int:
    """Phát lần lượt từng nhịp; trả về số message đã gửi."""
    total_hours = max(len(stay) for stay in stays.values())
    if max_hours is not None:
        total_hours = min(total_hours, max_hours)
    start, sent = clock(), 0
    for step in range(total_hours):
        now = datetime.now(timezone.utc)
        for subject_id, stay in stays.items():
            if step < len(stay):
                message = build_message(stay.iloc[step], now, subject_id in drift_subjects)
                producer.produce(topic, key=message.key, value=message.to_json())
                sent += 1
        producer.poll(0)
        if step % 12 == 0:
            log.info("nhịp %d/%d, đã gửi %d message", step + 1, total_hours, sent)
        delay = start + (step + 1) * seconds_per_hour - clock()
        if delay > 0:
            sleep(delay)
    producer.flush(30)
    return sent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--replay-file", type=Path, default=DEFAULT_REPLAY_FILE)
    parser.add_argument("--seconds-per-hour", type=float, help="mặc định REPLAY_SECONDS_PER_DATA_HOUR")
    parser.add_argument("--limit-patients", type=int, help="chỉ phát N bệnh nhân đầu tiên")
    parser.add_argument("--max-hours", type=int, help="dừng sau N giờ dữ liệu")
    parser.add_argument("--drift", action="store_true", help="bật chế độ drift mô phỏng")
    parser.add_argument("--drift-fraction", type=float, default=0.5, help="tỷ lệ bệnh nhân bị áp drift")
    parser.add_argument("--drift-seed", type=int, default=42)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    settings = load_settings()
    stays = load_replay(args.replay_file, args.limit_patients)
    drift_subjects = choose_drift_subjects(list(stays), args.drift_fraction, args.drift_seed) if args.drift else set()
    seconds = args.seconds_per_hour if args.seconds_per_hour is not None else settings.seconds_per_data_hour
    log.info(
        "phát lại %d bệnh nhân, %.2f giây/giờ dữ liệu, drift trên %s", len(stays), seconds, sorted(drift_subjects) or "không"
    )
    ensure_topics(settings)
    producer = Producer({"bootstrap.servers": settings.kafka_bootstrap, "linger.ms": 5, "acks": "all"})
    sent = replay(producer, settings.topic_vitals, stays, seconds, drift_subjects, args.max_hours)
    log.info("xong: %d message", sent)


if __name__ == "__main__":
    main()
