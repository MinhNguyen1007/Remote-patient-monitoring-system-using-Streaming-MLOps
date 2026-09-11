from datetime import datetime, timedelta, timezone
from uuid import uuid4

import numpy as np
import pandas as pd
import pytest

from config import REPO_ROOT
from patient_state import PatientState
from rpm_common.anomaly import WINDOW_HOURS
from rpm_common.baseline import BASELINE_MIN_HOURS, ZSCORE_COLUMNS
from rpm_common.features import RISK_FEATURE_COLUMNS
from rpm_common.itemids import VITALS, obs_col

PROCESSED = REPO_ROOT / "ml" / "data" / "processed"
T0 = datetime(2026, 9, 11, tzinfo=timezone.utc)


def make_state(**kwargs) -> PatientState:
    return PatientState(uuid4(), 1, 11, 70.0, 1.0, **kwargs)


def feed(state: PatientState, stay: pd.DataFrame, upto: int) -> None:
    for _, row in stay.iloc[len(state.rows):upto].iterrows():
        vitals = {v: None if pd.isna(row[obs_col(v)]) else row[obs_col(v)] for v in VITALS}
        state.append(int(row["hour_index"]), T0 + timedelta(hours=int(row["hour_index"])), vitals)


@pytest.mark.skipif(not (PROCESSED / "stream_replay.parquet").exists(), reason="chưa chạy ml/src/preprocess.py")
def test_online_features_match_training_features_hour_by_hour():
    """Chống lệch train/serving: đặc trưng consumer tính từng giờ = dòng tương ứng trong hourly.parquet."""
    replay = pd.read_parquet(PROCESSED / "stream_replay.parquet")
    hourly = pd.read_parquet(PROCESSED / "hourly.parquet")
    columns = list(RISK_FEATURE_COLUMNS) + list(ZSCORE_COLUMNS) + ["news2_score", "risk_class"]
    for stay_id in replay["icustay_id"].unique()[:3]:
        stay = replay[replay["icustay_id"] == stay_id].sort_values("hour_index")
        expected = hourly[hourly["icustay_id"] == stay_id].set_index("hour_index", drop=False)
        first = stay.iloc[0]
        state = PatientState(uuid4(), int(first["subject_id"]), int(stay_id), first["age"], first["gender_male"])
        for upto in sorted({1, 5, 13, 30, len(stay)} & set(range(1, len(stay) + 1))):
            feed(state, stay, upto)
            online = state.features().iloc[-1]
            reference = expected.loc[online["hour_index"], columns]
            pd.testing.assert_series_equal(
                online[columns].astype(float), reference.astype(float), check_names=False, atol=1e-9
            )


def test_append_rejects_hours_not_newer_than_last():
    state = make_state()
    state.append(0, T0, {"heart_rate": 80.0})
    with pytest.raises(ValueError):
        state.append(0, T0, {"heart_rate": 81.0})


def test_missing_hours_are_treated_as_unmeasured_hours():
    state = make_state()
    state.append(0, T0, {v: 80.0 for v in VITALS})
    state.append(3, T0 + timedelta(hours=3), {v: 80.0 for v in VITALS})
    features = state.features()
    assert features["hour_index"].tolist() == [0, 1, 2, 3]
    # Forward-fill tối đa 2 giờ: giờ 1, 2 được điền, không điền ngược
    assert features["heart_rate"].tolist() == [80.0, 80.0, 80.0, 80.0]
    assert np.isnan(features.loc[1, obs_col("heart_rate")])


def test_anomaly_window_first_available_at_hour_index_16():
    """Baseline dùng được từ hour_index 5 (≥ 6 giờ), cộng cửa sổ 12 giờ z-score → sớm nhất ở hour_index 16."""
    state = make_state()
    normal = {"heart_rate": 75.0, "spo2": 98.0, "respiratory_rate": 16.0, "systolic_bp": 120.0,
              "diastolic_bp": 70.0, "temperature": 37.0}
    rng = np.random.default_rng(0)
    first_scored = None
    for hour in range(WINDOW_HOURS + 8):
        state.append(hour, T0 + timedelta(hours=hour), {k: v + rng.normal() for k, v in normal.items()})
        window = state.current_window(state.features())
        if window is not None and first_scored is None:
            first_scored = hour
    assert first_scored == BASELINE_MIN_HOURS - 1 + WINDOW_HOURS - 1 == 16
    assert window.shape == (1, WINDOW_HOURS, len(VITALS))
