"""DAG retrain_pipeline — Champion–Challenger cho 2 mô hình (docs/design/02_9 mục 2.9.5, 02_4 mục 2.4.3).

build_dataset ──► retrain_risk ────┬──► publish_result
              └─► retrain_anomaly ─┴──► all_models_trained

- Kích hoạt bởi drift_check (conf {"trigger": "DRIFT", "drift_report_id": ...}) hoặc Admin qua backend
  (POST /admin/models/retrain → conf {"trigger": "MANUAL"}). Không có lịch chạy.
- build_dataset: 4 nhóm cố định (hourly.parquet) + dữ liệu stream đã phát, dựng lại từ DB, nhãn đã "chín".
- retrain_risk / retrain_anomaly: challenger huấn luyện trên train + stream, chấm cùng champion trên test cố định,
  quality gate, chuyển alias champion hoặc gắn tag gate=rejected, ghi model_versions. Hai mô hình gate độc lập.
- publish_result: sự kiện `retrain_completed` (kể cả khi một mô hình lỗi) để giao diện Admin cập nhật ngay.
- all_models_trained: chỉ thành công khi cả 2 bước huấn luyện thành công, để trạng thái DAG phản ánh đúng lỗi.
"""

import os
from datetime import datetime, timedelta, timezone

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.empty import EmptyOperator

RPM_PYTHON = os.environ.get("RPM_PYTHON", "/opt/rpm-venv/bin/python")
RUNS_DIR = os.environ.get("RPM_RUNS_DIR", "/opt/airflow/rpm_runs")

# conf do người gọi đặt: truyền qua biến môi trường, retrain.py tự kiểm tra giá trị hợp lệ
RUN_ENV = {
    "RPM_TRIGGER": "{{ dag_run.conf.get('trigger') or 'MANUAL' }}",
    "RPM_DRIFT_REPORT_ID": "{{ dag_run.conf.get('drift_report_id') or '' }}",
    "RPM_DAG_RUN_ID": "{{ run_id }}",
}


def retrain_step(step: str, **kwargs) -> BashOperator:
    return BashOperator(
        task_id={"build": "build_dataset", "publish": "publish_result"}.get(step, f"retrain_{step}"),
        bash_command=(
            f'"{RPM_PYTHON}" -m rpm_ml.pipelines.retrain {step} --runs-dir "{RUNS_DIR}" '
            '--dag-run-id "$RPM_DAG_RUN_ID" --trigger "$RPM_TRIGGER" --drift-report-id "$RPM_DRIFT_REPORT_ID"'
        ),
        env=RUN_ENV,
        append_env=True,
        **kwargs,
    )


with DAG(
    dag_id="retrain_pipeline",
    description="Huấn luyện challenger 2 mô hình trên train + stream, quality gate, promote/từ chối",
    schedule=None,
    start_date=datetime(2026, 9, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    # Backend kích hoạt qua REST API: DAG bị tạm dừng thì lần chạy chỉ nằm ở trạng thái queued
    is_paused_upon_creation=False,
    default_args={"retries": 0, "execution_timeout": timedelta(hours=1)},
    tags=["rpm", "mlops"],
    doc_md=__doc__,
) as dag:
    build = retrain_step("build")
    risk = retrain_step("risk")
    anomaly = retrain_step("anomaly")
    publish = retrain_step("publish", trigger_rule="all_done")
    finished = EmptyOperator(task_id="all_models_trained")

    build >> [risk, anomaly]
    [risk, anomaly] >> publish
    [risk, anomaly] >> finished
