from types import SimpleNamespace

import numpy as np
import pytest

from anomaly_model import AnomalyDetector, build_lstm_autoencoder
from rpm_common.anomaly import N_CHANNELS, WINDOW_HOURS


class ShrinkModel:
    """Model giả tái tạo cửa sổ nhỏ đi một nửa: MSE = trung bình (x/2)²."""

    def predict(self, x, verbose=0):
        return x / 2


def make_detector(reference) -> AnomalyDetector:
    detector = AnomalyDetector()
    detector.autoencoder = ShrinkModel()
    detector.mse_reference = np.sort(np.asarray(reference, dtype=float))
    return detector


def alternating_window(v: float, offset: float = 0.0) -> np.ndarray:
    """Cửa sổ ±v xen kẽ theo giờ (trung bình từng kênh = offset), để kết quả sau khi căn giữa dễ tính tay."""
    signs = np.where(np.arange(WINDOW_HOURS) % 2 == 0, 1.0, -1.0)[:, None]
    return (offset + v * signs * np.ones((WINDOW_HOURS, N_CHANNELS))).astype(np.float32)


def test_predict_returns_empirical_cdf_score_in_unit_interval():
    detector = make_detector(reference=[0.25, 1.0, 4.0, 9.0])
    windows = np.stack([alternating_window(v) for v in (0.0, 2.0, 100.0)])
    # Sau khi căn giữa vẫn là ±v; MSE = (v/2)² → 0, 1, 2500 → tỷ lệ tham chiếu ≤ MSE: 0, 2/4, 1
    np.testing.assert_allclose(detector.predict(None, windows), [0.0, 0.5, 1.0])


def test_predict_ignores_window_level_offset_from_baseline():
    detector = make_detector(reference=[0.25, 1.0, 4.0, 9.0])
    same_shape = np.stack([alternating_window(2.0), alternating_window(2.0, offset=6.0)])
    scores = detector.predict(None, same_shape)
    assert scores[0] == pytest.approx(scores[1])


def test_predict_rejects_wrong_window_shape():
    detector = make_detector(reference=[1.0])
    with pytest.raises(ValueError):
        detector.predict(None, np.zeros((1, WINDOW_HOURS - 1, N_CHANNELS)))
    with pytest.raises(ValueError):
        detector.predict(None, np.zeros((WINDOW_HOURS, N_CHANNELS)))


def test_load_context_reads_keras_model_and_reference(tmp_path):
    model = build_lstm_autoencoder()
    keras_path, reference_path = tmp_path / "autoencoder.keras", tmp_path / "mse_reference.npy"
    model.save(keras_path)
    np.save(reference_path, np.array([0.1, 0.2]))
    detector = AnomalyDetector()
    detector.load_context(
        SimpleNamespace(artifacts={"autoencoder": str(keras_path), "mse_reference": str(reference_path)})
    )
    scores = detector.predict(None, np.zeros((3, WINDOW_HOURS, N_CHANNELS), dtype=np.float32))
    assert scores.shape == (3,)
    assert np.all((scores >= 0) & (scores <= 1))


def test_autoencoder_reconstructs_same_shape():
    model = build_lstm_autoencoder()
    x = np.random.default_rng(0).normal(size=(4, WINDOW_HOURS, N_CHANNELS)).astype(np.float32)
    assert model.predict(x, verbose=0).shape == x.shape
