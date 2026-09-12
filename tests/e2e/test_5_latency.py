"""E2E phi chức năng: độ trễ đầu–cuối producer → WebSocket — 02_10 mục 2.10.4 dòng 1 (ngưỡng p95 < 2 giây).

Đo đúng chuỗi mà người dùng cảm nhận: `producer.produce()` → Kafka → stream consumer (đặc trưng + 2 mô hình) → DB
→ `predictions-stream` → Kafka listener của backend → EventDispatcher → WebSocket của điều dưỡng phụ trách.

Chạy sau cùng vì test này **dọn sạch dữ liệu phát lại** và đặt lại con trỏ giờ để có đủ 20 bệnh nhân phát đồng thời
ở tốc độ mặc định, đúng như kịch bản thiết kế. Kết quả ghi ra `reports/latency.md` để dùng cho báo cáo mục 3.4.
"""

import json
import statistics
import time
from pathlib import Path

import pytest

from conftest import DEMO_TABLES
from helpers import WsClient, wait_until

SECONDS_PER_HOUR = 5.0  # REPLAY_SECONDS_PER_DATA_HOUR mặc định
TICKS = 12              # bệnh nhân ngắn nhất trong nhóm stream chỉ có 12 giờ dữ liệu
EXTRA_TICKS = 12        # phát tiếp cho các bệnh nhân dài hơn, để có cả giai đoạn mô hình bất thường đã hoạt động
P95_THRESHOLD = 2.0
REPORT = Path(__file__).resolve().parent / "reports" / "latency.md"


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    low, high = int(position), min(int(position) + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def summarize(samples: list[dict]) -> dict:
    values = [s["latency"] for s in samples]
    return {
        "n": len(values),
        "p50": percentile(values, 0.50),
        "p95": percentile(values, 0.95),
        "p99": percentile(values, 0.99),
        "max": max(values),
        "mean": statistics.fmean(values),
    }


@pytest.fixture(scope="module")
def fresh_stack(consumer, backend, db, replay):
    """Dọn dữ liệu phát lại và đặt lại con trỏ giờ, để cả 20 bệnh nhân cùng bắt đầu từ giờ 0.

    Phải dừng consumer trước khi TRUNCATE: state trong bộ nhớ của nó đang giữ `patient_id` sắp bị xóa.
    """
    consumer.kill()
    db.execute(f"TRUNCATE {', '.join(DEMO_TABLES)}")
    for subject in replay.subjects:
        replay.cursor[subject] = 0
    consumer.start(ready_timeout=300)
    return replay


def test_end_to_end_latency_p95(fresh_stack, consumer, backend, db, ws_url, api_url, make_staff, record_property):
    replay = fresh_stack
    subjects = replay.subjects
    assert len(subjects) == 20, f"kịch bản 2.10.4 cần 20 bệnh nhân, file replay có {len(subjects)}"

    # Nhịp đầu chỉ để tạo bệnh nhân trong DB (phân công cần patient_id), chưa tính vào số đo.
    replay.publish_tick(subjects)
    patients = {
        subject: wait_until(lambda s=subject: db.patient_id(s), timeout=300, message=f"bệnh nhân {subject}")
        for subject in subjects
    }
    wait_until(
        lambda: db.one("SELECT count(*) FROM predictions") >= len(subjects),
        timeout=300, message="consumer xử lý xong nhịp khởi động",
    )

    from helpers import Api

    nurse = make_staff("NURSE", list(patients.values()))
    token = Api(api_url).login(nurse["email"], nurse["password"]).token
    client = WsClient(ws_url, token)
    published: dict[tuple[int, int], float] = {}

    def stamp(message) -> None:
        published[(message.subject_id, message.hour_index)] = time.time()

    try:
        # Giai đoạn 1: 20 bệnh nhân, tốc độ mặc định — đúng kịch bản ở 02_10 mục 2.10.4.
        long_stays = [s for s in subjects if len(replay.stays[s]) >= TICKS + EXTRA_TICKS]
        phase_of: dict[tuple[int, int], str] = {}
        for phase, ticks, group in (("20 bệnh nhân", TICKS - 1, subjects),
                                    (f"{len(long_stays)} bệnh nhân dài", EXTRA_TICKS, long_stays)):
            for _ in range(ticks):
                started = time.monotonic()
                for message in replay.publish_tick(group, on_publish=stamp):
                    phase_of[(message.subject_id, message.hour_index)] = phase
                slack = SECONDS_PER_HOUR - (time.monotonic() - started)
                if slack > 0:
                    time.sleep(slack)

        # Chờ các prediction cuối về tới WebSocket (không tính vào độ trễ: đã có dấu thời gian riêng từng message)
        wait_until(
            lambda: len([e for e in client.received("prediction")]) >= len(published),
            timeout=180, message=f"nhận đủ {len(published)} prediction qua WebSocket",
        )
    finally:
        client.close()

    samples = []
    for received_at, event in client.timed("prediction"):
        key = (event["data"]["subject_id"], event["data"]["hour_index"])
        if key in published:
            samples.append({
                "subject_id": key[0], "hour_index": key[1], "latency": received_at - published[key],
                "phase": phase_of.get(key, "?"), "anomaly": event["data"]["anomaly_score"] is not None,
            })

    assert len(samples) == len(published), f"nhận {len(samples)}/{len(published)} prediction qua WebSocket"
    overall = summarize(samples)
    by_phase = {phase: summarize([s for s in samples if s["phase"] == phase])
                for phase in dict.fromkeys(s["phase"] for s in samples)}
    with_anomaly = [s for s in samples if s["anomaly"]]
    write_report(overall, by_phase, with_anomaly and summarize(with_anomaly) or None, len(subjects))

    for key, value in overall.items():
        record_property(f"latency_{key}", round(value, 3) if isinstance(value, float) else value)
    print(f"\nđộ trễ đầu–cuối: n={overall['n']} p50={overall['p50']:.2f}s p95={overall['p95']:.2f}s "
          f"p99={overall['p99']:.2f}s max={overall['max']:.2f}s")
    assert overall["p95"] < P95_THRESHOLD, (
        f"p95 = {overall['p95']:.2f}s, ngưỡng {P95_THRESHOLD}s — chi tiết ở {REPORT}"
    )


def write_report(overall: dict, by_phase: dict, with_anomaly: dict | None, n_patients: int) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Độ trễ đầu–cuối (02_10 mục 2.10.4)",
        "",
        f"Sinh tự động bởi `tests/e2e/test_5_latency.py` lúc {time.strftime('%Y-%m-%d %H:%M:%S')}.",
        "",
        f"Đo từ lúc producer gọi `produce()` tới lúc client WebSocket nhận được sự kiện `prediction`, "
        f"{n_patients} bệnh nhân phát đồng thời, {SECONDS_PER_HOUR:g} giây/giờ dữ liệu (tốc độ mặc định).",
        "",
        "| Nhóm mẫu | n | p50 (s) | p95 (s) | p99 (s) | max (s) | trung bình (s) |",
        "|---|---|---|---|---|---|---|",
    ]
    rows = [("Tất cả", overall), *by_phase.items()]
    if with_anomaly:
        rows.append(("Có điểm bất thường (đủ cửa sổ 12 giờ)", with_anomaly))
    for label, stats in rows:
        lines.append(
            f"| {label} | {stats['n']} | {stats['p50']:.2f} | {stats['p95']:.2f} | {stats['p99']:.2f} | "
            f"{stats['max']:.2f} | {stats['mean']:.2f} |"
        )
    lines += ["", f"Ngưỡng thiết kế: p95 < {P95_THRESHOLD:g} giây.", ""]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    REPORT.with_suffix(".json").write_text(
        json.dumps({"overall": overall, "by_phase": by_phase, "with_anomaly": with_anomaly}, indent=2),
        encoding="utf-8",
    )
