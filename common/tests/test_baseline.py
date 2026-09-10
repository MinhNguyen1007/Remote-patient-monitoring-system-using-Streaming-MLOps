import numpy as np
import pytest

from rpm_common.pipeline import build_hourly_features


def test_zscore_is_missing_before_six_hours(grid_factory):
    features = build_hourly_features(grid_factory(8))
    assert features["heart_rate_z"].iloc[:5].isna().all()
    assert features["heart_rate_z"].iloc[5:].notna().all()
    assert features["baseline_ready"].tolist() == [False] * 5 + [True] * 3


def test_baseline_is_frozen_after_24_hours(grid_factory):
    hr = [80.0] * 24 + [120.0] * 7
    features = build_hourly_features(grid_factory(31, overrides={"heart_rate": hr}))
    # std trong 24 giờ đầu bằng 0 nên dùng sàn 5 bpm
    assert features["heart_rate_z"].iloc[30] == pytest.approx((120.0 - 80.0) / 5.0)


def test_std_floor_prevents_zscore_blow_up(grid_factory):
    spo2 = [98.0] * 25 + [96.0]
    features = build_hourly_features(grid_factory(26, overrides={"spo2": spo2}))
    assert features["spo2_z"].iloc[25] == pytest.approx(-2.0)


def test_baseline_uses_real_spread_when_above_floor(grid_factory):
    hr = [70.0, 90.0] * 12 + [100.0]
    features = build_hourly_features(grid_factory(25, overrides={"heart_rate": hr}))
    std = np.std([70.0, 90.0] * 12, ddof=1)
    assert features["heart_rate_z"].iloc[24] == pytest.approx((100.0 - 80.0) / std)
