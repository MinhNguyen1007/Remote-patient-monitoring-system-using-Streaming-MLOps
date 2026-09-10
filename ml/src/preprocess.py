"""Tiền xử lý MIMIC-III Demo → dữ liệu theo giờ cho huấn luyện và dữ liệu phát lại cho producer.

Chạy từ gốc repo: python ml/src/preprocess.py
Đầu ra (thư mục ml/data/processed, không nằm trong git):
  hourly.parquet         mọi đợt ICU: vitals, NEWS2, đặc trưng, z-score, nhãn dự báo, nhóm chia dữ liệu
  stream_replay.parquet  1 đợt ICU dài nhất của mỗi bệnh nhân nhóm stream, giá trị đo theo giờ chưa điền
  summary.json           thống kê nhanh để kiểm tra
Chi tiết giải thuật: docs/design/02_9_thiet_ke_giai_thuat.md mục 2.9.1–2.9.2.
"""

import argparse
import json
from pathlib import Path

import pandas as pd

from rpm_common.cleaning import CHARTEVENTS_COLUMNS, clean_chartevents
from rpm_common.features import compute_age_years
from rpm_common.grid import to_hourly_grid
from rpm_common.itemids import VITALS, obs_col
from rpm_common.labels import make_forecast_label
from rpm_common.news2 import RISK_LEVELS
from rpm_common.pipeline import build_hourly_features
from split import load_or_create_split, subject_to_group

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = REPO_ROOT / "mimic-iii-clinical-database-demo-1.4_data"
DEFAULT_OUT_DIR = REPO_ROOT / "ml" / "data" / "processed"
DEFAULT_SPLIT_FILE = REPO_ROOT / "ml" / "splits" / "subject_split.json"
HORIZONS = (1, 4)


def read_table(data_dir: Path, name: str, **kwargs) -> pd.DataFrame:
    df = pd.read_csv(data_dir / f"{name}.csv", low_memory=False, **kwargs)
    df.columns = [c.lower() for c in df.columns]
    return df


def load_chartevents(data_dir: Path) -> pd.DataFrame:
    wanted = set(CHARTEVENTS_COLUMNS)
    return read_table(data_dir, "CHARTEVENTS", usecols=lambda c: c.lower() in wanted, dtype={"stopped": str, "STOPPED": str})


def load_stays(data_dir: Path) -> pd.DataFrame:
    """Thông tin tĩnh của từng đợt ICU: bệnh nhân, tuổi lúc vào ICU, giới tính, tử vong tại viện."""
    icu = read_table(data_dir, "ICUSTAYS", parse_dates=["intime", "outtime"])
    patients = read_table(data_dir, "PATIENTS")
    admissions = read_table(data_dir, "ADMISSIONS")[["hadm_id", "hospital_expire_flag"]]
    stays = icu.merge(patients[["subject_id", "gender", "dob"]], on="subject_id").merge(admissions, on="hadm_id")
    stays["age"] = compute_age_years(stays["dob"], stays["intime"])
    stays["gender_male"] = (stays["gender"] == "M").astype(float)
    return stays[["icustay_id", "subject_id", "hadm_id", "dbsource", "age", "gender_male", "hospital_expire_flag"]]


def subject_strata(data_dir: Path, subject_ids) -> pd.DataFrame:
    """Tầng phân chia của các bệnh nhân có dữ liệu vitals: có lượt nhập viện tử vong tại viện hay không."""
    admissions = read_table(data_dir, "ADMISSIONS")
    died = admissions.groupby("subject_id")["hospital_expire_flag"].max().rename("stratum")
    subjects = pd.DataFrame({"subject_id": sorted(int(s) for s in set(subject_ids))})
    return subjects.merge(died, on="subject_id", how="left").fillna({"stratum": 0})


def select_replay_stays(hourly: pd.DataFrame, stream_subjects: list[int]) -> pd.DataFrame:
    """Mỗi bệnh nhân nhóm stream được phát lại đúng 1 đợt ICU: đợt có nhiều giờ dữ liệu nhất."""
    lengths = (
        hourly[hourly["subject_id"].isin(stream_subjects)]
        .groupby(["subject_id", "icustay_id"])
        .size()
        .rename("hours")
        .reset_index()
        .sort_values(["subject_id", "hours", "icustay_id"], ascending=[True, False, True])
    )
    chosen = lengths.drop_duplicates("subject_id")["icustay_id"]
    columns = ["subject_id", "icustay_id", "hour_index", "hour", *[obs_col(v) for v in VITALS], "age", "gender_male"]
    replay = hourly[hourly["icustay_id"].isin(chosen)][columns].rename(columns={"hour": "source_charttime"})
    return replay.sort_values(["subject_id", "hour_index"]).reset_index(drop=True)


def build_summary(hourly: pd.DataFrame, replay: pd.DataFrame) -> dict:
    def distribution(series: pd.Series) -> dict:
        counts = series.dropna().astype(int).value_counts().sort_index()
        return {RISK_LEVELS[k]: int(v) for k, v in counts.items()}

    per_split = {}
    for group, part in hourly.groupby("split"):
        per_split[group] = {
            "subjects": int(part["subject_id"].nunique()),
            "stays": int(part["icustay_id"].nunique()),
            "hours": int(len(part)),
            **{f"label_h{h}": distribution(part[f"label_h{h}"]) for h in HORIZONS},
        }
    return {
        "stays_with_vitals": int(hourly["icustay_id"].nunique()),
        "hours": int(len(hourly)),
        "hours_with_news2": int(hourly["risk_class"].notna().sum()),
        "risk_class": distribution(hourly["risk_class"]),
        "splits": per_split,
        "stream_replay": {
            "subjects": int(replay["subject_id"].nunique()),
            "hours": int(len(replay)),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--split-file", type=Path, default=DEFAULT_SPLIT_FILE)
    args = parser.parse_args()

    grid = to_hourly_grid(clean_chartevents(load_chartevents(args.data_dir)))
    grid = grid.merge(load_stays(args.data_dir), on="icustay_id", how="left")
    hourly = build_hourly_features(grid)
    for horizon in HORIZONS:
        hourly[f"label_h{horizon}"] = make_forecast_label(hourly["risk_class"], hourly["icustay_id"], horizon)

    groups = load_or_create_split(subject_strata(args.data_dir, hourly["subject_id"]), args.split_file)
    hourly["split"] = hourly["subject_id"].map(subject_to_group(groups))
    replay = select_replay_stays(hourly, groups["stream"])

    args.out_dir.mkdir(parents=True, exist_ok=True)
    hourly.to_parquet(args.out_dir / "hourly.parquet", index=False)
    replay.to_parquet(args.out_dir / "stream_replay.parquet", index=False)
    summary = build_summary(hourly, replay)
    (args.out_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
