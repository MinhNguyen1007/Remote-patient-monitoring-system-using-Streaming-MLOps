"""Đường dẫn dữ liệu và kết quả của ml/, tính từ vị trí package (cài editable: pip install -e ml).

Trong image Airflow, package nằm ở /opt/rpm/ml/src/rpm_ml nên ML_DIR = /opt/rpm/ml (ml/data/processed được mount vào).
"""

from pathlib import Path

ML_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = ML_DIR.parent
ENV_FILE = REPO_ROOT / ".env"

RAW_DATA_DIR = ML_DIR / "data" / "raw" / "mimic-iii-clinical-database-demo-1.4"
PROCESSED_DIR = ML_DIR / "data" / "processed"
HOURLY_FILE = PROCESSED_DIR / "hourly.parquet"
STREAM_REPLAY_FILE = PROCESSED_DIR / "stream_replay.parquet"
SPLIT_FILE = ML_DIR / "splits" / "subject_split.json"
REPORTS_DIR = ML_DIR / "reports"
