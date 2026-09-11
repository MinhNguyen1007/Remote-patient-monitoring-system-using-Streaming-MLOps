from datetime import datetime, timedelta, timezone

from rpm_ml.pipelines.policy import (
    PUBLISH_TASK,
    TRIGGER_TASK,
    branch_targets,
    retrain_block_reason,
    should_notify_admin,
)

NOW = datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc)


def test_no_previous_retrain_allows_trigger():
    assert retrain_block_reason([], NOW) is None


def test_running_or_queued_retrain_blocks_trigger():
    assert "đang có" in retrain_block_reason([("running", None)], NOW)
    assert "đang có" in retrain_block_reason([("success", NOW - timedelta(hours=5)), ("queued", None)], NOW)


def test_retrain_finished_within_one_hour_blocks_trigger():
    reason = retrain_block_reason([("success", NOW - timedelta(minutes=59))], NOW)
    assert reason is not None and "59 phút" in reason
    # Lần thất bại cũng tính: tránh kích hoạt liên tục một pipeline đang lỗi
    assert retrain_block_reason([("failed", NOW - timedelta(minutes=10))], NOW) is not None


def test_retrain_finished_more_than_one_hour_ago_allows_trigger():
    runs = [("success", NOW - timedelta(hours=3)), ("failed", NOW - timedelta(hours=1, minutes=1))]
    assert retrain_block_reason(runs, NOW) is None


def test_immediate_second_check_does_not_trigger_again():
    """02_10 mục 2.10.2: kiểm tra ngay sau khi vừa trigger thì run mới đang queued → không trigger lần 2."""
    detect = {"status": "checked", "drift_detected": True}
    assert branch_targets(detect, retrain_block_reason([], NOW)) == [TRIGGER_TASK, PUBLISH_TASK]
    assert branch_targets(detect, retrain_block_reason([("queued", None)], NOW)) == [PUBLISH_TASK]


def test_branch_targets_by_detect_result():
    assert branch_targets({"status": "skipped", "reason": "..."}, None) == []
    assert branch_targets({"status": "checked", "drift_detected": False}, None) == [PUBLISH_TASK]


def test_admin_email_only_at_start_of_drift_episode_or_when_retrain_triggered():
    assert should_notify_admin(True, previous_drift_detected=None, triggered_retrain=False)
    assert should_notify_admin(True, previous_drift_detected=False, triggered_retrain=False)
    # Drift kéo dài, không kích hoạt thêm retrain (bị chặn chống vòng lặp) → không gửi lặp
    assert not should_notify_admin(True, previous_drift_detected=True, triggered_retrain=False)
    assert should_notify_admin(True, previous_drift_detected=True, triggered_retrain=True)
    assert not should_notify_admin(False, previous_drift_detected=True, triggered_retrain=False)
