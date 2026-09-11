from rpm_common.news2 import RISK_CRITICAL, RISK_NORMAL, RISK_WARNING
from rpm_common.risk import risk_level_from_proba


def test_critical_when_probability_reaches_threshold_even_if_not_argmax():
    levels = risk_level_from_proba([[0.5, 0.2, 0.3], [0.5, 0.21, 0.29]], tau_critical=0.3)
    assert levels.tolist() == [RISK_CRITICAL, RISK_NORMAL]


def test_falls_back_to_larger_of_normal_and_warning():
    levels = risk_level_from_proba([[0.2, 0.7, 0.1], [0.6, 0.3, 0.1]], tau_critical=0.5)
    assert levels.tolist() == [RISK_WARNING, RISK_NORMAL]
