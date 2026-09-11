import numpy as np
import pandas as pd

from rpm_ml.models.risk import CV_FOLDS, cross_validate


class RecordingModel:
    """Model giả: ghi lại bệnh nhân đã thấy lúc fit, báo lỗi nếu phải dự đoán cho chính bệnh nhân đó."""

    def fit(self, X, y, sample_weight=None):
        self.seen = set(X["subject"])
        return self

    def predict_proba(self, X):
        assert not self.seen & set(X["subject"]), "rò rỉ bệnh nhân giữa fit và dự đoán out-of-fold"
        return np.tile([0.2, 0.3, 0.5], (len(X), 1))


def make_dev(n_subjects: int = 10):
    subjects = np.repeat(np.arange(n_subjects), 6)
    X = pd.DataFrame({"subject": subjects, "x": np.arange(len(subjects), dtype=float)})
    y = pd.Series(np.tile([0, 1, 2], 2 * n_subjects))
    return X, y, pd.Series(subjects)


def test_out_of_fold_proba_covers_every_sample_without_patient_leak():
    X, y, groups = make_dev()
    summary, oof = cross_validate(RecordingModel, X, y, groups)
    assert oof.shape == (len(X), 3)
    assert not np.isnan(oof).any()
    np.testing.assert_allclose(oof.sum(axis=1), 1.0)
    assert set(summary) >= {"macro_f1", "recall_critical"}


def test_out_of_fold_proba_is_positionally_aligned_with_input():
    """Chỉ số của DataFrame không liên tục (sau concat train ∪ validation) vẫn phải khớp theo vị trí."""
    X, y, groups = make_dev()
    shuffled_index = np.random.default_rng(0).permutation(len(X)) * 7
    X.index = y.index = groups.index = shuffled_index

    class SubjectProba(RecordingModel):
        def predict_proba(self, X):
            super().predict_proba(X)
            p_critical = X["subject"].to_numpy() / 100
            return np.column_stack([1 - p_critical, np.zeros(len(X)), p_critical])

    _, oof = cross_validate(SubjectProba, X, y, groups)
    np.testing.assert_allclose(oof[:, 2], X["subject"].to_numpy() / 100)
    assert CV_FOLDS <= X["subject"].nunique()
