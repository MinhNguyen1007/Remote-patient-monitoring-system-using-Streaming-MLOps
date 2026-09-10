import numpy as np
import pandas as pd
import pytest

from rpm_common.baseline import ZSCORE_COLUMNS
from rpm_common.features import RISK_FEATURE_COLUMNS, WINDOW_FEATURE_COLUMNS, compute_age_years
from rpm_common.grid import fill_forward
from rpm_common.itemids import VITALS, obs_col
from rpm_common.pipeline import build_hourly_features


def test_slope_of_linear_series_is_its_rate_per_hour(grid_factory):
    hr = [60.0 + 2.0 * h for h in range(10)]
    features = build_hourly_features(grid_factory(10, overrides={"heart_rate": hr}))
    slope = features["heart_rate_slope_6h"]
    assert slope.iloc[:2].isna().all()
    assert np.allclose(slope.iloc[2:], 2.0)


def test_window_statistics_need_three_observations(grid_factory):
    hr = [80.0, np.nan, np.nan, 90.0, np.nan, np.nan, np.nan, np.nan]
    features = build_hourly_features(grid_factory(8, overrides={"heart_rate": hr}))
    assert features[["heart_rate_mean_6h", "heart_rate_std_6h", "heart_rate_slope_6h"]].isna().all().all()


def test_window_mean_and_std_use_last_six_observed_hours(grid_factory):
    hr = [70.0, 72.0, 74.0, 90.0, 76.0, 78.0, 80.0, 82.0]
    features = build_hourly_features(grid_factory(8, overrides={"heart_rate": hr}))
    window = np.array(hr[2:8])
    assert features["heart_rate_mean_6h"].iloc[7] == pytest.approx(window.mean())
    assert features["heart_rate_std_6h"].iloc[7] == pytest.approx(window.std(ddof=1))


def test_delta_uses_filled_values(grid_factory):
    hr = [80.0, np.nan, 86.0]
    features = build_hourly_features(grid_factory(3, overrides={"heart_rate": hr}))
    assert features["heart_rate_delta_1h"].tolist()[1:] == [0.0, 6.0]


def test_features_at_hour_t_do_not_depend_on_later_data():
    rng = np.random.default_rng(0)
    n, cut = 40, 20
    base = {
        "heart_rate": rng.normal(85, 15, n),
        "spo2": rng.normal(95, 3, n).clip(80, 100),
        "respiratory_rate": rng.normal(19, 5, n).clip(5, 40),
        "systolic_bp": rng.normal(115, 20, n),
        "diastolic_bp": rng.normal(60, 10, n),
        "temperature": rng.normal(37.2, 0.8, n),
    }
    frame = pd.DataFrame({"icustay_id": 1, "hour_index": np.arange(n)})
    for vital, values in base.items():
        values = values.copy()
        values[rng.random(n) < 0.3] = np.nan
        frame[obs_col(vital)] = values

    changed = frame.copy()
    for vital in VITALS:
        changed.loc[changed["hour_index"] > cut, obs_col(vital)] = rng.normal(150, 30, n - cut - 1)

    original = build_hourly_features(fill_forward(frame))
    perturbed = build_hourly_features(fill_forward(changed))
    columns = list(WINDOW_FEATURE_COLUMNS) + list(ZSCORE_COLUMNS) + ["news2_score", "risk_class"]
    pd.testing.assert_frame_equal(original.loc[:cut, columns], perturbed.loc[:cut, columns])


def test_risk_feature_columns_exist_after_pipeline(grid_factory):
    features = build_hourly_features(grid_factory(5)).assign(age=60.0, gender_male=1.0)
    assert set(RISK_FEATURE_COLUMNS) <= set(features.columns)


def test_age_is_capped_for_shifted_birth_dates_and_counts_birthdays():
    dob = pd.Series(["1850-03-01", "2100-06-15"])
    reference = pd.Series(["2150-01-01", "2150-06-14"])
    assert compute_age_years(dob, reference).tolist() == [90.0, 49.0]
