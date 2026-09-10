import numpy as np
import pandas as pd

from rpm_common.itemids import VITALS, obs_col

FFILL_LIMIT_HOURS = {
    "heart_rate": 2,
    "spo2": 2,
    "respiratory_rate": 2,
    "systolic_bp": 2,
    "diastolic_bp": 2,
    "temperature": 6,
}


def to_hourly_grid(long_df: pd.DataFrame) -> pd.DataFrame:
    """Đưa dữ liệu dạng dài về lưới 1 giờ liên tục cho từng đợt ICU.

    Mỗi giờ lấy trung vị các lần đo (`<vital>_obs`, rỗng nếu giờ đó không đo); lưới chạy từ giờ
    đầu tiên đến giờ cuối cùng có đo, không bỏ giờ nào. `hour_index` đếm từ 0 trong mỗi đợt.
    """
    df = long_df.assign(hour=long_df["charttime"].dt.floor("h"))
    wide = df.pivot_table(index=["icustay_id", "hour"], columns="vital", values="value", aggfunc="median")
    wide = wide.reindex(columns=list(VITALS))

    frames = []
    for stay_id, stay in wide.groupby(level="icustay_id", sort=True):
        stay = stay.droplevel("icustay_id")
        hours = pd.date_range(stay.index.min(), stay.index.max(), freq="h", name="hour")
        stay = stay.reindex(hours).reset_index()
        stay.insert(0, "icustay_id", stay_id)
        stay.insert(2, "hour_index", np.arange(len(stay)))
        frames.append(stay)

    grid = pd.concat(frames, ignore_index=True)
    grid.columns.name = None
    grid = grid.rename(columns={v: obs_col(v) for v in VITALS})
    return fill_forward(grid)


def fill_forward(grid: pd.DataFrame) -> pd.DataFrame:
    """Thêm cột `<vital>` = giá trị đo gần nhất trong cùng đợt ICU, chỉ điền tới giới hạn giờ cho phép.

    Chỉ điền theo chiều thời gian (không nội suy, không điền ngược) để lúc huấn luyện và lúc
    streaming chỉ dùng thông tin đã có tới thời điểm hiện tại.
    """
    grid = grid.copy()
    by_stay = grid.groupby("icustay_id", sort=False)
    for vital in VITALS:
        grid[vital] = by_stay[obs_col(vital)].ffill(limit=FFILL_LIMIT_HOURS[vital])
    return grid
