"""Các bước của DAG retrain_pipeline (Champion–Challenger) — docs/design/02_9 mục 2.9.5, 02_3 mục 2.3.3, 02_4 mục 2.4.3.

Lệnh (trên host cần POSTGRES_HOST=localhost MLFLOW_TRACKING_URI=http://localhost:5000
KAFKA_BOOTSTRAP_SERVERS=localhost:29092):
  python -m rpm_ml.pipelines.retrain build   --runs-dir DIR --dag-run-id RUN
      dựng dữ liệu = 4 nhóm cố định của hourly.parquet + dữ liệu stream đã thực sự phát (đọc từ DB, nhãn đã "chín")
  python -m rpm_ml.pipelines.retrain risk    --runs-dir DIR --dag-run-id RUN --trigger MANUAL|DRIFT [--drift-report-id ID]
  python -m rpm_ml.pipelines.retrain anomaly --runs-dir DIR --dag-run-id RUN --trigger MANUAL|DRIFT [--drift-report-id ID]
      huấn luyện challenger trên train + stream, đánh giá cùng champion trên test cố định, gate, promote/từ chối,
      ghi model_versions (kể cả version bị từ chối)
  python -m rpm_ml.pipelines.retrain publish --runs-dir DIR --dag-run-id RUN --trigger ... [--drift-report-id ID]
      publish sự kiện retrain_completed (backend đẩy WebSocket cho Admin), xóa bản dữ liệu tạm
"""

import argparse
import json
import logging
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import mlflow
import pandas as pd
from mlflow import MlflowClient

from rpm_ml.paths import HOURLY_FILE
from rpm_ml.storage import db
from rpm_ml.storage.events import RETRAIN_COMPLETED, publish, to_jsonable
from rpm_ml.data.stream_data import STREAM_GROUP, build_stream_hourly, combine_with_stream, load_stream_records, stream_summary

log = logging.getLogger("retrain")

DEFAULT_DATA = HOURLY_FILE
TRIGGERS = ("MANUAL", "DRIFT")
RETRAIN_GROUPS = ("train", STREAM_GROUP)
MODELS = {"risk": "risk_classifier", "anomaly": "anomaly_detector"}
DATASET_FILE = "dataset.parquet"
# Metric lưu vào model_versions: cùng tiền tố với metric consumer đồng bộ (services/streaming: rpm_streaming/consumer/model_service.py)
DB_METRIC_PREFIXES = ("test_", "persistence_test_")


def run_dir(runs_dir: Path, dag_run_id: str) -> Path:
    """Thư mục tạm của một lần chạy DAG (run_id của Airflow có ':' và '+', không hợp lệ trên mọi hệ thống file)."""
    return runs_dir / re.sub(r"[^A-Za-z0-9_.-]", "_", dag_run_id)


def training_groups(hourly: pd.DataFrame) -> tuple[str, ...]:
    """Có dữ liệu stream đã phát thì huấn luyện trên train + stream; chưa có thì chỉ train (như lần đầu)."""
    return RETRAIN_GROUPS if (hourly["split"] == STREAM_GROUP).any() else ("train",)


