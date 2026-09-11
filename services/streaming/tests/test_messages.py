import json
import math
import uuid

import numpy as np

from rpm_streaming.kafka.messages import VitalsMessage, event_json
from rpm_common.itemids import VITALS


def test_vitals_message_roundtrip_keeps_missing_values_as_none():
    message = VitalsMessage(
        subject_id=10032, icustay_id=1, age=88, gender="M", hour_index=3,
        recorded_at="2026-09-11T10:00:00+00:00", source_charttime=None,
        vitals={v: None for v in VITALS} | {"heart_rate": 101.5},
    )
    parsed = VitalsMessage.from_json(message.to_json())
    assert parsed == message
    assert message.key == "10032"


def test_event_json_is_strict_json_without_nan_and_with_numpy_values():
    payload = {"id": uuid.uuid4(), "score": np.float64(0.5), "nested": {"hr": float("nan"), "flag": np.bool_(True)}}
    data = json.loads(event_json(payload))
    assert data["score"] == 0.5
    assert data["nested"] == {"hr": None, "flag": True}
    assert not any(isinstance(v, float) and math.isnan(v) for v in data["nested"].values())
