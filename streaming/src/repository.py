"""Truy cập PostgreSQL/TimescaleDB của consumer (schema do Alembic ở backend/ quản lý).

Consumer chỉ ghi các bảng thuộc luồng streaming: patients, vital_records, predictions, alerts, model_versions
(đồng bộ từ MLflow) và seed alert_settings lần đầu. Mỗi bản ghi giờ được ghi trong **một transaction**:
vital_record + prediction + alert (tham chiếu vào hypertable là tham chiếu logic, xem 02_7).
"""

import json
import uuid
from dataclasses import dataclass
from datetime import datetime

import psycopg2
import psycopg2.extras

from alerting import AlertHistory
from rpm_common.itemids import VITALS

psycopg2.extras.register_uuid()


@dataclass(frozen=True)
class AlertSettingsRow:
    risk_critical_threshold: float | None
    anomaly_threshold: float
    cooldown_hours: int


class Repository:
    def __init__(self, dsn: str):
        self.conn = psycopg2.connect(dsn)
        self.conn.autocommit = False

    def close(self) -> None:
        self.conn.close()

    # ----------------------------------------------------------------------------------- bệnh nhân & lịch sử

    def upsert_patient(self, subject_id: int, icustay_id: int, age: int | None, gender: str | None) -> uuid.UUID:
        with self.conn, self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO patients (id, display_name, gender, age, mimic_subject_id, mimic_icustay_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (mimic_subject_id) DO UPDATE SET gender = EXCLUDED.gender, age = EXCLUDED.age
                RETURNING id, mimic_icustay_id
                """,
                (uuid.uuid4(), f"BN-{subject_id}", gender, age, subject_id, icustay_id),
            )
            patient_id, stored_stay = cur.fetchone()
        if stored_stay != icustay_id:
            raise ValueError(f"bệnh nhân {subject_id} đã gắn với đợt ICU {stored_stay}, nhận {icustay_id}")
        return patient_id

    def load_vitals(self, patient_id: uuid.UUID) -> list[dict]:
        with self.conn, self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"SELECT hour_index, recorded_at, {', '.join(VITALS)} FROM vital_records "
                "WHERE patient_id = %s ORDER BY hour_index",
                (patient_id,),
            )
            return [dict(row) for row in cur.fetchall()]

    def alert_history(self, patient_id: uuid.UUID) -> dict[str, AlertHistory]:
        """Theo từng loại: còn cảnh báo OPEN không, và giờ dữ liệu của cảnh báo gần nhất."""
        with self.conn, self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT a.alert_type, bool_or(a.status = 'OPEN'), max(v.hour_index)
                FROM alerts a
                JOIN vital_records v ON v.patient_id = a.patient_id AND v.recorded_at = a.prediction_recorded_at
                WHERE a.patient_id = %s
                GROUP BY a.alert_type
                """,
                (patient_id,),
            )
            return {row[0]: AlertHistory(has_open=row[1], last_hour_index=row[2]) for row in cur.fetchall()}

    # ------------------------------------------------------------------------------------------ cấu hình

    def alert_settings(self, defaults: AlertSettingsRow) -> AlertSettingsRow:
        """Bản ghi mới nhất của alert_settings; bảng rỗng thì seed từ DEFAULT_* (.env)."""
        with self.conn, self.conn.cursor() as cur:
            cur.execute(
                "SELECT risk_critical_threshold, anomaly_threshold, cooldown_hours FROM alert_settings "
                "ORDER BY updated_at DESC LIMIT 1"
            )
            row = cur.fetchone()
            if row is None:
                cur.execute(
                    "INSERT INTO alert_settings (id, risk_critical_threshold, anomaly_threshold, cooldown_hours) "
                    "VALUES (%s, %s, %s, %s)",
                    (uuid.uuid4(), defaults.risk_critical_threshold, defaults.anomaly_threshold, defaults.cooldown_hours),
                )
                return defaults
        return AlertSettingsRow(*row)

    def sync_champion(
        self, model_name: str, mlflow_version: str, run_id: str, trigger: str, metrics: dict, trained_at: datetime | None
    ) -> uuid.UUID:
        """Ghi/cập nhật version champion vào model_versions và chỉ để đúng 1 version is_champion cho model này."""
        with self.conn, self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO model_versions
                    (id, model_name, mlflow_version, mlflow_run_id, gate_status, is_champion, trigger, metrics, trained_at)
                VALUES (%s, %s, %s, %s, 'PROMOTED', true, %s, %s, %s)
                ON CONFLICT (model_name, mlflow_version) DO UPDATE
                    SET is_champion = true, gate_status = 'PROMOTED', metrics = EXCLUDED.metrics
                RETURNING id
                """,
                (uuid.uuid4(), model_name, mlflow_version, run_id, trigger, json.dumps(metrics), trained_at),
            )
            version_id = cur.fetchone()[0]
            cur.execute(
                "UPDATE model_versions SET is_champion = false WHERE model_name = %s AND id <> %s AND is_champion",
                (model_name, version_id),
            )
        return version_id

    # ------------------------------------------------------------------------------------ ghi một bản ghi giờ

    def save_hour(self, vital: dict, prediction: dict, alerts: list[dict]) -> None:
        """vital_record + prediction + các alert trong cùng một transaction."""
        with self.conn, self.conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO vital_records (patient_id, recorded_at, hour_index, {', '.join(VITALS)}) "
                f"VALUES (%(patient_id)s, %(recorded_at)s, %(hour_index)s, {', '.join(f'%({v})s' for v in VITALS)})",
                vital,
            )
            cur.execute(
                """
                INSERT INTO predictions (id, recorded_at, patient_id, predicted_at, news2_score, risk_level, risk_score,
                                         anomaly_score, is_anomaly, risk_model_version_id, anomaly_model_version_id)
                VALUES (%(id)s, %(recorded_at)s, %(patient_id)s, %(predicted_at)s, %(news2_score)s, %(risk_level)s,
                        %(risk_score)s, %(anomaly_score)s, %(is_anomaly)s, %(risk_model_version_id)s,
                        %(anomaly_model_version_id)s)
                """,
                prediction,
            )
            for alert in alerts:
                cur.execute(
                    """
                    INSERT INTO alerts (id, patient_id, prediction_id, prediction_recorded_at, alert_type, status,
                                        created_at)
                    VALUES (%(id)s, %(patient_id)s, %(prediction_id)s, %(prediction_recorded_at)s, %(alert_type)s,
                            'OPEN', %(created_at)s)
                    """,
                    alert,
                )
