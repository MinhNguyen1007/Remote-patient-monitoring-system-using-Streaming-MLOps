"""E2E: Streaming → Prediction → Alert — docs/design/02_10 mục 2.10.2 dòng 1 (Activity 2.3.1, Sequence 2.4.1).

Chạy trên hệ thống thật: producer đẩy giờ dữ liệu lên `vitals-stream`, stream consumer (tiến trình riêng, nạp
champion từ MLflow) ghi DB và publish `predictions-stream` / `alerts-stream`.

Các module test đánh số theo thứ tự chạy: con trỏ giờ phát lại dùng chung cả phiên, và `test_5_latency` dọn DB để
đo lại từ đầu nên phải chạy sau cùng.
"""

import pytest

from conftest import TOPIC_ALERTS, TOPIC_PREDICTIONS
from helpers import wait_until
from rpm_common.itemids import VITALS


@pytest.fixture(scope="module")
def subjects(replay) -> list[int]:
    return replay.take(2)


def test_vitals_message_creates_record_prediction_and_event(replay, consumer, db, tap, subjects):
    """Một message vitals → 1 vital_record + 1 prediction trong DB + 1 message trên predictions-stream."""
    subject = subjects[0]
    predictions = tap([TOPIC_PREDICTIONS])

    sent = replay.publish_tick([subject])
    assert len(sent) == 1
    message = sent[0]

    patient_id = wait_until(lambda: db.patient_id(subject), message=f"bệnh nhân {subject} xuất hiện trong DB")
    record = wait_until(
        lambda: next(iter(db.rows(
            "SELECT * FROM vital_records WHERE patient_id = %s AND hour_index = %s", (patient_id, message.hour_index)
        )), None),
        message="vital_record",
    )
    prediction = wait_until(
        lambda: next(iter(db.rows(
            "SELECT * FROM predictions WHERE patient_id = %s AND recorded_at = %s",
            (patient_id, record["recorded_at"]),
        )), None),
        message="prediction",
    )

    # vital_records lưu **giá trị đo chưa điền**, đúng như producer gửi (quy ước ở services/streaming/CLAUDE.md)
    for vital in VITALS:
        expected = message.vitals[vital]
        if expected is None:
            assert record[vital] is None, f"{vital} phải trống như giá trị đo gốc"
        else:
            assert record[vital] == pytest.approx(expected, abs=1e-6), vital
    assert prediction["risk_level"] in ("NORMAL", "WARNING", "CRITICAL")
    assert 0.0 <= prediction["risk_score"] <= 1.0
    assert prediction["risk_model_version_id"] is not None, "prediction phải ghi version model đã dùng"

    events = predictions.collect_until(
        lambda got: any(e["value"]["prediction_id"] == str(prediction["id"]) for e in got)
    )
    event = next(e["value"] for e in events if e["value"]["prediction_id"] == str(prediction["id"]))
    assert event["patient_id"] == str(patient_id)
    assert event["subject_id"] == subject
    assert event["hour_index"] == message.hour_index
    assert event["risk_level"] == prediction["risk_level"]
    assert event["risk_score"] == pytest.approx(prediction["risk_score"])
    assert event["news2_score"] == prediction["news2_score"]
    # Key = patient_id để Kafka giữ đúng thứ tự theo từng bệnh nhân
    assert next(e["key"] for e in events if e["value"]["prediction_id"] == str(prediction["id"])) == str(patient_id)


def test_consecutive_critical_hours_create_single_alert(replay, consumer, db, tap, subjects, force_critical,
                                                       alert_slate):
    """Hạ ngưỡng của Admin → nhiều giờ CRITICAL liên tiếp chỉ sinh 1 cảnh báo RISK (chống bão cảnh báo).

    Bao trùm 2 ý của 2.10.2 dòng 1: vượt ngưỡng thì có `alerts` + message trên `alerts-stream`; các giờ CRITICAL sau
    không tạo thêm cảnh báo vì vẫn còn cảnh báo OPEN cùng loại.
    """
    subject = subjects[1]
    alerts_tap = tap([TOPIC_ALERTS])

    # Giờ đầu chạy với ngưỡng thật để bệnh nhân có mặt trong DB, sau đó mới hạ ngưỡng.
    replay.publish_tick([subject])
    patient_id = wait_until(lambda: db.patient_id(subject), message=f"bệnh nhân {subject}")
    wait_until(lambda: db.one("SELECT count(*) FROM predictions WHERE patient_id = %s", (patient_id,)) >= 1)

    force_critical()  # ngưỡng 1e-6 → mọi giờ thành CRITICAL; consumer đọc lại alert_settings mỗi 1 giây trong test
    seen, hours_needed = alert_slate(patient_id)
    hours = [m.hour_index for m in replay.publish_hours([subject], hours_needed)]
    assert len(hours) == hours_needed >= 2

    wait_until(
        lambda: db.one(
            "SELECT count(*) FROM predictions WHERE patient_id = %s AND risk_level = 'CRITICAL' AND recorded_at >= "
            "(SELECT min(recorded_at) FROM vital_records WHERE patient_id = %s AND hour_index = %s)",
            (patient_id, patient_id, hours[0]),
        ) >= len(hours),
        message=f"{len(hours)} giờ CRITICAL liên tiếp",
    )
    alerts = [
        row for row in db.rows(
            "SELECT a.*, v.hour_index FROM alerts a JOIN vital_records v"
            " ON v.patient_id = a.patient_id AND v.recorded_at = a.prediction_recorded_at"
            " WHERE a.patient_id = %s ORDER BY v.hour_index", (patient_id,)
        ) if str(row["id"]) not in seen
    ]
    assert [a["alert_type"] for a in alerts] == ["RISK"], f"chỉ được 1 cảnh báo RISK mới, nhận {alerts}"
    assert alerts[0]["status"] == "OPEN"
    assert alerts[0]["hour_index"] == hours[0], "cảnh báo phải gắn với giờ CRITICAL đầu tiên"

    published = alerts_tap.collect_until(lambda got: any(e["value"]["alert_id"] == str(alerts[0]["id"]) for e in got))
    event = next(e["value"] for e in published if e["value"]["alert_id"] == str(alerts[0]["id"]))
    assert (event["alert_type"], event["status"], event["subject_id"]) == ("RISK", "OPEN", subject)
    assert event["risk_level"] == "CRITICAL"
    assert len([e for e in published if e["value"]["patient_id"] == str(patient_id)]) == 1


def test_duplicate_hour_is_skipped(replay, consumer, db, subjects):
    """Phát lại đúng giờ đã có → consumer bỏ qua, không tạo bản ghi hay prediction trùng (at-least-once)."""
    subject = subjects[0]
    patient_id = db.patient_id(subject)
    before = db.one("SELECT count(*) FROM vital_records WHERE patient_id = %s", (patient_id,))
    last = db.rows(
        "SELECT hour_index FROM vital_records WHERE patient_id = %s ORDER BY hour_index DESC LIMIT 1", (patient_id,)
    )[0]["hour_index"]

    replay.cursor[subject] -= 1  # phát lại chính giờ vừa gửi
    resent = replay.publish_tick([subject])
    assert resent[0].hour_index == last
    wait_until(
        lambda: f"bỏ qua BN-{subject} giờ {last}" in consumer.log_since_last_start(),
        message="log bỏ qua giờ trùng",
    )

    assert db.one("SELECT count(*) FROM vital_records WHERE patient_id = %s", (patient_id,)) == before
    assert db.one("SELECT count(*) FROM predictions WHERE patient_id = %s", (patient_id,)) == before
