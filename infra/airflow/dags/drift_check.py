"""DAG drift_check — kiểm tra drift định kỳ, tự kích hoạt retrain (docs/design/02_9 mục 2.9.4, 02_3 mục 2.3.3).

detect_drift ──► decide_retrain ──► trigger_retrain ──► publish_report
                              └──────────────────────────► publish_report

- detect_drift: PSI/KS của 24 giờ dữ liệu streaming gần nhất so với `risk_classifier@champion`, ghi drift_reports.
  Bỏ qua (không ghi báo cáo) khi chưa có champion, không có dữ liệu mới hoặc cửa sổ < 200 bản ghi.
- decide_retrain: có drift và không bị chống vòng lặp chặn (đang có retrain chạy / lần gần nhất kết thúc < 1 giờ)
  thì kích hoạt DAG retrain_pipeline với conf {"trigger": "DRIFT", "drift_report_id": ...}.
- publish_report: ghi việc đã kích hoạt retrain vào báo cáo, publish sự kiện `drift_report` lên Kafka; backend đẩy
  WebSocket cho Admin và gửi email khi bắt đầu một đợt drift mới hoặc khi đã kích hoạt retrain.

Code ML chạy trong venv riêng của image (RPM_PYTHON), file DAG chỉ dùng thư viện của Airflow + rpm_ml.pipelines.policy
(chỉ thư viện chuẩn; import qua RPM_ML_SRC).
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone

from airflow import DAG
from airflow.models import DagRun
from airflow.operators.bash import BashOperator
from airflow.operators.python import BranchPythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator

RPM_PYTHON = os.environ.get("RPM_PYTHON", "/opt/rpm-venv/bin/python")
RPM_ML_SRC = os.environ.get("RPM_ML_SRC", "/opt/rpm/ml/src")
sys.path.insert(0, RPM_ML_SRC)

from rpm_ml.pipelines.policy import PUBLISH_TASK, TRIGGER_TASK, branch_targets, retrain_block_reason  # noqa: E402

RETRAIN_DAG = "retrain_pipeline"
# 2 phút = 24 giờ dữ liệu ở tốc độ phát lại mặc định (5 giây/giờ): mỗi lần kiểm tra phủ đúng phần dữ liệu mới
INTERVAL_MINUTES = int(os.environ.get("DRIFT_CHECK_INTERVAL_MINUTES", "2"))
DRIFT_SCRIPT = f'"{RPM_PYTHON}" -m rpm_ml.drift.detect'


def decide_retrain(ti) -> list[str]:
    result = json.loads(ti.xcom_pull(task_ids="detect_drift"))
    reason = None
    if result.get("status") == "checked":
        ti.xcom_push(key="report_id", value=result["report_id"])
        if result["drift_detected"]:
            runs = DagRun.find(dag_id=RETRAIN_DAG)
            reason = retrain_block_reason([(run.state, run.end_date) for run in runs], datetime.now(timezone.utc))
    ti.xcom_push(key="blocked_reason", value=reason or "")
    return branch_targets(result, reason)


with DAG(
    dag_id="drift_check",
    description="PSI/KS 24 giờ dữ liệu streaming gần nhất; drift → tự kích hoạt retrain_pipeline",
    schedule=timedelta(minutes=INTERVAL_MINUTES),
    start_date=datetime(2026, 9, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    is_paused_upon_creation=False,
    default_args={"retries": 0, "execution_timeout": timedelta(minutes=10)},
    tags=["rpm", "mlops"],
    doc_md=__doc__,
) as dag:
    detect = BashOperator(task_id="detect_drift", bash_command=f"{DRIFT_SCRIPT} detect", do_xcom_push=True)
    decide = BranchPythonOperator(task_id="decide_retrain", python_callable=decide_retrain)
    trigger = TriggerDagRunOperator(
        task_id=TRIGGER_TASK,
        trigger_dag_id=RETRAIN_DAG,
        trigger_run_id="drift__{{ ts_nodash }}",
        conf={"trigger": "DRIFT", "drift_report_id": "{{ ti.xcom_pull(task_ids='decide_retrain', key='report_id') }}"},
        wait_for_completion=False,
    )
    # Giá trị truyền qua biến môi trường (không ghép vào câu lệnh) để không bị diễn giải như lệnh shell
    publish = BashOperator(
        task_id=PUBLISH_TASK,
        bash_command=(
            f'{DRIFT_SCRIPT} publish --report-id "$REPORT_ID" --retrain-run-id "$RETRAIN_RUN_ID" '
            '--blocked-reason "$BLOCKED_REASON"'
        ),
        env={
            "REPORT_ID": "{{ ti.xcom_pull(task_ids='decide_retrain', key='report_id') }}",
            "RETRAIN_RUN_ID": f"{{{{ ti.xcom_pull(task_ids='{TRIGGER_TASK}', key='trigger_run_id') or '' }}}}",
            "BLOCKED_REASON": "{{ ti.xcom_pull(task_ids='decide_retrain', key='blocked_reason') or '' }}",
        },
        append_env=True,
        # Chạy cả khi trigger_retrain bị bỏ qua (không drift / bị chặn), miễn là nhánh dẫn tới nó được chọn
        trigger_rule="none_failed_min_one_success",
    )

    detect >> decide >> [trigger, publish]
    trigger >> publish
