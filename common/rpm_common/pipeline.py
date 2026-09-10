import pandas as pd

from rpm_common.baseline import add_baseline_zscores
from rpm_common.features import add_window_features
from rpm_common.news2 import compute_news2


def build_hourly_features(grid: pd.DataFrame) -> pd.DataFrame:
    """Từ lưới 1 giờ đã forward-fill → thêm NEWS2, đặc trưng cửa sổ và z-score theo baseline.

    Là đường tính đặc trưng duy nhất cho cả huấn luyện (toàn bộ lịch sử) và streaming (bộ đệm
    theo bệnh nhân): mọi đặc trưng tại giờ t chỉ phụ thuộc dữ liệu tới t.
    """
    grid = grid.sort_values(["icustay_id", "hour_index"], kind="stable").reset_index(drop=True)
    grid = pd.concat([grid, compute_news2(grid)], axis=1)
    grid = pd.concat([grid, add_window_features(grid)], axis=1)
    return pd.concat([grid, add_baseline_zscores(grid)], axis=1)
