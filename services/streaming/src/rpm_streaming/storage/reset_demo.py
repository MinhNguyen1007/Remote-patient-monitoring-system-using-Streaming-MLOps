"""Xóa dữ liệu của một lần phát lại để demo lại từ đầu: patients, vital_records, predictions, alerts, notification_logs,
patient_assignments. Giữ nguyên users, model_versions, alert_settings, drift_reports.

Phải dừng consumer trước khi chạy. Offset Kafka không cần xóa: lần phát lại sau là message mới.
Chạy từ gốc repo (host): POSTGRES_HOST=localhost .venv\Scripts\python -m rpm_streaming.storage.reset_demo --yes
"""

import argparse

import psycopg2

from rpm_streaming.config import load_settings

TABLES = ("notification_logs", "alerts", "predictions", "vital_records", "patient_assignments", "patients")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--yes", action="store_true", help="xác nhận xóa dữ liệu")
    args = parser.parse_args()
    if not args.yes:
        parser.error("thao tác xóa dữ liệu cần --yes")
    with psycopg2.connect(load_settings().postgres_dsn) as conn, conn.cursor() as cur:
        cur.execute(f"TRUNCATE {', '.join(TABLES)}")
    print("đã xóa:", ", ".join(TABLES))


if __name__ == "__main__":
    main()
