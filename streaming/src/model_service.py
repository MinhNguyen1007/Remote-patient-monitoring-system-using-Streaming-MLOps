"""Model Service chạy trong consumer — docs/design/02_4 mục 2.4.1 và 2.4.3.

- Nạp `models:/risk_classifier@champion` và `models:/anomaly_detector@champion`, theo **số version** mà alias đang
  trỏ tới (tránh đổi alias giữa chừng lúc tải).
- Định kỳ đọc lại alias; version đổi thì nạp model mới.
- Mỗi version champion được đồng bộ vào bảng `model_versions` để prediction ghi đúng version đã dùng.
- Thiếu champion rủi ro thì consumer không chạy được; thiếu champion bất thường thì `anomaly_score` để trống.
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import UUID

import numpy as np
import pandas as pd

from rpm_common.news2 import RISK_CRITICAL
from rpm_common.risk import risk_level_from_proba

log = logging.getLogger("model_service")

RISK_MODEL = "risk_classifier"
ANOMALY_MODEL = "anomaly_detector"


@dataclass
class LoadedModel:
    name: str
    version: str
    db_id: UUID
    model: Any
    tau_critical: float | None = None


@dataclass(frozen=True)
class RiskResult:
    risk_score: float
    risk_level: int


def predict_risk(loaded: LoadedModel, features: pd.DataFrame, tau_critical: float) -> RiskResult:
    """Dự báo cho **một** giờ (DataFrame 1 dòng): risk_score = P(CRITICAL), risk_level theo τ_critical."""
    if len(features) != 1:
        raise ValueError(f"cần đúng 1 dòng đặc trưng, nhận {len(features)}")
    columns = list(loaded.model.feature_names_in_)
    proba = loaded.model.predict_proba(features[columns].astype(float))
    return RiskResult(float(proba[0, RISK_CRITICAL]), int(risk_level_from_proba(proba, tau_critical)[0]))


def predict_anomaly(loaded: LoadedModel | None, window: np.ndarray | None) -> float | None:
    """anomaly_score ∈ [0, 1] cho cửa sổ (1, 12, 6); trống khi chưa đủ cửa sổ hoặc chưa có champion."""
    if loaded is None or window is None:
        return None
    return float(np.asarray(loaded.model.predict(window)).reshape(-1)[0])


class ModelService:
    def __init__(self, client, sync_champion: Callable[..., UUID], refresh_seconds: float, clock=time.monotonic):
        self.client = client
        self.sync_champion = sync_champion
        self.refresh_seconds = refresh_seconds
        self.clock = clock
        self.risk: LoadedModel | None = None
        self.anomaly: LoadedModel | None = None
        self._last_check = float("-inf")

    def refresh_if_due(self) -> None:
        if self.clock() - self._last_check < self.refresh_seconds:
            return
        self._last_check = self.clock()
        self.risk = self._refresh(RISK_MODEL, self.risk, required=True)
        self.anomaly = self._refresh(ANOMALY_MODEL, self.anomaly, required=False)

    def _refresh(self, name: str, current: LoadedModel | None, required: bool) -> LoadedModel | None:
        from mlflow.exceptions import MlflowException

        try:
            version = self.client.get_model_version_by_alias(name, "champion")
        except MlflowException:
            if required and current is None:
                raise RuntimeError(f"chưa có {name}@champion trên MLflow — hãy train và promote trước") from None
            if current is None:
                log.warning("chưa có %s@champion: bỏ qua mô hình này", name)
            return current
        if current is not None and current.version == version.version:
            return current
        loaded = self._load(name, version)
        log.info("đã nạp %s v%s (trước đó: %s)", name, version.version, current.version if current else "chưa có")
        return loaded

    def _load(self, name: str, version) -> LoadedModel:
        import mlflow

        uri = f"models:/{name}/{version.version}"
        run = self.client.get_run(version.run_id)
        metrics = {k: v for k, v in run.data.metrics.items() if k.startswith("test_")}
        trained_at = datetime.fromtimestamp(run.info.start_time / 1000, tz=timezone.utc)
        db_id = self.sync_champion(
            model_name=name,
            mlflow_version=version.version,
            run_id=version.run_id,
            trigger=version.tags.get("trigger", "INITIAL"),
            metrics=metrics,
            trained_at=trained_at,
        )
        if name == RISK_MODEL:
            model = single_threaded(mlflow.sklearn.load_model(uri))
            return LoadedModel(name, version.version, db_id, model, float(version.tags["tau_critical"]))
        return LoadedModel(name, version.version, db_id, mlflow.pyfunc.load_model(uri))


def single_threaded(model):
    """Suy luận từng dòng một: pool luồng của n_jobs=-1 tốn ~40 ms/lần gọi, n_jobs=1 chỉ ~12 ms, kết quả như nhau."""
    steps = [step for _, step in model.steps] if hasattr(model, "steps") else [model]
    for step in steps:
        if hasattr(step, "n_jobs"):
            step.n_jobs = 1
    return model
