"""E2E phi chức năng: chịu lỗi consumer và backend — 02_10 mục 2.10.4 dòng 2 và 3.

- Consumer bị giết cứng giữa lúc đang xử lý: dựng lại state từ DB, không bỏ sót bản ghi, không tạo cảnh báo trùng.
- Backend tắt trong lúc replay: consumer vẫn ghi DB; bật lại thì Kafka listener đọc tiếp từ offset đã commit nên
  không mất cảnh báo (bằng chứng: `notification_logs` của cảnh báo sinh ra lúc backend đang tắt).
"""

import pytest

from helpers import wait_until

HOURS = 8


@pytest.fixture(scope="module")
def subjects(replay) -> list[int]:
    return replay.take(2, offset=5)


def counts(db, patient_id) -> dict:
    return db.rows(
        "SELECT count(*) AS records, count(DISTINCT hour_index) AS hours FROM vital_records WHERE patient_id = %s",
        (patient_id,),
    )[0]


def test_consumer_restart_loses_no_record_and_duplicates_no_alert(replay, consumer, db, subjects, force_critical,
                                                                  alert_slate):
    """Giết cứng consumer giữa dòng dữ liệu rồi bật lại: đủ bản ghi, không trùng giờ, mỗi bệnh nhân vẫn 1 cảnh báo."""
    replay.publish_tick(subjects)
    patients = {
        subject: wait_until(lambda s=subject: db.patient_id(s), message=f"bệnh nhân {subject}")
        for subject in subjects
    }
    before = {subject: counts(db, patient_id)["records"] for subject, patient_id in patients.items()}
    seen = {subject: alert_slate(patient_id)[0] for subject, patient_id in patients.items()}

    force_critical()  # mọi giờ thành CRITICAL để kiểm tra luôn việc chống trùng cảnh báo sau khi khởi động lại
    replay.publish_hours(subjects, HOURS)
    # Chờ consumer xử lý được một phần rồi mới giết, để chắc chắn có message đang bay dở
    wait_until(
        lambda: counts(db, patients[subjects[0]])["records"] >= before[subjects[0]] + 2,
        message="consumer xử lý được vài giờ đầu",
    )
    consumer.restart(ready_timeout=300)

    for subject, patient_id in patients.items():
        expected = before[subject] + HOURS
        result = wait_until(
            lambda pid=patient_id, n=expected: counts(db, pid) if counts(db, pid)["records"] >= n else None,
            timeout=180, message=f"đủ {expected} bản ghi của BN-{subject}",
        )
        assert result["records"] == expected, f"BN-{subject} có {result['records']} bản ghi, chờ {expected}"
        assert result["hours"] == expected, "không được có giờ trùng"
        predictions = db.one("SELECT count(*) FROM predictions WHERE patient_id = %s", (patient_id,))
        assert predictions == expected, "mỗi bản ghi phải có đúng 1 prediction"
        alerts = [
            row for row in db.rows("SELECT id, alert_type FROM alerts WHERE patient_id = %s", (patient_id,))
            if str(row["id"]) not in seen[subject]
        ]
        assert [a["alert_type"] for a in alerts] == ["RISK"], f"BN-{subject} phải có đúng 1 cảnh báo RISK: {alerts}"

    assert "dựng lại state BN-" in consumer.log_since_last_start(), "consumer phải dựng lại state từ DB"


def test_backend_restart_keeps_alerts_from_kafka_offset(replay, consumer, backend, db, api_url, make_staff,
                                                        subjects, force_critical, alert_slate):
    """Backend tắt lúc đang replay: cảnh báo sinh ra trong lúc đó vẫn được xử lý sau khi backend bật lại."""
    subject = subjects[1]
    patient_id = db.patient_id(subject)
    doctor = make_staff("DOCTOR", [patient_id])
    force_critical()
    seen_alerts, hours_needed = alert_slate(patient_id)

    backend.kill()
    try:
        replay.publish_hours([subject], hours_needed)
        new_alert = wait_until(
            lambda: next(
                (row for row in db.rows("SELECT id FROM alerts WHERE patient_id = %s", (patient_id,))
                 if str(row["id"]) not in seen_alerts),
                None,
            ),
            timeout=180, message="consumer vẫn tạo cảnh báo khi backend đang tắt",
        )
        assert db.rows("SELECT * FROM notification_logs WHERE alert_id = %s", (new_alert["id"],)) == [], \
            "backend đang tắt thì chưa được có log email"
    finally:
        backend.start(ready_timeout=180)  # các test sau (và teardown của fixture) cần backend sống lại
    logs = wait_until(
        lambda: db.rows("SELECT * FROM notification_logs WHERE alert_id = %s", (new_alert["id"],)) or None,
        timeout=180, message="backend đọc tiếp từ offset cũ và xử lý cảnh báo bị bỏ lại",
    )
    assert {str(row["recipient_user_id"]) for row in logs} == {doctor["id"]}
    assert {row["status"] for row in logs} == {"SENT"}
