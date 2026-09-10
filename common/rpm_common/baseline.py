import numpy as np
import pandas as pd

from rpm_common.itemids import VITALS, obs_col

BASELINE_MAX_HOURS = 24
BASELINE_MIN_HOURS = 6
STD_FLOOR = {
    "heart_rate": 5.0,
    "spo2": 1.0,
    "respiratory_rate": 2.0,
    "systolic_bp": 5.0,
    "diastolic_bp": 5.0,
    "temperature": 0.2,
}

ZSCORE_COLUMNS = tuple(f"{v}_z" for v in VITALS)


def add_baseline_zscores(grid: pd.DataFrame) -> pd.DataFrame:
    """Z-score từng vital so với baseline của chính đợt ICU đó.

    Baseline = trung bình/độ lệch chuẩn các giá trị đo thật, tính lũy tiến trên tối đa 24 giờ đầu rồi
    cố định; chỉ dùng được từ khi đã qua 6 giờ (`baseline_ready`). Độ lệch chuẩn có sàn tối thiểu
    để không chia cho số gần 0. Z-score để rỗng khi baseline chưa dùng được.
    """
    stay = grid["icustay_id"]
    in_baseline_window = grid["hour_index"] < BASELINE_MAX_HOURS
    ready = grid["hour_index"] >= BASELINE_MIN_HOURS - 1

    out = {}
    for vital in VITALS:
        expanding = grid[obs_col(vital)].where(in_baseline_window).groupby(stay, sort=False).expanding()
        mean = expanding.mean().reset_index(level=0, drop=True).reindex(grid.index)
        std = expanding.std().reset_index(level=0, drop=True).reindex(grid.index)
        scale = np.fmax(std, STD_FLOOR[vital])
        out[f"{vital}_z"] = ((grid[vital] - mean) / scale).where(ready)
    out["baseline_ready"] = ready
    return pd.DataFrame(out, index=grid.index)
