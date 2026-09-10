import numpy as np
import pandas as pd
import pytest

from rpm_common.news2 import RISK_CRITICAL, RISK_NORMAL, RISK_WARNING, compute_news2, score_parameter


@pytest.mark.parametrize(
    "param, value, expected",
    [
        ("respiratory_rate", 8, 3),
        ("respiratory_rate", 9, 1),
        ("respiratory_rate", 11, 1),
        ("respiratory_rate", 12, 0),
        ("respiratory_rate", 20, 0),
        ("respiratory_rate", 20.5, 2),
        ("respiratory_rate", 24, 2),
        ("respiratory_rate", 25, 3),
        ("spo2", 91, 3),
        ("spo2", 92, 2),
        ("spo2", 93, 2),
        ("spo2", 94, 1),
        ("spo2", 95, 1),
        ("spo2", 96, 0),
        ("systolic_bp", 90, 3),
        ("systolic_bp", 91, 2),
        ("systolic_bp", 100, 2),
        ("systolic_bp", 101, 1),
        ("systolic_bp", 110, 1),
        ("systolic_bp", 111, 0),
        ("systolic_bp", 219, 0),
        ("systolic_bp", 220, 3),
        ("heart_rate", 40, 3),
        ("heart_rate", 41, 1),
        ("heart_rate", 50, 1),
        ("heart_rate", 51, 0),
        ("heart_rate", 90, 0),
        ("heart_rate", 90.5, 1),
        ("heart_rate", 110, 1),
        ("heart_rate", 111, 2),
        ("heart_rate", 130, 2),
        ("heart_rate", 131, 3),
        ("temperature", 35.0, 3),
        ("temperature", 35.1, 1),
        ("temperature", 36.0, 1),
        ("temperature", 36.1, 0),
        ("temperature", 38.0, 0),
        ("temperature", 38.1, 1),
        ("temperature", 39.0, 1),
        ("temperature", 39.1, 2),
    ],
)
def test_score_parameter_boundaries(param, value, expected):
    assert score_parameter(param, [value])[0] == expected


def test_missing_value_gives_missing_score():
    assert np.isnan(score_parameter("heart_rate", [np.nan])[0])


def _news2(**overrides):
    row = {"respiratory_rate": 16, "spo2": 98, "systolic_bp": 120, "heart_rate": 75, "temperature": 37.0}
    row.update(overrides)
    return compute_news2(pd.DataFrame([row])).iloc[0]


def test_all_normal_vitals_are_normal():
    result = _news2()
    assert result["news2_score"] == 0
    assert result["risk_class"] == RISK_NORMAL


def test_single_parameter_scoring_three_is_warning_even_with_low_total():
    result = _news2(spo2=90)
    assert result["news2_score"] == 3
    assert result["news2_red_flag"] == 1
    assert result["risk_class"] == RISK_WARNING


def test_total_five_is_warning():
    result = _news2(respiratory_rate=22, heart_rate=115, temperature=38.5)
    assert result["news2_score"] == 5
    assert result["news2_red_flag"] == 0
    assert result["risk_class"] == RISK_WARNING


def test_total_seven_is_critical():
    result = _news2(respiratory_rate=26, spo2=92, heart_rate=115)
    assert result["news2_score"] == 7
    assert result["risk_class"] == RISK_CRITICAL


def test_maximum_total_is_fifteen():
    result = _news2(respiratory_rate=5, spo2=80, systolic_bp=80, heart_rate=150, temperature=34.0)
    assert result["news2_score"] == 15


def test_incomplete_vitals_give_missing_total_flag_and_class():
    result = _news2(temperature=np.nan, spo2=85)
    assert np.isnan(result["news2_score"])
    assert np.isnan(result["news2_red_flag"])
    assert np.isnan(result["risk_class"])
