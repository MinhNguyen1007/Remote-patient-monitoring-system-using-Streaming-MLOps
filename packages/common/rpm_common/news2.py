"""NEWS2 rút gọn 5 thông số (0–15) và mức rủi ro — bảng ngưỡng ở docs/design/02_9 mục 2.9.1(d)."""

import numpy as np
import pandas as pd

RISK_NORMAL, RISK_WARNING, RISK_CRITICAL = 0, 1, 2
RISK_LEVELS = ("NORMAL", "WARNING", "CRITICAL")

# Mỗi thông số: [(cận trên, điểm), ...] theo khoảng nửa mở (cận dưới, cận trên]; lớn hơn cận cuối nhận `above`.
_BANDS = {
    "respiratory_rate": ([(8, 3), (11, 1), (20, 0), (24, 2)], 3),
    "spo2": ([(91, 3), (93, 2), (95, 1)], 0),
    "systolic_bp": ([(90, 3), (100, 2), (110, 1), (219, 0)], 3),
    "heart_rate": ([(40, 3), (50, 1), (90, 0), (110, 1), (130, 2)], 3),
    "temperature": ([(35.0, 3), (36.0, 1), (38.0, 0), (39.0, 1)], 2),
}

NEWS2_PARAMS = tuple(_BANDS)
NEWS2_COMPONENT_COLUMNS = tuple(f"news2_{p}" for p in NEWS2_PARAMS)


def score_parameter(param: str, values) -> np.ndarray:
    """Điểm NEWS2 (0–3) của một thông số; giá trị rỗng cho điểm rỗng."""
    x = np.asarray(values, dtype=float)
    bands, above = _BANDS[param]
    scores = np.select([x <= upper for upper, _ in bands], [s for _, s in bands], default=above).astype(float)
    scores[np.isnan(x)] = np.nan
    return scores


def compute_news2(df: pd.DataFrame) -> pd.DataFrame:
    """Điểm thành phần, tổng điểm, cờ "có thông số đạt 3 điểm" và mức rủi ro (0/1/2).

    Dùng các cột vital đã forward-fill. Thiếu bất kỳ thông số nào thì tổng điểm, cờ và mức rủi ro để rỗng.
    """
    out = pd.DataFrame(index=df.index)
    for param in NEWS2_PARAMS:
        out[f"news2_{param}"] = score_parameter(param, df[param])

    components = out[list(NEWS2_COMPONENT_COLUMNS)]
    complete = components.notna().all(axis=1)
    total = components.sum(axis=1)
    red_flag = (components == 3).any(axis=1)
    risk = np.select(
        [total >= 7, (total >= 5) | red_flag],
        [RISK_CRITICAL, RISK_WARNING],
        default=RISK_NORMAL,
    ).astype(float)

    out["news2_score"] = total.where(complete)
    out["news2_red_flag"] = red_flag.astype(float).where(complete)
    out["risk_class"] = pd.Series(risk, index=df.index).where(complete)
    return out
