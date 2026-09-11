import pandas as pd

from rpm_ml.data.preprocess import select_replay_stays
from rpm_common.itemids import VITALS, obs_col


def _hourly(rows):
    df = pd.DataFrame(rows, columns=["subject_id", "icustay_id", "hour_index"])
    df["hour"] = pd.Timestamp("2150-01-01") + pd.to_timedelta(df["hour_index"], unit="h")
    for vital in VITALS:
        df[obs_col(vital)] = 1.0
        df[vital] = 1.0
    return df.assign(age=60.0, gender_male=1.0)


def test_replays_only_the_longest_stay_of_each_stream_subject():
    hourly = _hourly(
        [(1, 10, 0), (1, 10, 1), (1, 11, 0), (1, 11, 1), (1, 11, 2), (2, 20, 0), (3, 30, 0), (3, 30, 1)]
    )
    replay = select_replay_stays(hourly, stream_subjects=[1, 2])
    assert sorted(replay["icustay_id"].unique()) == [11, 20]
    assert replay.loc[replay["icustay_id"] == 11, "hour_index"].tolist() == [0, 1, 2]
    assert "source_charttime" in replay.columns
    assert not set(VITALS) & set(replay.columns)
