import pandas as pd

from rpm_common.itemids import FAHRENHEIT_ITEMIDS, ITEMID_TO_VITAL, VALID_RANGES

CHARTEVENTS_COLUMNS = ["icustay_id", "itemid", "charttime", "valuenum", "error", "stopped"]


def clean_chartevents(chartevents: pd.DataFrame) -> pd.DataFrame:
    """Lọc CHARTEVENTS về dạng dài (icustay_id, charttime, vital, value), nhiệt độ quy về °C.

    Bỏ: itemid ngoài mapping, dòng error = 1 (MetaVision), stopped = "D/C'd" (CareVue),
    valuenum hoặc icustay_id rỗng, giá trị ngoài khoảng hợp lệ theo đơn vị gốc.
    """
    df = chartevents[chartevents["itemid"].isin(ITEMID_TO_VITAL.keys())]
    df = df[(df["error"] != 1) & (df["stopped"] != "D/C'd")]
    df = df.dropna(subset=["icustay_id", "valuenum"])

    vital = df["itemid"].map(ITEMID_TO_VITAL)
    is_fahrenheit = df["itemid"].isin(FAHRENHEIT_ITEMIDS)
    range_key = vital.copy()
    range_key[(vital == "temperature") & is_fahrenheit] = "temperature_f"
    range_key[(vital == "temperature") & ~is_fahrenheit] = "temperature_c"
    bounds = pd.DataFrame(
        range_key.map(VALID_RANGES).tolist(),
        index=df.index,
        columns=["low", "high", "high_inclusive"],
    )

    value = df["valuenum"].astype(float)
    valid = (value > bounds["low"]) & (
        (value < bounds["high"]) | (bounds["high_inclusive"] & (value == bounds["high"]))
    )
    value = value.where(~is_fahrenheit, (value - 32.0) / 1.8)
    value = value.where(vital != "temperature", value.round(1))

    out = pd.DataFrame(
        {
            "icustay_id": df["icustay_id"].astype("int64"),
            "charttime": pd.to_datetime(df["charttime"]),
            "vital": vital,
            "value": value,
        }
    )
    return out[valid].reset_index(drop=True)
