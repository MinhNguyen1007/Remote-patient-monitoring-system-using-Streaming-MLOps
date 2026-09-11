"""Quy tắc quyết định của DAG drift_check — docs/design/02_9 mục 2.9.4–2.9.5, 02_3 mục 2.3.3.

Chỉ dùng thư viện chuẩn: file DAG (môi trường Python của Airflow, không có thư viện ML) import trực tiếp module này.
"""

from collections.abc import Iterable
from datetime import datetime, timedelta

RETRAIN_COOLDOWN = timedelta(hours=1)
ACTIVE_RUN_STATES = frozenset({"queued", "running"})

TRIGGER_TASK = "trigger_retrain"
PUBLISH_TASK = "publish_report"


def retrain_block_reason(
    runs: Iterable[tuple[str, datetime | None]], now: datetime, cooldown: timedelta = RETRAIN_COOLDOWN
) -> str | None:
    """Chống vòng lặp: không tự kích hoạt khi đang có retrain chạy hoặc lần gần nhất kết thúc chưa quá `cooldown`.

    `runs` là (trạng thái, thời điểm kết thúc) của mọi lần chạy DAG retrain_pipeline, kể cả lần do Admin kích hoạt.
    """
    runs = list(runs)
    if any(str(state) in ACTIVE_RUN_STATES for state, _ in runs):
        return "đang có một lần retrain chạy"
    ended = [end for _, end in runs if end is not None]
    if ended and now - max(ended) < cooldown:
        minutes = int((now - max(ended)).total_seconds() // 60)
        required = int(cooldown.total_seconds() // 60)
        return f"lần retrain gần nhất mới kết thúc {minutes} phút trước (cần cách ít nhất {required} phút)"
    return None


def branch_targets(detect_result: dict, block_reason: str | None) -> list[str]:
    """Task chạy tiếp sau khi kiểm tra drift.

    - Bỏ qua lần kiểm tra (không ghi báo cáo): dừng.
    - Có báo cáo: luôn publish để tab Giám sát mô hình cập nhật; thêm trigger retrain khi có drift và không bị chặn.
    """
    if detect_result.get("status") != "checked":
        return []
    if detect_result.get("drift_detected") and block_reason is None:
        return [TRIGGER_TASK, PUBLISH_TASK]
    return [PUBLISH_TASK]


def should_notify_admin(drift_detected: bool, previous_drift_detected: bool | None, triggered_retrain: bool) -> bool:
    """Email Admin khi bắt đầu một đợt drift mới (lần kiểm tra trước không có drift) hoặc khi đã kích hoạt retrain.

    Drift kéo dài (vd challenger bị gate từ chối nên PSI vẫn cao) không gửi lặp mỗi lần kiểm tra — cùng tinh thần chống
    bão cảnh báo ở mục 2.9.6. Mọi lần kiểm tra vẫn được ghi drift_reports và đẩy lên giao diện.
    """
    return bool(drift_detected and (triggered_retrain or not previous_drift_detected))
