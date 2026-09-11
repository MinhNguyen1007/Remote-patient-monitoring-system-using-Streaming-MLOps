"""Mapping itemid CHARTEVENTS (CareVue + MetaVision) → vital chuẩn. Nguồn và lý do: ml/README.md mục 4."""

VITALS = (
    "heart_rate",
    "spo2",
    "respiratory_rate",
    "systolic_bp",
    "diastolic_bp",
    "temperature",
)

ITEMID_TO_VITAL = {
    211: "heart_rate",
    220045: "heart_rate",
    646: "spo2",
    220277: "spo2",
    615: "respiratory_rate",
    618: "respiratory_rate",
    220210: "respiratory_rate",
    224690: "respiratory_rate",
    51: "systolic_bp",
    442: "systolic_bp",
    455: "systolic_bp",
    6701: "systolic_bp",
    220050: "systolic_bp",
    220179: "systolic_bp",
    8368: "diastolic_bp",
    8440: "diastolic_bp",
    8441: "diastolic_bp",
    8555: "diastolic_bp",
    220051: "diastolic_bp",
    220180: "diastolic_bp",
    676: "temperature",
    678: "temperature",
    223761: "temperature",
    223762: "temperature",
}

FAHRENHEIT_ITEMIDS = frozenset({678, 223761})

# (cận dưới loại trừ, cận trên, có nhận đúng cận trên), theo đơn vị gốc của itemid
VALID_RANGES = {
    "heart_rate": (0.0, 300.0, False),
    "spo2": (0.0, 100.0, True),
    "respiratory_rate": (0.0, 70.0, False),
    "systolic_bp": (0.0, 400.0, False),
    "diastolic_bp": (0.0, 300.0, False),
    "temperature_c": (10.0, 50.0, False),
    "temperature_f": (70.0, 120.0, False),
}


def obs_col(vital: str) -> str:
    """Tên cột giá trị đo thật (chưa điền) của một vital trên lưới 1 giờ."""
    return f"{vital}_obs"
