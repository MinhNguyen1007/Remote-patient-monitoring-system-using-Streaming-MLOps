import numpy as np
import pandas as pd
import pytest

from rpm_common.anomaly import (
    WINDOW_HOURS,
    anomaly_score_from_mse,
    center_windows,
    latest_window,
    make_windows,
    reconstruction_mse,
)
from rpm_common.baseline import ZSCORE_COLUMNS
from rpm_common.news2 import RISK_CRITICAL, RISK_NORMAL


def make_hourly(n_hours: int, stay_id: int = 1, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    data = {"icustay_id": stay_id, "hour_index": np.arange(n_hours), "risk_class": RISK_NORMAL}
    for col in ZSCORE_COLUMNS:
        data[col] = rng.normal(size=n_hours)
    return pd.DataFrame(data)


def test_one_window_per_hour_from_hour_12_within_a_stay():
    windows, meta = make_windows(make_hourly(20))
    assert windows.shape == (20 - WINDOW_HOURS + 1, WINDOW_HOURS, len(ZSCORE_COLUMNS))
    assert windows.dtype == np.float32
    assert meta["hour_index"].tolist() == list(range(WINDOW_HOURS - 1, 20))
    assert meta["all_normal"].all()


def test_window_holds_the_12_hours_ending_at_t_in_channel_order():
    hourly = make_hourly(15)
    windows, meta = make_windows(hourly)
    last = meta.index[meta["hour_index"] == 14][0]
    expected = hourly.loc[3:14, list(ZSCORE_COLUMNS)].to_numpy(dtype=np.float32)
    np.testing.assert_allclose(windows[last], expected)


def test_window_at_t_does_not_depend_on_hours_after_t():
    hourly = make_hourly(30)
    changed = hourly.copy()
    changed.loc[changed["hour_index"] > 20, list(ZSCORE_COLUMNS)] = 99.0
    a, meta_a = make_windows(hourly)
    b, meta_b = make_windows(changed)
    upto = (meta_a["hour_index"] <= 20).to_numpy()
    np.testing.assert_array_equal(a[upto], b[(meta_b["hour_index"] <= 20).to_numpy()])


def test_windows_with_missing_zscore_are_dropped():
    hourly = make_hourly(20)
    hourly.loc[hourly["hour_index"] == 15, "spo2_z"] = np.nan
    _, meta = make_windows(hourly)
    # Mọi cửa sổ chứa giờ 15 (kết thúc ở 15 … 19) bị bỏ
    assert meta["hour_index"].tolist() == [11, 12, 13, 14]


def test_windows_never_span_two_stays_and_short_stays_have_none():
    hourly = pd.concat([make_hourly(13, stay_id=1), make_hourly(11, stay_id=2), make_hourly(12, stay_id=3)])
    hourly = hourly.reset_index(drop=True)
    _, meta = make_windows(hourly)
    assert meta.groupby("icustay_id").size().to_dict() == {1: 2, 3: 1}


def test_row_points_to_last_hour_of_window_in_original_index():
    hourly = make_hourly(14)
    hourly.index = hourly.index + 1000
    _, meta = make_windows(hourly)
    assert hourly.loc[meta["row"], "hour_index"].tolist() == meta["hour_index"].tolist()


def test_all_normal_false_if_any_hour_not_normal_or_unknown():
    hourly = make_hourly(14)
    hourly.loc[hourly["hour_index"] == 0, "risk_class"] = RISK_CRITICAL
    hourly.loc[hourly["hour_index"] == 13, "risk_class"] = np.nan
    _, meta = make_windows(hourly)
    assert meta["all_normal"].tolist() == [False, True, False]


def test_latest_window_needs_12_scorable_hours():
    assert latest_window(make_hourly(WINDOW_HOURS - 1)) is None
    history = make_hourly(20)
    window = latest_window(history)
    assert window.shape == (1, WINDOW_HOURS, len(ZSCORE_COLUMNS))
    np.testing.assert_allclose(window[0], history.tail(WINDOW_HOURS)[list(ZSCORE_COLUMNS)].to_numpy(np.float32))
    history.loc[history.index[-1], "heart_rate_z"] = np.nan
    assert latest_window(history) is None


def test_center_windows_removes_per_channel_mean_but_keeps_shape():
    rng = np.random.default_rng(2)
    windows = rng.normal(size=(3, WINDOW_HOURS, len(ZSCORE_COLUMNS))).astype(np.float32)
    shifted = windows + np.arange(len(ZSCORE_COLUMNS), dtype=np.float32) * 5
    centered = center_windows(shifted)
    np.testing.assert_allclose(centered.mean(axis=1), 0, atol=1e-5)
    np.testing.assert_allclose(centered, center_windows(windows), atol=1e-5)
    np.testing.assert_allclose(np.diff(centered, axis=1), np.diff(windows, axis=1), atol=1e-5)


def test_reconstruction_mse_is_mean_over_steps_and_channels():
    x = np.zeros((2, 3, 2))
    x_hat = np.zeros((2, 3, 2))
    x_hat[1, 0, 0] = 6.0
    np.testing.assert_allclose(reconstruction_mse(x, x_hat), [0.0, 36.0 / 6])


def test_anomaly_score_is_empirical_cdf_of_reference():
    reference = [4.0, 1.0, 3.0, 2.0]
    scores = anomaly_score_from_mse([0.5, 1.0, 2.5, 4.0, 100.0], reference)
    np.testing.assert_allclose(scores, [0.0, 0.25, 0.5, 1.0, 1.0])


def test_anomaly_score_is_monotonic_and_in_unit_interval():
    rng = np.random.default_rng(1)
    reference = rng.gamma(2.0, size=500)
    mse = np.sort(rng.gamma(2.0, size=200))
    scores = anomaly_score_from_mse(mse, reference)
    assert np.all(np.diff(scores) >= 0)
    assert scores.min() >= 0 and scores.max() <= 1
    assert anomaly_score_from_mse([np.quantile(reference, 0.99)], reference)[0] == pytest.approx(0.99, abs=0.01)
