import json

import numpy as np
import pandas as pd

from producer import DRIFT_SHIFTS, apply_drift, choose_drift_subjects, replay
from rpm_common.itemids import VITALS, obs_col


class FakeProducer:
    def __init__(self):
        self.sent = []

    def produce(self, topic, key, value):
        self.sent.append((topic, key, json.loads(value)))

    def poll(self, timeout):
        return 0

    def flush(self, timeout=None):
        return 0


def make_stay(subject_id: int, hours: int) -> pd.DataFrame:
    data = {
        "subject_id": subject_id, "icustay_id": subject_id * 10, "hour_index": np.arange(hours),
        "source_charttime": pd.date_range("2130-01-01", periods=hours, freq="h"), "age": 70.0, "gender_male": 1.0,
    }
    for v in VITALS:
        data[obs_col(v)] = 80.0
    data[obs_col("spo2")] = 99.0
    data[obs_col("temperature")] = np.nan
    return pd.DataFrame(data)


def test_replay_sends_hour_k_of_every_patient_in_step_k_with_subject_key():
    producer, clock = FakeProducer(), iter(range(1000))
    stays = {1: make_stay(1, 3), 2: make_stay(2, 1)}
    sent = replay(producer, "vitals", stays, 0.0, set(), clock=lambda: next(clock), sleep=lambda s: None)
    assert sent == 4
    assert [(key, msg["hour_index"]) for _, key, msg in producer.sent] == [("1", 0), ("2", 0), ("1", 1), ("1", 2)]
    assert producer.sent[0][2]["vitals"]["temperature"] is None
    assert producer.sent[0][2]["gender"] == "M"


def test_drift_applies_only_to_chosen_subjects_and_clips_spo2():
    producer, clock = FakeProducer(), iter(range(1000))
    replay(producer, "vitals", {1: make_stay(1, 1), 2: make_stay(2, 1)}, 0.0, {2}, clock=lambda: next(clock), sleep=lambda s: None)
    by_key = {key: msg for _, key, msg in producer.sent}
    assert by_key["1"]["vitals"]["heart_rate"] == 80.0 and not by_key["1"]["drift_applied"]
    assert by_key["2"]["vitals"]["heart_rate"] == 80.0 + DRIFT_SHIFTS["heart_rate"] and by_key["2"]["drift_applied"]
    assert apply_drift({"spo2": 99.0, "heart_rate": None})["spo2"] == 96.0
    assert apply_drift({"spo2": 101.0})["spo2"] == 98.0


def test_drift_subject_choice_is_deterministic_and_sized_by_fraction():
    subjects = list(range(20))
    assert choose_drift_subjects(subjects, 0.5, 42) == choose_drift_subjects(subjects, 0.5, 42)
    assert len(choose_drift_subjects(subjects, 0.5, 42)) == 10
    assert choose_drift_subjects(subjects, 0.0, 42) == set()
