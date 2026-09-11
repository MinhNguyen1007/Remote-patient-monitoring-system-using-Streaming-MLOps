"""Dữ liệu streaming đã tích lũy trong DB → bảng theo giờ cùng dạng với hourly.parquet (dùng cho drift và retrain).

`vital_records` lưu giá trị đo chưa điền, như producer gửi. Đặc trưng được dựng lại theo đúng đường tính của lúc huấn
luyện và của consumer: lưới giờ `<vital>_obs` (giờ bị hụt = giờ không đo) → `fill_forward` → `build_hourly_features`,
rồi gắn nhãn dự báo. Nhãn chỉ có ở những giờ đã "chín" (đủ h giờ phía sau trong phần đã phát) — docs/design/02_9 mục
2.9.2 và 2.9.5.
"""

import numpy as np
import pandas as pd

from rpm_common.grid import fill_forward
from rpm_common.itemids import VITALS, obs_col
from rpm_common.labels import make_forecast_label
from rpm_common.pipeline import build_hourly_features

STREAM_GROUP = "stream"
HORIZONS = (1, 4)
STATIC_COLUMNS = ["patient_id", "subject_id", "age", "gender_male"]


def load_stream_records(conn) -> pd.DataFrame:
    """Mọi bản ghi giờ đã nhận của các bệnh nhân đang giám sát, kèm thông tin tĩnh của bệnh nhân."""
    query = f"""
        SELECT v.patient_id, p.mimic_subject_id AS subject_id, p.mimic_icustay_id AS icustay_id, p.age, p.gender,
               v.hour_index, v.recorded_at, {", ".join(f"v.{v} AS {obs_col(v)}" for v in VITALS)}
        FROM vital_records v JOIN patients p ON p.id = v.patient_id
        ORDER BY p.mimic_icustay_id, v.hour_index
    """
    with conn.cursor() as cur:
        cur.execute(query)
        columns = [c.name for c in cur.description]
        records = pd.DataFrame(cur.fetchall(), columns=columns)
    records["gender_male"] = records["gender"].map({"M": 1.0, "F": 0.0})
    records["recorded_at"] = pd.to_datetime(records["recorded_at"], utc=True)
    obs = [obs_col(v) for v in VITALS]
    records[obs + ["age"]] = records[obs + ["age"]].astype(float)
    return records.drop(columns="gender")


def build_stream_hourly(records: pd.DataFrame) -> pd.DataFrame:
    """Đặc trưng + nhãn dự báo theo giờ của từng đợt ICU đã phát; cột `split` = "stream"."""
    if records.empty:
        return pd.DataFrame()
    frames = []
    for stay_id, stay in records.groupby("icustay_id", sort=True):
        stay = stay.set_index("hour_index")
        stay = stay.reindex(range(int(stay.index.min()), int(stay.index.max()) + 1))
        stay[STATIC_COLUMNS] = stay[STATIC_COLUMNS].ffill().bfill()
        stay["icustay_id"] = stay_id
        frames.append(stay.rename_axis("hour_index").reset_index())
    grid = pd.concat(frames, ignore_index=True)
    grid["subject_id"] = grid["subject_id"].astype(int)
    hourly = build_hourly_features(fill_forward(grid))
    for horizon in HORIZONS:
        hourly[f"label_h{horizon}"] = make_forecast_label(hourly["risk_class"], hourly["icustay_id"], horizon)
    hourly["split"] = STREAM_GROUP
    return hourly


def combine_with_stream(hourly: pd.DataFrame, stream: pd.DataFrame) -> pd.DataFrame:
    """Nối dữ liệu stream vào hourly.parquet (4 nhóm cố định); bệnh nhân stream không bao giờ nằm ở nhóm khác."""
    if stream.empty:
        return hourly
    overlap = set(stream["subject_id"]) & set(hourly.loc[hourly["split"] != STREAM_GROUP, "subject_id"])
    if overlap:
        raise ValueError(f"bệnh nhân stream trùng với nhóm khác: {sorted(overlap)}")
    # Hàng của nhóm stream trong hourly.parquet là toàn bộ đợt ICU (chưa phát) — chỉ dùng phần đã thực sự phát
    base = hourly[hourly["split"] != STREAM_GROUP]
    return pd.concat([base, stream.drop(columns=["patient_id", "recorded_at"], errors="ignore")], ignore_index=True)


def stream_summary(stream: pd.DataFrame) -> dict:
    if stream.empty:
        return {"patients": 0, "hours": 0, "labeled_hours_h4": 0}
    return {
        "patients": int(stream["subject_id"].nunique()),
        "hours": int(len(stream)),
        "labeled_hours_h4": int(stream["label_h4"].notna().sum()),
        "max_hour_index": int(np.nanmax(stream["hour_index"])),
    }
