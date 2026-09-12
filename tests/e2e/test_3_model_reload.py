"""E2E: đổi alias `champion` trên MLflow → consumer nạp version mới — 02_10 mục 2.10.2 dòng 6 (Sequence 2.4.3).

Test này **đổi tạm** alias `champion` của `risk_classifier` rồi trả lại đúng version ban đầu trong teardown (kể cả
khi assert thất bại). Registry MLflow là trạng thái thật dùng chung, nên fixture `champion_alias` là nơi duy nhất
được phép ghi vào nó.
"""

import pytest

from conftest import MLFLOW_URI
from helpers import wait_until

RISK_MODEL = "risk_classifier"


@pytest.fixture(scope="module")
def mlflow_client():
    from mlflow import MlflowClient

    return MlflowClient(MLFLOW_URI)


@pytest.fixture
def champion_alias(mlflow_client):
    """Cho phép trỏ alias `champion` sang version khác; luôn trả lại version ban đầu khi test kết thúc."""
    original = mlflow_client.get_model_version_by_alias(RISK_MODEL, "champion").version

    def switch_to(version: str) -> None:
        mlflow_client.set_registered_model_alias(RISK_MODEL, "champion", version)

    def other_version() -> str:
        versions = sorted(
            (v.version for v in mlflow_client.search_model_versions(f"name='{RISK_MODEL}'")), key=int, reverse=True
        )
        candidate = next((v for v in versions if v != original), None)
        if candidate is None:
            pytest.skip(f"registry chỉ có 1 version {RISK_MODEL}, không kiểm tra được việc nạp lại")
        return candidate

    yield switch_to, original, other_version
    mlflow_client.set_registered_model_alias(RISK_MODEL, "champion", original)
    assert mlflow_client.get_model_version_by_alias(RISK_MODEL, "champion").version == original


@pytest.fixture(scope="module")
def subject(replay) -> int:
    return replay.take(1, offset=4)[0]


def risk_version_of_last_prediction(db, patient_id) -> str:
    row = db.rows(
        "SELECT m.mlflow_version FROM predictions p JOIN model_versions m ON m.id = p.risk_model_version_id"
        " WHERE p.patient_id = %s ORDER BY p.recorded_at DESC LIMIT 1", (patient_id,)
    )
    return row[0]["mlflow_version"] if row else None


def gate_row(db, version: str) -> dict | None:
    rows = db.rows(
        "SELECT gate_status, gate_reasons, is_champion FROM model_versions"
        " WHERE model_name = %s AND mlflow_version = %s", (RISK_MODEL, version)
    )
    return rows[0] if rows else None


def test_consumer_reloads_champion_within_one_refresh_cycle(replay, consumer, db, subject, champion_alias):
    switch_to, original, other_version = champion_alias

    replay.publish_tick([subject])
    patient_id = wait_until(lambda: db.patient_id(subject), message=f"bệnh nhân {subject}")
    wait_until(lambda: risk_version_of_last_prediction(db, patient_id), message="prediction đầu tiên")
    assert risk_version_of_last_prediction(db, patient_id) == original

    replacement = other_version()
    gate_before = gate_row(db, replacement)
    switch_to(replacement)
    wait_until(
        lambda: f"đã nạp {RISK_MODEL} v{replacement}" in consumer.log_since_last_start(),
        timeout=180, message=f"consumer nạp {RISK_MODEL} v{replacement}",
    )

    replay.publish_tick([subject])
    wait_until(
        lambda: risk_version_of_last_prediction(db, patient_id) == replacement,
        message=f"prediction ghi version {replacement}",
    )
    # Cờ champion trong model_versions đi theo alias (tab Giám sát mô hình của Admin đọc cột này)
    champions = db.rows(
        "SELECT mlflow_version, is_champion FROM model_versions WHERE model_name = %s AND is_champion", (RISK_MODEL,)
    )
    assert [row["mlflow_version"] for row in champions] == [replacement]

    # Nhưng kết luận của quality gate thì KHÔNG được đổi theo alias: đổi alias sang một version đã bị gate từ chối
    # không biến nó thành PROMOTED, nếu không tab Giám sát mô hình sẽ báo sai lý do gate.
    gate_after = gate_row(db, replacement)
    if gate_before is not None:
        assert (gate_after["gate_status"], gate_after["gate_reasons"]) == \
            (gate_before["gate_status"], gate_before["gate_reasons"]), \
            "đổi alias champion không được ghi đè gate_status/gate_reasons"

    switch_to(original)
    wait_until(
        lambda: consumer.log_since_last_start().count(f"đã nạp {RISK_MODEL} v{original}") >= 2,
        timeout=180, message=f"consumer nạp lại {RISK_MODEL} v{original}",
    )
    replay.publish_tick([subject])
    wait_until(
        lambda: risk_version_of_last_prediction(db, patient_id) == original,
        message=f"prediction quay lại version {original}",
    )
