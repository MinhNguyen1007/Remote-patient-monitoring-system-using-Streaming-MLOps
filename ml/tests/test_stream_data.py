from uuid import uuid4

import numpy as np
import pandas as pd
import pytest

from rpm_common.baseline import ZSCORE_COLUMNS
from rpm_common.features import RISK_FEATURE_COLUMNS
from rpm_common.itemids import VITALS, obs_col
from rpm_ml.data.stream_data import STREAM_GROUP, build_stream_hourly, combine_with_stream
from rpm_ml.paths import PROCESSED_DIR as PROCESSED
from rpm_ml.pipelines.retrain import run_dir, training_groups

COMPARED = list(RISK_FEATURE_COLUMNS) + list(ZSCORE_COLUMNS) + ["news2_score", "risk_class", "label_h1", "label_h4"]


def records_from_replay(replay: pd.DataFrame, hours: int | None = None) -> pd.DataFrame:
    """Giả lập nội dung vital_records + patients sau khi phát `hours` nhịp đầu của lần phát lại."""
    frames = []
    for _, stay in replay.groupby("icustay_id"):
        stay = stay.sort_values("hour_index").head(hours) if hours else stay
        frames.append(
            stay.assign(
                patient_id=uuid4(),
                recorded_at=pd.Timestamp("2026-09-11", tz="UTC") + pd.to_timedelta(stay["hour_index"] * 5, unit="s"),
            )
        )
    columns = ["patient_id", "subject_id", "icustay_id", "age", "gender_male", "hour_index", "recorded_at"]
    return pd.concat(frames)[columns + [obs_col(v) for v in VITALS]]


@pytest.mark.skipif(not (PROCESSED / "stream_replay.parquet").exists(), reason="chưa chạy python -m rpm_ml.data.preprocess")
def test_stream_rebuilt_from_db_matches_training_rows():
    """Dữ liệu stream dựng lại từ giá trị đo chưa điền = dòng tương ứng của hourly.parquet (đặc trưng lẫn nhãn)."""
    replay = pd.read_parquet(PROCESSED / "stream_replay.parquet")
    hourly = pd.read_parquet(PROCESSED / "hourly.parquet")
    stays = replay["icustay_id"].unique()[:4]
    rebuilt = build_stream_hourly(records_from_replay(replay[replay["icustay_id"].isin(stays)]))
    expected = hourly[hourly["icustay_id"].isin(stays)].sort_values(["icustay_id", "hour_index"])
    assert (rebuilt["split"] == STREAM_GROUP).all()
    pd.testing.assert_frame_equal(
        rebuilt[COMPARED].reset_index(drop=True).astype(float),
        expected[COMPARED].reset_index(drop=True).astype(float),
        atol=1e-9,
    )


@pytest.mark.skipif(not (PROCESSED / "stream_replay.parquet").exists(), reason="chưa chạy python -m rpm_ml.data.preprocess")
def test_labels_only_for_hours_already_matured():
    """Mới phát 30 giờ: nhãn h = 4 chỉ có tới giờ 25; đặc trưng vẫn trùng dữ liệu huấn luyện (chỉ dùng quá khứ)."""
    replay = pd.read_parquet(PROCESSED / "stream_replay.parquet")
    hourly = pd.read_parquet(PROCESSED / "hourly.parquet")
    lengths = replay.groupby("icustay_id").size()
    stay = lengths[lengths > 60].index[0]
    rebuilt = build_stream_hourly(records_from_replay(replay[replay["icustay_id"] == stay], hours=30))
    assert rebuilt["hour_index"].max() == 29
    assert rebuilt.loc[rebuilt["hour_index"] >= 26, "label_h4"].isna().all()
    expected = hourly[hourly["icustay_id"] == stay].set_index("hour_index").loc[:25]
    matured = rebuilt.set_index("hour_index").loc[:25]
    np.testing.assert_allclose(matured["label_h4"].astype(float), expected["label_h4"].astype(float))
    features = [c for c in RISK_FEATURE_COLUMNS if c != "hour_index"]
    pd.testing.assert_frame_equal(
        rebuilt.set_index("hour_index")[features].astype(float),
        hourly[hourly["icustay_id"] == stay].set_index("hour_index").loc[:29, features].astype(float),
        atol=1e-9,
        check_index_type=False,
    )


def _toy_records(hours: list[int]) -> pd.DataFrame:
    rows = [
        {"patient_id": "p1", "subject_id": 7, "icustay_id": 70, "age": 60.0, "gender_male": 1.0, "hour_index": h,
         "recorded_at": pd.Timestamp("2026-09-11", tz="UTC") + pd.Timedelta(seconds=5 * h)}
        | {obs_col(v): 80.0 for v in VITALS}
        for h in hours
    ]
    return pd.DataFrame(rows)


def test_missing_hours_become_unmeasured_hours_without_recorded_at():
    rebuilt = build_stream_hourly(_toy_records([0, 1, 4]))
    assert rebuilt["hour_index"].tolist() == [0, 1, 2, 3, 4]
    assert rebuilt["recorded_at"].isna().tolist() == [False, False, True, True, False]
    assert (rebuilt["subject_id"] == 7).all() and (rebuilt["age"] == 60.0).all()


def test_empty_stream_gives_empty_frame_and_training_on_train_only():
    assert build_stream_hourly(_toy_records([]).iloc[0:0]).empty
    hourly = pd.DataFrame({"subject_id": [1, 2], "split": ["train", "validation"]})
    assert training_groups(hourly) == ("train",)
    assert training_groups(combine_with_stream(hourly, pd.DataFrame())) == ("train",)


def test_combine_replaces_unplayed_stream_rows_and_rejects_patient_overlap():
    hourly = pd.DataFrame(
        {"subject_id": [1, 2, 3, 3], "split": ["train", "validation", "stream", "stream"], "hour_index": [0, 0, 0, 1]}
    )
    stream = pd.DataFrame(
        {"subject_id": [3], "split": [STREAM_GROUP], "hour_index": [0], "patient_id": ["p"], "recorded_at": [pd.NaT]}
    )
    combined = combine_with_stream(hourly, stream)
    # Chỉ giữ phần stream đã thực sự phát (1 giờ), không giữ toàn bộ đợt ICU có sẵn trong hourly.parquet
    assert (combined["split"] == STREAM_GROUP).sum() == 1
    assert "patient_id" not in combined.columns
    assert training_groups(combined) == ("train", STREAM_GROUP)
    with pytest.raises(ValueError):
        combine_with_stream(hourly, stream.assign(subject_id=1))


def test_run_dir_is_safe_for_airflow_run_ids(tmp_path):
    path = run_dir(tmp_path, "manual__2026-09-11T10:00:00.123+00:00")
    assert path.parent == tmp_path and ":" not in path.name and "+" not in path.name
