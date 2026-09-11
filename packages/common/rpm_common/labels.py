import pandas as pd


def make_forecast_label(risk_class: pd.Series, stay_ids: pd.Series, horizon: int) -> pd.Series:
    """Nhãn dự báo y_t = mức rủi ro cao nhất trong (t, t+horizon] của cùng đợt ICU.

    Để rỗng nếu thiếu bất kỳ giờ nào trong horizon (hết đợt ICU hoặc giờ đó không đủ 5 thông số NEWS2).
    Yêu cầu dữ liệu sắp theo (icustay_id, hour_index) và đủ mọi giờ như lưới của `to_hourly_grid`.
    """
    grouped = risk_class.groupby(stay_ids, sort=False)
    future = pd.concat([grouped.shift(-k) for k in range(1, horizon + 1)], axis=1)
    return future.max(axis=1).where(future.notna().all(axis=1))
