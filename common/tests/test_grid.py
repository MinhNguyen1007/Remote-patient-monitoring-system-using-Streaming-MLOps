import numpy as np
import pandas as pd

from rpm_common.grid import to_hourly_grid


def _long(rows):
    df = pd.DataFrame(rows, columns=["icustay_id", "charttime", "vital", "value"])
    df["charttime"] = pd.to_datetime(df["charttime"])
    return df


def test_hourly_median_and_continuous_hours():
    grid = to_hourly_grid(
        _long(
            [
                (1, "2150-01-01 10:05", "heart_rate", 80),
                (1, "2150-01-01 10:40", "heart_rate", 90),
                (1, "2150-01-01 13:10", "heart_rate", 100),
            ]
        )
    )
    assert grid["hour_index"].tolist() == [0, 1, 2, 3]
    assert grid["heart_rate_obs"].tolist()[0] == 85
    assert np.isnan(grid["heart_rate_obs"].iloc[1])
    assert grid["heart_rate_obs"].iloc[3] == 100


def test_forward_fill_limits_two_hours_for_vitals_and_six_for_temperature():
    grid = to_hourly_grid(
        _long(
            [
                (1, "2150-01-01 00:00", "heart_rate", 80),
                (1, "2150-01-01 00:00", "temperature", 37.0),
                (1, "2150-01-01 09:00", "spo2", 97),
            ]
        )
    )
    assert grid["heart_rate"].notna().tolist()[:4] == [True, True, True, False]
    assert grid["temperature"].notna().tolist()[:8] == [True] * 7 + [False]


def test_never_fills_backward():
    grid = to_hourly_grid(
        _long([(1, "2150-01-01 00:00", "spo2", 97), (1, "2150-01-01 02:00", "heart_rate", 80)])
    )
    assert grid["heart_rate"].isna().tolist() == [True, True, False]


def test_forward_fill_does_not_cross_stays():
    grid = to_hourly_grid(
        _long(
            [
                (1, "2150-01-01 00:00", "heart_rate", 80),
                (2, "2150-01-01 01:00", "spo2", 97),
                (2, "2150-01-01 02:00", "heart_rate", 90),
            ]
        )
    )
    stay2 = grid[grid["icustay_id"] == 2]
    assert stay2["hour_index"].tolist() == [0, 1]
    assert np.isnan(stay2["heart_rate"].iloc[0])
