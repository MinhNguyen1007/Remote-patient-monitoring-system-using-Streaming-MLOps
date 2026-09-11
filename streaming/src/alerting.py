"""Logic sinh cảnh báo và chống bão cảnh báo — docs/design/02_9 mục 2.9.6, 02_3 mục 2.3.1.

Với mỗi cặp (bệnh nhân, loại cảnh báo), chỉ tạo cảnh báo mới khi:
  - điều kiện kích hoạt đúng (RISK: risk_level = CRITICAL; ANOMALY: anomaly_score ≥ τ_anomaly);
  - không còn cảnh báo cùng loại đang OPEN;
  - cảnh báo cùng loại gần nhất cách ít nhất `cooldown` giờ **dữ liệu**.
Mức WARNING không tạo cảnh báo.
"""

from dataclasses import dataclass

ALERT_TYPES = ("RISK", "ANOMALY")


@dataclass(frozen=True)
class AlertHistory:
    """Tóm tắt cảnh báo trước đó của một loại cho một bệnh nhân."""

    has_open: bool
    last_hour_index: int | None


def effective_risk_threshold(admin_threshold: float | None, champion_tau: float) -> float:
    """Ngưỡng Admin cấu hình (UC08) nếu có, ngược lại dùng τ_critical gắn kèm model champion."""
    return champion_tau if admin_threshold is None else admin_threshold


def alerts_to_create(
    triggered: dict[str, bool], hour_index: int, history: dict[str, AlertHistory], cooldown_hours: int
) -> list[str]:
    created = []
    for alert_type in ALERT_TYPES:
        if not triggered.get(alert_type, False):
            continue
        previous = history.get(alert_type)
        if previous is not None:
            if previous.has_open:
                continue
            if previous.last_hour_index is not None and hour_index - previous.last_hour_index < cooldown_hours:
                continue
        created.append(alert_type)
    return created
