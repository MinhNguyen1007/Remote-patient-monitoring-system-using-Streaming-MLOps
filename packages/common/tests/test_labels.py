import numpy as np
import pandas as pd

from rpm_common.labels import make_forecast_label


def _label(risk, stays, horizon):
    return make_forecast_label(pd.Series(risk, dtype=float), pd.Series(stays), horizon)


def test_label_is_highest_risk_in_next_h_hours():
    y = _label([0, 0, 1, 0, 2, 0], [1] * 6, 2)
    assert y.tolist()[:4] == [1.0, 1.0, 2.0, 2.0]
    assert y.iloc[4:].isna().all()


def test_label_excludes_current_hour():
    y = _label([2, 0, 0], [1] * 3, 1)
    assert y.iloc[0] == 0.0


def test_label_is_missing_when_any_future_hour_is_missing():
    y = _label([0, np.nan, 0, 0], [1] * 4, 2)
    assert np.isnan(y.iloc[0])
    assert y.iloc[1] == 0.0
    assert np.isnan(y.iloc[2])


def test_label_does_not_look_into_the_next_stay():
    y = _label([0, 0, 2, 2], [1, 1, 2, 2], 1)
    assert y.iloc[0] == 0.0
    assert np.isnan(y.iloc[1])
    assert y.iloc[2] == 2.0
