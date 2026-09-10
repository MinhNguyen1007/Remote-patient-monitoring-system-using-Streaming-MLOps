import numpy as np
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from rpm_common.news2 import RISK_CRITICAL

CLASSES = [0, 1, 2]
TAU_GRID = np.round(np.arange(0.05, 0.951, 0.01), 2)


def classification_metrics(y_true, y_pred, proba=None) -> dict:
    """Metric theo docs/design/02_9 mục 2.9.2; AUROC/AUPRC chỉ tính khi có xác suất."""
    y_true = np.asarray(y_true, dtype=int)
    y_pred = np.asarray(y_pred, dtype=int)
    metrics = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, labels=CLASSES, average="macro", zero_division=0)),
        "recall_critical": float(recall_score(y_true, y_pred, labels=[RISK_CRITICAL], average="macro", zero_division=0)),
        "precision_critical": float(
            precision_score(y_true, y_pred, labels=[RISK_CRITICAL], average="macro", zero_division=0)
        ),
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=CLASSES).tolist(),
    }
    if proba is not None:
        proba = np.asarray(proba, dtype=float)
        metrics["auroc_ovr"] = float(roc_auc_score(y_true, proba, multi_class="ovr", average="macro", labels=CLASSES))
        metrics["auprc_critical"] = float(average_precision_score(y_true == RISK_CRITICAL, proba[:, RISK_CRITICAL]))
    return metrics


def choose_tau_critical(y_true, p_critical, target_recall: float) -> float:
    """Ngưỡng lớn nhất trên lưới mà recall lớp CRITICAL vẫn ≥ target; không ngưỡng nào đạt thì lấy ngưỡng nhỏ nhất."""
    is_critical = np.asarray(y_true) == RISK_CRITICAL
    p_critical = np.asarray(p_critical, dtype=float)
    for tau in TAU_GRID[::-1]:
        if (is_critical & (p_critical >= tau)).sum() >= target_recall * is_critical.sum():
            return float(tau)
    return float(TAU_GRID[0])


def scalar_metrics(metrics: dict, prefix: str) -> dict:
    """Bỏ các metric không phải số (ma trận nhầm lẫn) và gắn tiền tố để log MLflow."""
    return {f"{prefix}_{k}": v for k, v in metrics.items() if isinstance(v, float)}
