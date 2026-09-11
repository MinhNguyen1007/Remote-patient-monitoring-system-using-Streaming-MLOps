"""Định dạng message JSON trên 3 topic Kafka — docs/design/02_9 mục 2.9.1(g), 02_4 mục 2.4.1.

- `vitals-stream` (producer → consumer): key = mã bệnh nhân (`subject_id` MIMIC), giá trị đo **chưa điền**.
- `predictions-stream`, `alerts-stream` (consumer → backend): key = `patient_id` (UUID trong DB).
"""

import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime

from rpm_common.itemids import VITALS


def _clean(value):
    """NaN → None, kiểu numpy → kiểu Python, áp dụng cả trong dict/list lồng nhau, để JSON hợp lệ."""
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        value = value.item()
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


@dataclass(frozen=True)
class VitalsMessage:
    subject_id: int
    icustay_id: int
    age: int | None
    gender: str | None
    hour_index: int
    recorded_at: str
    source_charttime: str | None
    vitals: dict[str, float | None]
    drift_applied: bool = False

    @property
    def key(self) -> str:
        return str(self.subject_id)

    def to_json(self) -> bytes:
        return json.dumps(asdict(self)).encode("utf-8")

    @classmethod
    def from_json(cls, raw: bytes) -> "VitalsMessage":
        data = json.loads(raw)
        data["vitals"] = {v: _clean(data["vitals"].get(v)) for v in VITALS}
        return cls(**data)

    @property
    def recorded_at_dt(self) -> datetime:
        return datetime.fromisoformat(self.recorded_at)


def event_json(payload: dict) -> bytes:
    return json.dumps(_clean(payload), default=str, allow_nan=False).encode("utf-8")
