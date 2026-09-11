import math

import numpy as np
import pandas as pd
import pytest

from rpm_ml.drift.stats import (
    CALIBRATION_FAMILY_FPR,
    DRIFT_FEATURES,
    PSI_SIGNIFICANT,
    bin_proportions,
    calibrate_thresholds,
    decide_drift,
    feature_drift,
    psi,
    reference_stats,
    replay_shaped_windows,
    select_window,
    window_skip_reason,
)


def test_psi_matches_hand_computed_value():
    expected = 0.25 * math.log(2) + 0.25 * math.log(1.5)
    assert psi([0.5, 0.5], [0.25, 0.75]) == pytest.approx(expected, abs=1e-4)


def test_psi_is_zero_for_identical_distributions():
    assert psi([0.2, 0.3, 0.5], [0.2, 0.3, 0.5]) == pytest.approx(0.0)


def test_empty_bins_use_epsilon_instead_of_failing():
    value = psi([0.5, 0.5, 0.0], [0.4, 0.4, 0.2])
    assert math.isfinite(value) and value > 0


def test_values_equal_to_an_edge_go_to_the_upper_bin():
    assert bin_proportions([1.0, 2.0, 3.0], np.array([2.0])).tolist() == [1 / 3, 2 / 3]


def _hourly(n, shift=0.0, seed=0):
    rng = np.random.default_rng(seed)
    return pd.DataFrame({feature: rng.normal(50 + shift, 10, n) for feature in DRIFT_FEATURES})


def test_shifted_stream_has_high_psi_and_same_distribution_has_low_psi():
    reference = reference_stats(_hourly(5000))
    same = feature_drift(reference, _hourly(2000, seed=1))
    shifted = feature_drift(reference, _hourly(2000, shift=15, seed=2))
    assert max(r["psi"] for r in same.values()) < 0.1
    assert min(r["psi"] for r in shifted.values()) >= 0.25
    assert min(r["ks_statistic"] for r in shifted.values()) > max(r["ks_statistic"] for r in same.values())


def test_decide_drift_uses_per_feature_threshold_with_floor():
    stats = {"heart_rate": {"psi": 0.9}, "spo2": {"psi": 0.3}, "temperature": {"psi": 0.2}}
    drifted, features = decide_drift(stats, {"heart_rate": 1.4, "spo2": 0.1, "temperature": 0.1})
    # heart_rate dưới ngưỡng hiệu chỉnh 1,4; spo2 vượt sàn 0,25 (ngưỡng hiệu chỉnh 0,1 thấp hơn sàn); temperature < sàn
    assert drifted and features == ["spo2"]
    assert stats["spo2"]["threshold"] == PSI_SIGNIFICANT and stats["heart_rate"]["threshold"] == 1.4
    assert [stats[f]["level"] for f in ("heart_rate", "spo2", "temperature")] == ["significant", "significant", "moderate"]


def test_decide_drift_without_any_exceedance():
    drifted, features = decide_drift({"heart_rate": {"psi": 0.5}}, {"heart_rate": 0.8})
    assert not drifted and features == []


def test_select_window_takes_latest_replay_ticks():
    ticks = pd.date_range("2026-09-11", periods=30, freq="5s", tz="UTC")
    hourly = pd.DataFrame(
        {"recorded_at": list(ticks) * 2 + [pd.NaT], "patient": [1] * 30 + [2] * 30 + [2], "heart_rate": 80.0}
    )
    window = select_window(hourly, hours=24)
    assert len(window) == 48
    assert window["recorded_at"].min() == ticks[6] and window["recorded_at"].max() == ticks[-1]


def _stays(lengths, seed=0):
    rng = np.random.default_rng(seed)
    frames = []
    for i, length in enumerate(lengths):
        frame = pd.DataFrame({feature: rng.normal(50 + rng.normal(0, 5), 10, length) for feature in DRIFT_FEATURES})
        frames.append(frame.assign(icustay_id=i, subject_id=i, hour_index=np.arange(length)))
    return frames


def test_replay_shaped_windows_start_at_hour_zero_and_stop_below_min_records():
    stays = _stays([30, 60, 100])
    windows = list(replay_shaped_windows(stays, min_records=50))
    # nhịp 24: 24 + 24 + 24 = 72; nhịp 28: 24 + 24 + 24; nhịp 32: 22 + 24 + 24 = 70; ... dừng khi < 50
    assert len(windows[0]) == 72
    assert all(len(w) >= 50 for w in windows)
    assert len(windows) < len(range(24, 101, 4))


def test_calibrated_thresholds_respect_floor_and_target_false_positive_rate(monkeypatch):
    import rpm_ml.drift.stats as drift

    monkeypatch.setattr(drift, "CALIBRATION_REPEATS", 20)
    monkeypatch.setattr(drift, "MIN_WINDOW_RECORDS", 100)
    dev = pd.concat(_stays([40 + 7 * (i % 9) for i in range(40)], seed=3), ignore_index=True)
    calibration = calibrate_thresholds(dev, seed=1)
    thresholds = calibration["thresholds"]
    assert set(thresholds) == set(DRIFT_FEATURES)
    assert min(thresholds.values()) >= PSI_SIGNIFICANT
    assert calibration["family_false_positive_rate"] <= CALIBRATION_FAMILY_FPR + 1e-9
    assert calibration["null_windows"] > 0


def _window(ticks: int, patients: int, start="2026-09-11"):
    times = pd.date_range(start, periods=ticks, freq="5s", tz="UTC")
    return pd.DataFrame({"recorded_at": [t for t in times for _ in range(patients)]})


def test_window_needs_24_ticks_new_data_and_200_records():
    # Đầu lần phát lại: 16 nhịp × 20 bệnh nhân = 320 bản ghi nhưng chưa đủ 24 giờ → bỏ qua
    assert "16 giờ" in window_skip_reason(_window(16, 20))
    assert "bản ghi" in window_skip_reason(_window(24, 8))
    full = _window(24, 20)
    assert window_skip_reason(full) is None
    assert "dữ liệu mới" in window_skip_reason(full, last_window_end=full["recorded_at"].max())
    assert window_skip_reason(full, last_window_end=full["recorded_at"].max() - pd.Timedelta(seconds=5)) is None
