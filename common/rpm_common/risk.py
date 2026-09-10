import numpy as np

from rpm_common.news2 import RISK_CRITICAL, RISK_NORMAL, RISK_WARNING


def risk_level_from_proba(proba, tau_critical: float) -> np.ndarray:
    """Mức rủi ro từ xác suất 3 lớp (thứ tự NORMAL, WARNING, CRITICAL) — docs/design/02_9 mục 2.9.6.

    CRITICAL nếu P(CRITICAL) ≥ τ_critical; ngược lại lấy lớp có xác suất lớn hơn giữa NORMAL và WARNING.
    """
    proba = np.asarray(proba, dtype=float)
    fallback = np.where(proba[:, RISK_WARNING] > proba[:, RISK_NORMAL], RISK_WARNING, RISK_NORMAL)
    return np.where(proba[:, RISK_CRITICAL] >= tau_critical, RISK_CRITICAL, fallback)
