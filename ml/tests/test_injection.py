import numpy as np
import pytest

from injection import DRIFT_SIGMA, KINDS, SHIFT_SIGMA, SPIKE_SIGMA, channel_sigma, inject_anomalies

N, LENGTH, CHANNELS = 300, 12, 6


def make_windows(seed: int = 0) -> np.ndarray:
    return np.random.default_rng(seed).normal(size=(N, LENGTH, CHANNELS)).astype(np.float32)


def test_injects_rate_of_windows_split_evenly_across_kinds():
    _, is_anomaly, kind = inject_anomalies(make_windows(), np.ones(CHANNELS), rate=0.1, seed=1)
    assert is_anomaly.sum() == 30
    assert {k: (kind == k).sum() for k in KINDS} == {"spike": 10, "level_shift": 10, "drift": 10}
    assert set(kind[~is_anomaly]) == {""}


def test_same_seed_gives_identical_injection_and_input_is_untouched():
    windows = make_windows()
    original = windows.copy()
    a = inject_anomalies(windows, np.ones(CHANNELS), seed=7)
    b = inject_anomalies(windows, np.ones(CHANNELS), seed=7)
    np.testing.assert_array_equal(a[0], b[0])
    np.testing.assert_array_equal(a[2], b[2])
    np.testing.assert_array_equal(windows, original)


def test_clean_windows_are_unchanged():
    windows = make_windows()
    injected, is_anomaly, _ = inject_anomalies(windows, np.ones(CHANNELS), seed=3)
    np.testing.assert_array_equal(injected[~is_anomaly], windows[~is_anomaly])


@pytest.mark.parametrize("kind", KINDS)
def test_each_kind_changes_one_channel_with_expected_shape(kind):
    windows = np.zeros((N, LENGTH, CHANNELS), dtype=np.float32)
    sigma = np.arange(1.0, CHANNELS + 1)
    injected, _, kinds = inject_anomalies(windows, sigma, seed=5)
    for i in np.flatnonzero(kinds == kind):
        delta = injected[i] - windows[i]
        channels = np.flatnonzero(np.abs(delta).sum(axis=0) > 0)
        assert len(channels) == 1
        channel = channels[0]
        added = delta[:, channel]
        if kind == "spike":
            changed = np.flatnonzero(added)
            assert 1 <= len(changed) <= 2 and np.all(np.diff(changed) == 1)
            np.testing.assert_allclose(np.abs(added[changed]), SPIKE_SIGMA * sigma[channel])
        elif kind == "level_shift":
            np.testing.assert_allclose(added[: LENGTH // 2], 0)
            np.testing.assert_allclose(added[LENGTH // 2 :], SHIFT_SIGMA * sigma[channel])
        else:
            np.testing.assert_allclose(added, np.linspace(0, DRIFT_SIGMA * sigma[channel], LENGTH), rtol=1e-6)


def test_channel_sigma_is_std_per_channel_over_all_steps():
    windows = make_windows()
    windows[:, :, 2] *= 3
    sigma = channel_sigma(windows)
    assert sigma.shape == (CHANNELS,)
    assert sigma[2] == pytest.approx(3 * sigma[0], rel=0.1)
