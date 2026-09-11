"""Truy cập rpm_db cho drift_check và retrain_pipeline (schema do Alembic ở services/backend quản lý).

Chỉ ghi 2 bảng thuộc luồng MLOps: `drift_reports` và `model_versions` (kể cả version bị gate từ chối). Consumer cũng
đồng bộ version champion vào `model_versions` khi nạp model (services/streaming: rpm_streaming/storage/repository.py) — hai nơi dùng chung khóa
`(model_name, mlflow_version)`, nên đổi tên cột phải sửa cả hai.
"""

import json
import os
import uuid
from datetime import datetime

import psycopg2
import psycopg2.extras

from rpm_ml.paths import ENV_FILE

psycopg2.extras.register_uuid()


def load_env() -> None:
    """Biến đã đặt trong shell/container được ưu tiên hơn `.env` ở gốc repo (khi chạy trên host)."""
    try:
        from dotenv import load_dotenv
    except ImportError:  # image Airflow: biến môi trường do docker compose cấp
        return
    load_dotenv(ENV_FILE, override=False)


def connect():
    load_env()
    env = os.environ
    return psycopg2.connect(
        host=env.get("POSTGRES_HOST", "localhost"),
        port=env.get("POSTGRES_PORT", "5432"),
        dbname=env["POSTGRES_DB"],
        user=env["POSTGRES_USER"],
        password=env["POSTGRES_PASSWORD"],
    )


# ------------------------------------------------------------------------------------------------ drift_reports


def last_drift_report(conn) -> dict | None:
    with conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT id, window_end, drift_detected FROM drift_reports ORDER BY run_at DESC LIMIT 1")
        row = cur.fetchone()
    return dict(row) if row else None


def insert_drift_report(
    conn, *, window_start: datetime, window_end: datetime, n_records: int, reference_model_version_id,
    max_psi: float, feature_stats: dict, drift_detected: bool,
) -> uuid.UUID:
    report_id = uuid.uuid4()
    with conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO drift_reports (id, run_at, window_start, window_end, n_records, reference_model_version_id,
                                       max_psi, feature_stats, drift_detected, triggered_retrain)
            VALUES (%s, now(), %s, %s, %s, %s, %s, %s, %s, false)
            """,
            (report_id, window_start, window_end, n_records, reference_model_version_id, max_psi,
             json.dumps(feature_stats), drift_detected),
        )
    return report_id


def get_drift_report(conn, report_id) -> dict:
    with conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM drift_reports WHERE id = %s", (uuid.UUID(str(report_id)),))
        row = cur.fetchone()
    if row is None:
        raise LookupError(f"không có drift_report {report_id}")
    return dict(row)


def previous_drift_detected(conn, report_id) -> bool | None:
    """Kết luận của lần kiểm tra ngay trước báo cáo này; None nếu đây là báo cáo đầu tiên."""
    with conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT drift_detected FROM drift_reports
            WHERE run_at < (SELECT run_at FROM drift_reports WHERE id = %s)
            ORDER BY run_at DESC LIMIT 1
            """,
            (uuid.UUID(str(report_id)),),
        )
        row = cur.fetchone()
    return None if row is None else bool(row[0])


def mark_retrain_triggered(conn, report_id, dag_run_id: str) -> None:
    with conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE drift_reports SET triggered_retrain = true, dag_run_id = %s WHERE id = %s",
            (dag_run_id, uuid.UUID(str(report_id))),
        )


# ----------------------------------------------------------------------------------------------- model_versions


def model_version_id(conn, model_name: str, mlflow_version: str) -> uuid.UUID | None:
    with conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM model_versions WHERE model_name = %s AND mlflow_version = %s",
            (model_name, str(mlflow_version)),
        )
        row = cur.fetchone()
    return row[0] if row else None


def record_model_version(
    conn, *, model_name: str, mlflow_version: str, run_id: str, promoted: bool, gate_reasons: list[str],
    trigger: str, drift_report_id, dag_run_id: str | None, metrics: dict, trained_at: datetime | None,
) -> uuid.UUID:
    """Ghi kết quả gate của một challenger; version được promote thành champion duy nhất của model đó."""
    drift_report = uuid.UUID(str(drift_report_id)) if drift_report_id else None
    with conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO model_versions (id, model_name, mlflow_version, mlflow_run_id, gate_status, gate_reasons,
                                        is_champion, trigger, drift_report_id, dag_run_id, metrics, trained_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (model_name, mlflow_version) DO UPDATE
                SET gate_status = EXCLUDED.gate_status, gate_reasons = EXCLUDED.gate_reasons,
                    is_champion = EXCLUDED.is_champion, trigger = EXCLUDED.trigger,
                    drift_report_id = EXCLUDED.drift_report_id, dag_run_id = EXCLUDED.dag_run_id,
                    metrics = COALESCE(model_versions.metrics, '{}'::jsonb) || EXCLUDED.metrics
            RETURNING id
            """,
            (
                uuid.uuid4(), model_name, str(mlflow_version), run_id, "PROMOTED" if promoted else "REJECTED",
                "; ".join(gate_reasons) or None, promoted, trigger, drift_report, dag_run_id, json.dumps(metrics),
                trained_at,
            ),
        )
        version_id = cur.fetchone()[0]
        if promoted:
            cur.execute(
                "UPDATE model_versions SET is_champion = false WHERE model_name = %s AND id <> %s AND is_champion",
                (model_name, version_id),
            )
    return version_id
