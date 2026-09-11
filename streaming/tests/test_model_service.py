from types import SimpleNamespace
from uuid import uuid4

import numpy as np
import pandas as pd
import pytest
from mlflow.exceptions import MlflowException

from model_service import ANOMALY_MODEL, RISK_MODEL, LoadedModel, ModelService, predict_anomaly, predict_risk
from rpm_common.news2 import RISK_CRITICAL, RISK_NORMAL, RISK_WARNING


class FakeRisk:
    feature_names_in_ = np.array(["a", "b"])

    def __init__(self, proba):
        self.proba = np.asarray([proba])

    def predict_proba(self, X):
        assert list(X.columns) == ["a", "b"]
        return self.proba


def loaded_risk(proba) -> LoadedModel:
    return LoadedModel(RISK_MODEL, "2", uuid4(), FakeRisk(proba), tau_critical=0.22)


def test_predict_risk_uses_tau_critical_not_argmax():
    row = pd.DataFrame({"a": [1.0], "b": [2.0], "extra": [3.0]})
    result = predict_risk(loaded_risk([0.5, 0.25, 0.25]), row, tau_critical=0.22)
    assert result.risk_level == RISK_CRITICAL and result.risk_score == pytest.approx(0.25)
    assert predict_risk(loaded_risk([0.3, 0.5, 0.2]), row, tau_critical=0.22).risk_level == RISK_WARNING
    assert predict_risk(loaded_risk([0.7, 0.1, 0.2]), row, tau_critical=0.22).risk_level == RISK_NORMAL


def test_predict_risk_requires_exactly_one_row():
    rows = pd.DataFrame({"a": [1.0, 2.0], "b": [2.0, 3.0]})
    with pytest.raises(ValueError):
        predict_risk(loaded_risk([0.5, 0.25, 0.25]), rows, tau_critical=0.22)


def test_predict_anomaly_empty_without_window_or_model_and_in_unit_interval():
    model = LoadedModel(ANOMALY_MODEL, "2", uuid4(), SimpleNamespace(predict=lambda w: np.array([0.97])))
    assert predict_anomaly(model, None) is None
    assert predict_anomaly(None, np.zeros((1, 12, 6))) is None
    assert 0 <= predict_anomaly(model, np.zeros((1, 12, 6))) <= 1


class FakeClient:
    def __init__(self, versions: dict[str, str]):
        self.versions = versions

    def get_model_version_by_alias(self, name, alias):
        if name not in self.versions:
            raise MlflowException("không có alias")
        return SimpleNamespace(version=self.versions[name])


class CountingService(ModelService):
    def __init__(self, client, clock):
        super().__init__(client, sync_champion=None, refresh_seconds=60, clock=clock)
        self.loads = []

    def _load(self, name, version):
        self.loads.append((name, version.version))
        return LoadedModel(name, version.version, uuid4(), object(), 0.22 if name == RISK_MODEL else None)


def test_reloads_only_when_champion_alias_moves_and_after_refresh_interval():
    now = [0.0]
    client = FakeClient({RISK_MODEL: "2", ANOMALY_MODEL: "2"})
    service = CountingService(client, clock=lambda: now[0])
    service.refresh_if_due()
    client.versions[RISK_MODEL] = "3"
    now[0] = 30.0
    service.refresh_if_due()  # chưa tới chu kỳ 60 giây
    assert service.risk.version == "2"
    now[0] = 61.0
    service.refresh_if_due()
    assert service.risk.version == "3"
    assert service.loads == [(RISK_MODEL, "2"), (ANOMALY_MODEL, "2"), (RISK_MODEL, "3")]


def test_missing_risk_champion_is_fatal_but_missing_anomaly_champion_is_not():
    with pytest.raises(RuntimeError):
        CountingService(FakeClient({ANOMALY_MODEL: "1"}), clock=lambda: 0.0).refresh_if_due()
    service = CountingService(FakeClient({RISK_MODEL: "1"}), clock=lambda: 0.0)
    service.refresh_if_due()
    assert service.anomaly is None and service.risk.version == "1"
