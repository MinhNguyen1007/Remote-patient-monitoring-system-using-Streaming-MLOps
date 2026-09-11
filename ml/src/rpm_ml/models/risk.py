"""Các mô hình ứng viên cho dự báo rủi ro — docs/design/02_9 mục 2.9.2."""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

from rpm_ml.evaluation.metrics import CLASSES, classification_metrics

CV_FOLDS = 5


def make_candidates(seed: int) -> dict:
    """Mỗi ứng viên là một hàm tạo estimator mới (sklearn API, có predict_proba 3 lớp)."""
    return {
        "logistic_regression": lambda: make_pipeline(
            SimpleImputer(strategy="median"), StandardScaler(), LogisticRegression(C=1.0, max_iter=3000)
        ),
        "random_forest": lambda: make_pipeline(
            SimpleImputer(strategy="median"),
            RandomForestClassifier(n_estimators=300, min_samples_leaf=5, n_jobs=-1, random_state=seed),
        ),
        "xgboost": lambda: XGBClassifier(
            objective="multi:softprob",
            n_estimators=300,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            tree_method="hist",
            eval_metric="mlogloss",
            n_jobs=-1,
            random_state=seed,
        ),
    }


def fit_balanced(model, X: pd.DataFrame, y: pd.Series):
    """Huấn luyện với trọng số lớp cân bằng (lớp hiếm như CRITICAL được đánh trọng số cao hơn)."""
    weights = compute_sample_weight("balanced", y)
    if isinstance(model, Pipeline):
        model.fit(X, y, **{f"{model.steps[-1][0]}__sample_weight": weights})
    else:
        model.fit(X, y, sample_weight=weights)
    return model


def cross_validate(make_model, X: pd.DataFrame, y: pd.Series, groups: pd.Series) -> tuple[dict, np.ndarray]:
    """GroupKFold theo bệnh nhân; metric tính tại lớp có xác suất lớn nhất (chưa áp τ).

    Trả thêm xác suất out-of-fold: mỗi mẫu được dự đoán bởi model không thấy bệnh nhân của nó lúc fit,
    dùng để chọn τ_critical trên toàn bộ tập phát triển thay vì chỉ trên validation.
    """
    folds = []
    oof_proba = np.full((len(X), len(CLASSES)), np.nan)
    for train_idx, valid_idx in GroupKFold(n_splits=CV_FOLDS).split(X, y, groups):
        model = fit_balanced(make_model(), X.iloc[train_idx], y.iloc[train_idx])
        proba = model.predict_proba(X.iloc[valid_idx])
        oof_proba[valid_idx] = proba
        folds.append(classification_metrics(y.iloc[valid_idx], proba.argmax(axis=1), proba))
    return summarize_folds(folds), oof_proba


def cross_validate_persistence(current: pd.Series, y: pd.Series, groups: pd.Series) -> dict:
    folds = [
        classification_metrics(y.iloc[valid_idx], current.iloc[valid_idx])
        for _, valid_idx in GroupKFold(n_splits=CV_FOLDS).split(current, y, groups)
    ]
    return summarize_folds(folds)


def summarize_folds(folds: list[dict]) -> dict:
    keys = [k for k, v in folds[0].items() if isinstance(v, float)]
    return {
        key: {"mean": float(np.mean([f[key] for f in folds])), "std": float(np.std([f[key] for f in folds]))}
        for key in keys
    }
