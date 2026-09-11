import numpy as np
import pandas as pd
import pytest

from rpm_common.grid import fill_forward
from rpm_common.itemids import VITALS, obs_col

NORMAL_VALUES = {
    "heart_rate": 75.0,
    "spo2": 98.0,
    "respiratory_rate": 16.0,
    "systolic_bp": 120.0,
    "diastolic_bp": 70.0,
    "temperature": 37.0,
}


def make_grid(n_hours: int, stay_id: int = 1, overrides: dict | None = None) -> pd.DataFrame:
    """Lưới 1 giờ của một đợt ICU với vitals bình thường đo đủ mọi giờ; `overrides[vital]` = list giá trị đo."""
    data = {"icustay_id": stay_id, "hour_index": np.arange(n_hours)}
    for vital in VITALS:
        values = (overrides or {}).get(vital, [NORMAL_VALUES[vital]] * n_hours)
        data[obs_col(vital)] = np.asarray(values, dtype=float)
    return fill_forward(pd.DataFrame(data))


@pytest.fixture
def grid_factory():
    return make_grid
