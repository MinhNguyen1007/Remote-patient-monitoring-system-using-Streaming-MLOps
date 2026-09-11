"""Kiểm tra drift cho DAG drift_check — docs/design/02_9 mục 2.9.4, 02_3 mục 2.3.3.

Cửa sổ hiện tại = 24 giờ dữ liệu streaming gần nhất, so với phân phối huấn luyện của `risk_classifier@champion`
(`reference_stats.json`) bằng PSI/KS; drift khi có đặc trưng vượt ngưỡng hiệu chỉnh của nó (`drift_thresholds.json`).

Lệnh (trên host cần POSTGRES_HOST=localhost MLFLOW_TRACKING_URI=http://localhost:5000
KAFKA_BOOTSTRAP_SERVERS=localhost:29092):
  python -m rpm_ml.drift.detect detect               tính PSI/KS, ghi drift_reports; dòng stdout cuối là JSON (XCom)
  python -m rpm_ml.drift.detect publish --report-id ID [--retrain-run-id RUN] [--blocked-reason TEXT]
                                                     ghi việc đã kích hoạt retrain, publish sự kiện drift_report
  python -m rpm_ml.drift.detect backfill-thresholds  hiệu chỉnh ngưỡng cho champion train trước Giai đoạn G và log
                                                     drift_thresholds.json vào run của nó (model không đổi)
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import mlflow
import pandas as pd
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException

from rpm_ml.paths import HOURLY_FILE
from rpm_ml.storage import db
from rpm_ml.drift.stats import calibrate_thresholds, decide_drift, feature_drift, select_window, window_skip_reason
from rpm_ml.storage.events import DRIFT_REPORT, publish, to_jsonable
from rpm_ml.pipelines.policy import should_notify_admin
from rpm_ml.data.stream_data import STREAM_GROUP, build_stream_hourly, load_stream_records

log = logging.getLogger("drift_detect")

DEFAULT_DATA = HOURLY_FILE
REFERENCE_MODEL = "risk_classifier"
REFERENCE_FILE = "reference_stats.json"
THRESHOLDS_FILE = "drift_thresholds.json"


class SkipCheck(Exception):
    """Lần kiểm tra bị bỏ qua, không ghi drift_reports."""


def evaluate_window(window: pd.DataFrame, reference: dict, thresholds: dict) -> dict:
    stats = feature_drift(reference, window)
    drift_detected, drifted = decide_drift(stats, thresholds["thresholds"])
    return {
        "feature_stats": stats,
        "drift_detected": drift_detected,
        "drifted_features": drifted,
        "max_psi": max(entry["psi"] for entry in stats.values()),
    }


def champion_reference(client: MlflowClient):
    try:
        version = client.get_model_version_by_alias(REFERENCE_MODEL, "champion")
    except MlflowException:
        raise SkipCheck(f"chưa có {REFERENCE_MODEL}@champion") from None
    try:
        reference = mlflow.artifacts.load_dict(f"runs:/{version.run_id}/{REFERENCE_FILE}")
        thresholds = mlflow.artifacts.load_dict(f"runs:/{version.run_id}/{THRESHOLDS_FILE}")
    except (MlflowException, OSError) as exc:
        raise SkipCheck(
            f"{REFERENCE_MODEL} v{version.version} thiếu {REFERENCE_FILE}/{THRESHOLDS_FILE} "
            f"(chạy `python -m rpm_ml.drift.detect backfill-thresholds`): {exc}"
        ) from None
    return version, reference, thresholds


def detect(conn, client: MlflowClient) -> dict:
    version, reference, thresholds = champion_reference(client)
    stream = build_stream_hourly(load_stream_records(conn))
    if stream.empty:
        raise SkipCheck("chưa có dữ liệu streaming")
    window = select_window(stream)
    window_start, window_end = window["recorded_at"].min(), window["recorded_at"].max()
    last = db.last_drift_report(conn)
    reason = window_skip_reason(window, last["window_end"] if last else None)
    if reason:
        raise SkipCheck(reason)

    result = evaluate_window(window, reference, thresholds)
    report_id = db.insert_drift_report(
        conn,
        window_start=window_start.to_pydatetime(),
        window_end=window_end.to_pydatetime(),
        n_records=len(window),
        reference_model_version_id=db.model_version_id(conn, REFERENCE_MODEL, version.version),
        max_psi=result["max_psi"],
        feature_stats=result["feature_stats"],
        drift_detected=result["drift_detected"],
    )
    return {
        "status": "checked",
        "report_id": str(report_id),
        "drift_detected": result["drift_detected"],
        "drifted_features": result["drifted_features"],
        "max_psi": round(result["max_psi"], 4),
        "n_records": len(window),
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "reference": f"{REFERENCE_MODEL} v{version.version}",
    }


def publish_report(conn, report_id: str, retrain_run_id: str, blocked_reason: str) -> dict:
    if retrain_run_id:
        db.mark_retrain_triggered(conn, report_id, retrain_run_id)
    report = db.get_drift_report(conn, report_id)
    previous = db.previous_drift_detected(conn, report_id)
    stats = report["feature_stats"] or {}
    event = {
        "type": DRIFT_REPORT,
        "drift_report_id": report["id"],
        "run_at": report["run_at"],
        "window_start": report["window_start"],
        "window_end": report["window_end"],
        "n_records": report["n_records"],
        "max_psi": report["max_psi"],
        "drift_detected": report["drift_detected"],
        "drifted_features": [feature for feature, entry in stats.items() if entry.get("drifted")],
        "feature_psi": {feature: entry["psi"] for feature, entry in stats.items()},
        "thresholds": {feature: entry.get("threshold") for feature, entry in stats.items()},
        "triggered_retrain": report["triggered_retrain"],
        "retrain_dag_run_id": report["dag_run_id"],
        "retrain_blocked_reason": blocked_reason or None,
        "previous_drift_detected": previous,
        "notify_admin": should_notify_admin(report["drift_detected"], previous, report["triggered_retrain"]),
    }
    publish(event)
    return event


def backfill_thresholds(client: MlflowClient, data: Path) -> dict:
    """Champion train trước khi có ngưỡng hiệu chỉnh: tính trên đúng dữ liệu phát triển của lần train đó rồi log vào run."""
    version = client.get_model_version_by_alias(REFERENCE_MODEL, "champion")
    run = client.get_run(version.run_id)
    groups = run.data.params.get("training_groups", "train").split(",")
    if STREAM_GROUP in groups:
        raise SystemExit("champion này được retrain có dữ liệu stream: ngưỡng đã được log lúc retrain")
    hourly = pd.read_parquet(data)
    calibration = calibrate_thresholds(hourly[hourly["split"].isin([*groups, "validation"])], int(run.data.params["seed"]))
    client.log_dict(version.run_id, calibration, THRESHOLDS_FILE)
    return {"model": f"{REFERENCE_MODEL} v{version.version}", "run_id": version.run_id} | calibration


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("detect")
    publish_parser = commands.add_parser("publish")
    publish_parser.add_argument("--report-id", required=True)
    publish_parser.add_argument("--retrain-run-id", default="")
    publish_parser.add_argument("--blocked-reason", default="")
    backfill_parser = commands.add_parser("backfill-thresholds")
    backfill_parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", stream=sys.stderr)
    db.load_env()
    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    client = MlflowClient()

    if args.command == "backfill-thresholds":
        result = backfill_thresholds(client, args.data)
    else:
        conn = db.connect()
        try:
            if args.command == "detect":
                try:
                    result = detect(conn, client)
                except SkipCheck as skip:
                    result = {"status": "skipped", "reason": str(skip)}
            else:
                result = publish_report(conn, args.report_id, args.retrain_run_id, args.blocked_reason)
        finally:
            conn.close()
    log.info("%s", json.dumps(to_jsonable(result), ensure_ascii=False, indent=2))
    # Dòng stdout cuối cùng là kết quả dạng JSON một dòng — BashOperator đẩy nó vào XCom
    print(json.dumps(to_jsonable(result), ensure_ascii=False))


if __name__ == "__main__":
    main()
