"""Đóng gói lại một version `anomaly_detector` với code wrapper hiện tại, **giữ nguyên trọng số và MSE tham chiếu**.

Dùng khi code wrapper (`anomaly_model.py`, được chụp kèm model qua `code_paths`) cần sửa mà model không đổi —
lần đầu (2026-09-11): v2 được log từ Windows nên đường dẫn artifact chứa `\`, container Linux không nạp được.

Các bước:
  1. tải artifact của version nguồn (autoencoder.keras, mse_reference.npy) và artifact đánh giá của run nguồn;
  2. log run mới + đăng ký version mới với code wrapper hiện tại;
  3. kiểm tra điểm của version mới **trùng khít** version nguồn trên tập test tiêm bất thường (không trùng → dừng,
     không promote);
  4. áp quality gate như mọi challenger (so với champion trên cùng tập test) rồi mới chuyển alias.

Không huấn luyện lại, không chọn lại ngưỡng. Chạy từ gốc repo: .venv\Scripts\python ml/src/repackage_anomaly.py --version 2
"""

import argparse
import json
import os
import tempfile
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd
from mlflow import MlflowClient

from gate import TAU_ANOMALY, evaluate_anomaly_gate
from injection import channel_sigma, inject_anomalies
from metrics import anomaly_metrics, scalar_metrics
from train_anomaly import (
    DEFAULT_DATA,
    EXPERIMENT,
    REGISTERED_MODEL,
    evaluate_champion,
    log_detector,
    normal_windows_by_split,
    tag_and_promote,
)

COPIED_RUN_ARTIFACTS = ("injection.json", "reference_stats.json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", required=True, help="version nguồn cần đóng gói lại")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    args = parser.parse_args()

    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    client = MlflowClient()
    source = client.get_model_version(REGISTERED_MODEL, args.version)
    windows = normal_windows_by_split(pd.read_parquet(args.data))
    test_x, test_y, test_kind = inject_anomalies(windows["test"], channel_sigma(windows["train"]))
    source_model = mlflow.pyfunc.load_model(f"models:/{REGISTERED_MODEL}/{args.version}")
    source_scores = source_model.predict(test_x)

    with tempfile.TemporaryDirectory() as tmp:
        model_dir = Path(mlflow.artifacts.download_artifacts(f"models:/{REGISTERED_MODEL}/{args.version}", dst_path=tmp))
        keras_path = model_dir / "artifacts" / "autoencoder.keras"
        reference_path = model_dir / "artifacts" / "mse_reference.npy"
        run_dir = Path(tmp) / "run"
        for name in COPIED_RUN_ARTIFACTS:
            mlflow.artifacts.download_artifacts(run_id=source.run_id, artifact_path=name, dst_path=str(run_dir))

        champion, champion_version = evaluate_champion(client, test_x, test_y, test_kind)
        mlflow.set_experiment(EXPERIMENT)
        with mlflow.start_run(run_name=f"repackage_v{args.version}") as run:
            mlflow.log_params(
                {"repackaged_from_version": args.version, "repackaged_from_run": source.run_id,
                 "tau_anomaly": TAU_ANOMALY, "champion_compared": champion_version or "none"}
            )
            for name in COPIED_RUN_ARTIFACTS:
                mlflow.log_artifact(str(run_dir / name))
            example = windows["train"][:5]
            version = log_detector(keras_path, reference_path, example, source_model.predict(example))
            new_scores = mlflow.pyfunc.load_model(f"models:/{REGISTERED_MODEL}/{version}").predict(test_x)
            identical = bool(np.array_equal(new_scores, source_scores))
            test = anomaly_metrics(test_y, new_scores, TAU_ANOMALY, test_kind)
            gate = evaluate_anomaly_gate(test, champion)
            if not identical:
                gate.passed = False
                gate.reasons.append(f"điểm khác version nguồn v{args.version}")
            mlflow.log_metrics(scalar_metrics(test, "test"))
            mlflow.log_dict({"test": test, "champion_test": champion, "identical_to_source": identical,
                             "gate": {"passed": gate.passed, "reasons": gate.reasons}}, "evaluation.json")
            mlflow.set_tags({"gate": "passed" if gate.passed else "rejected", "gate_reasons": "; ".join(gate.reasons)})
        note = f"đóng gói lại v{args.version} (cùng trọng số) với wrapper chuẩn hóa đường dẫn artifact"
        tag_and_promote(client, version, gate, trigger=source.tags.get("trigger", "MANUAL"),
                        extra_tags={"repackaged_from": args.version, "gate_note": note})

    print(json.dumps({"run_id": run.info.run_id, "new_version": version, "identical_to_source": identical,
                      "test_auroc": round(test["auroc"], 3), "gate": {"passed": gate.passed, "reasons": gate.reasons}},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
