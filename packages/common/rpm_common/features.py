import pandas as pd

from rpm_common.itemids import VITALS, obs_col
from rpm_common.news2 import NEWS2_COMPONENT_COLUMNS

ROLLING_WINDOW_HOURS = 6
ROLLING_MIN_OBS = 3
AGE_CAP_YEARS = 90

WINDOW_FEATURE_COLUMNS = tuple(
    f"{v}_{stat}" for v in VITALS for stat in ("mean_6h", "std_6h", "slope_6h", "delta_1h")
) + ("news2_delta_1h", "news2_max_6h")

RISK_FEATURE_COLUMNS = (
    VITALS
    + NEWS2_COMPONENT_COLUMNS
    + ("news2_score", "news2_red_flag")
    + WINDOW_FEATURE_COLUMNS
    + ("hour_index", "age", "gender_male")
)


def add_window_features(grid: pd.DataFrame) -> pd.DataFrame:
    """Đặc trưng theo cửa sổ 6 giờ gần nhất (tính cả giờ hiện tại) cho từng đợt ICU.

    Trung bình/độ lệch chuẩn/độ dốc tính trên giá trị đo thật `<vital>_obs`, cần ít nhất 3 giá trị;
    chênh lệch 1 giờ tính trên giá trị đã điền. Yêu cầu `grid` sắp theo (icustay_id, hour_index),
    đủ mọi giờ, và đã có cột `news2_score`.
    """
    stay = grid["icustay_id"]
    by_stay = grid.groupby(stay, sort=False)
    feats = {}
    for vital in VITALS:
        roll = grid[obs_col(vital)].groupby(stay, sort=False).rolling(ROLLING_WINDOW_HOURS, min_periods=ROLLING_MIN_OBS)
        feats[f"{vital}_mean_6h"] = roll.mean().reset_index(level=0, drop=True)
        feats[f"{vital}_std_6h"] = roll.std().reset_index(level=0, drop=True)
        feats[f"{vital}_slope_6h"] = _rolling_slope(grid, obs_col(vital))
        feats[f"{vital}_delta_1h"] = grid[vital] - by_stay[vital].shift(1)

    feats["news2_delta_1h"] = grid["news2_score"] - by_stay["news2_score"].shift(1)
    feats["news2_max_6h"] = (
        grid["news2_score"]
        .groupby(stay, sort=False)
        .rolling(ROLLING_WINDOW_HOURS, min_periods=1)
        .max()
        .reset_index(level=0, drop=True)
    )
    return pd.DataFrame(feats, index=grid.index)


def _rolling_slope(grid: pd.DataFrame, column: str) -> pd.Series:
    """Độ dốc hồi quy tuyến tính (đơn vị/giờ) của các giá trị đo thật trong cửa sổ, qua tổng trượt."""
    y = grid[column]
    observed = y.notna().astype(float)
    x = grid["hour_index"].astype(float)
    parts = pd.DataFrame(
        {
            "n": observed,
            "sx": x * observed,
            "sy": y.fillna(0.0),
            "sxy": (x * y).fillna(0.0),
            "sxx": x * x * observed,
        }
    )
    sums = (
        parts.groupby(grid["icustay_id"], sort=False)
        .rolling(ROLLING_WINDOW_HOURS, min_periods=1)
        .sum()
        .reset_index(level=0, drop=True)
        .reindex(grid.index)
    )
    n = sums["n"]
    denom = n * sums["sxx"] - sums["sx"] ** 2
    slope = (n * sums["sxy"] - sums["sx"] * sums["sy"]) / denom
    return slope.where((n >= ROLLING_MIN_OBS) & (denom > 0))


def compute_age_years(dob: pd.Series, reference: pd.Series) -> pd.Series:
    """Tuổi tròn năm tại thời điểm tham chiếu, chặn trên 90.

    MIMIC dịch ngày sinh của bệnh nhân > 89 tuổi lùi khoảng 300 năm; tính theo năm/tháng/ngày thay vì
    trừ datetime để không tràn số của timedelta.
    """
    dob = pd.to_datetime(dob)
    reference = pd.to_datetime(reference)
    before_birthday = (reference.dt.month < dob.dt.month) | (
        (reference.dt.month == dob.dt.month) & (reference.dt.day < dob.dt.day)
    )
    age = reference.dt.year - dob.dt.year - before_birthday.astype(int)
    return age.clip(upper=AGE_CAP_YEARS).astype(float)
