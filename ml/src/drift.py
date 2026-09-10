"""PSI/KS cho drift detection — docs/design/02_9 mục 2.9.4."""

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp

from rpm_common.itemids import VITALS

DRIFT_FEATURES = VITALS + ("news2_score",)
N_BINS = 10
EPSILON = 1e-4
KS_SAMPLE_SIZE = 2000


def reference_stats(df: pd.DataFrame, seed: int = 42) -> dict:
    """Phân phối tham chiếu từ dữ liệu huấn luyện: mốc chia bin theo thập phân vị, tỷ lệ mỗi bin, mẫu con cho KS."""
    rng = np.random.default_rng(seed)
    stats = {}
    for feature in DRIFT_FEATURES:
        values = df[feature].dropna().to_numpy(dtype=float)
        edges = np.unique(np.quantile(values, np.linspace(0, 1, N_BINS + 1)[1:-1]))
        sample = rng.choice(values, size=min(KS_SAMPLE_SIZE, len(values)), replace=False)
        stats[feature] = {
            "edges": edges.tolist(),
            "proportions": bin_proportions(values, edges).tolist(),
            "n": int(len(values)),
            "sample": np.round(sample, 3).tolist(),
        }
    return stats


def bin_proportions(values, edges) -> np.ndarray:
    """Tỷ lệ giá trị rơi vào từng bin; bin đầu/cuối mở rộng ra ±∞, giá trị bằng mốc thuộc bin phía trên."""
    values = np.asarray(values, dtype=float)
    counts = np.bincount(np.searchsorted(edges, values, side="right"), minlength=len(edges) + 1)
    return counts / counts.sum()


def psi(expected, actual) -> float:
    """Population Stability Index; bin có tỷ lệ 0 được thay bằng ε để tránh ln(0) và chia cho 0."""
    expected = np.where(np.asarray(expected, dtype=float) == 0, EPSILON, expected)
    actual = np.where(np.asarray(actual, dtype=float) == 0, EPSILON, actual)
    return float(np.sum((actual - expected) * np.log(actual / expected)))


def feature_drift(reference: dict, current: pd.DataFrame) -> dict:
    """PSI và thống kê KS D của từng đặc trưng so với phân phối tham chiếu."""
    result = {}
    for feature, ref in reference.items():
        values = current[feature].dropna().to_numpy(dtype=float)
        actual = bin_proportions(values, np.asarray(ref["edges"]))
        result[feature] = {
            "psi": psi(ref["proportions"], actual),
            "ks_statistic": float(ks_2samp(ref["sample"], values).statistic),
            "n": int(len(values)),
        }
    return result