def build(directory: Path, data: Path) -> dict:
    hourly = pd.read_parquet(data)
    conn = db.connect()
    try:
        stream = build_stream_hourly(load_stream_records(conn))
    finally:
        conn.close()
    combined = combine_with_stream(hourly, stream)
    directory.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(directory / DATASET_FILE, index=False)
    summary = {
        "stream": stream_summary(stream),
        "hours_by_group": {group: int(n) for group, n in combined["split"].value_counts().sort_index().items()},
        "training_groups": list(training_groups(combined)),
    }
    (directory / "dataset.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def db_metrics(summary: dict) -> dict:
    """Metric của run trên test (+ persistence) như consumer đồng bộ, kèm metric champion được chấm lại cùng tập."""
    run_metrics = MlflowClient().get_run(summary["run_id"]).data.metrics
    metrics = {k: v for k, v in run_metrics.items() if k.startswith(DB_METRIC_PREFIXES)}
    for key, value in (summary.get("champion_test") or {}).items():
        metrics[f"champion_test_{key}"] = value
    return metrics


def retrain(kind: str, directory: Path, trigger: str, dag_run_id: str, drift_report_id: str, seed: int) -> dict:
    # TensorFlow chỉ được nạp ở bước cần tới nó
    if kind == "risk":
        from rpm_ml.training.train_risk import train_risk_model as train_model
    else:
        from rpm_ml.training.train_anomaly import train_anomaly_model as train_model

    hourly = pd.read_parquet(directory / DATASET_FILE)
    tags = {"dag_run_id": dag_run_id} | ({"drift_report_id": drift_report_id} if drift_report_id else {})
    summary = train_model(hourly, seed=seed, training_groups=training_groups(hourly), trigger=trigger, tags=tags)

    run = MlflowClient().get_run(summary["run_id"])
    conn = db.connect()
    try:
        summary["model_version_id"] = db.record_model_version(
            conn,
            model_name=summary["model_name"],
            mlflow_version=summary["registered_version"],
            run_id=summary["run_id"],
            promoted=summary["gate"]["passed"],
            gate_reasons=summary["gate"]["reasons"],
            trigger=trigger,
            drift_report_id=drift_report_id or None,
            dag_run_id=dag_run_id,
            metrics=db_metrics(summary),
            trained_at=datetime.fromtimestamp(run.info.start_time / 1000, tz=timezone.utc),
        )
    finally:
        conn.close()
    (directory / f"{kind}.json").write_text(json.dumps(to_jsonable(summary), indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def publish_result(directory: Path, trigger: str, dag_run_id: str, drift_report_id: str) -> dict:
    results = []
    for kind, model_name in MODELS.items():
        path = directory / f"{kind}.json"
        if not path.exists():
            results.append({"model_name": model_name, "status": "FAILED"})
            continue
        summary = json.loads(path.read_text(encoding="utf-8"))
        results.append(
            {
                "model_name": model_name,
                "status": "PROMOTED" if summary["gate"]["passed"] else "REJECTED",
                "version": summary["registered_version"],
                "gate_reasons": summary["gate"]["reasons"],
                "test": summary["test"],
                "champion_version": summary["champion_version"],
                "champion_test": summary["champion_test"],
            }
        )
    event = {
        "type": RETRAIN_COMPLETED,
        "dag_run_id": dag_run_id,
        "trigger": trigger,
        "drift_report_id": drift_report_id or None,
        "finished_at": datetime.now(timezone.utc),
        "results": results,
    }
    publish(event)
    (directory / DATASET_FILE).unlink(missing_ok=True)
    return event


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("build", "risk", "anomaly", "publish"))
    parser.add_argument("--runs-dir", type=Path, required=True)
    parser.add_argument("--dag-run-id", required=True)
    parser.add_argument("--trigger", default="MANUAL")
    parser.add_argument("--drift-report-id", default="")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    # Giá trị đến từ conf của lần chạy DAG (Admin có thể tự nhập trên Airflow UI) — kiểm tra trước khi dùng
    if args.trigger not in TRIGGERS:
        parser.error(f"--trigger phải là một trong {TRIGGERS}")
    if args.drift_report_id:
        args.drift_report_id = str(uuid.UUID(args.drift_report_id))

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", stream=sys.stderr)
    db.load_env()
    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    directory = run_dir(args.runs_dir, args.dag_run_id)

    if args.command == "build":
        result = build(directory, args.data)
    elif args.command == "publish":
        result = publish_result(directory, args.trigger, args.dag_run_id, args.drift_report_id)
    else:
        result = retrain(args.command, directory, args.trigger, args.dag_run_id, args.drift_report_id, args.seed)
    log.info("%s", json.dumps(to_jsonable(result), ensure_ascii=False, indent=2))
    print(json.dumps(to_jsonable(result), ensure_ascii=False))


if __name__ == "__main__":
    main()
