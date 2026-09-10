import math

import numpy as np
import pandas as pd
import pytest

from drift import DRIFT_FEATURES, bin_proportions, feature_drift, psi, reference_stats


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
