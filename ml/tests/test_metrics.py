import numpy as np
import pytest

from metrics import choose_tau_critical, classification_metrics


def test_tau_is_largest_threshold_keeping_target_recall():
    y = np.array([2, 2, 2, 2, 0, 0])
    p_critical = np.array([0.9, 0.7, 0.5, 0.2, 0.6, 0.1])
    # τ = 0.5 bắt được 3/4 ca CRITICAL (recall 0,75); cần τ ≤ 0,2 để đạt 1,0
    assert choose_tau_critical(y, p_critical, target_recall=0.75) == pytest.approx(0.5)
    assert choose_tau_critical(y, p_critical, target_recall=1.0) == pytest.approx(0.2)


def test_tau_falls_back_to_smallest_threshold_when_target_unreachable():
    y = np.array([2, 2])
    p_critical = np.array([0.01, 0.02])
    assert choose_tau_critical(y, p_critical, target_recall=0.8) == pytest.approx(0.05)


def test_classification_metrics_values():
    y_true = [0, 0, 1, 1, 2, 2]
    y_pred = [0, 1, 1, 1, 2, 0]
    metrics = classification_metrics(y_true, y_pred)
    assert metrics["accuracy"] == pytest.approx(4 / 6)
    assert metrics["recall_critical"] == pytest.approx(0.5)
    assert metrics["precision_critical"] == pytest.approx(1.0)
    assert metrics["confusion_matrix"] == [[1, 1, 0], [0, 2, 0], [1, 0, 1]]
    assert "auroc_ovr" not in metrics


def test_probability_metrics_are_added_when_proba_given():
    y_true = [0, 1, 2]
    proba = np.eye(3)
    metrics = classification_metrics(y_true, [0, 1, 2], proba)
    assert metrics["auroc_ovr"] == pytest.approx(1.0)
    assert metrics["auprc_critical"] == pytest.approx(1.0)
