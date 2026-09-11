"""Huấn luyện LSTM-Autoencoder phát hiện bất thường, đánh giá bằng tiêm bất thường, áp quality gate và đăng ký MLflow.

Cần MLflow server (docker compose up -d postgres mlflow); tracking URI lấy từ MLFLOW_TRACKING_URI,
mặc định http://localhost:5000. Chạy từ gốc repo: .venv\\Scripts\\python ml/src/train_anomaly.py
Thiết kế: docs/design/02_9_thiet_ke_giai_thuat.md mục 2.9.3, 2.9.5; 02_10 mục 2.10.3.
"""

import argparse
import json
import os
import tempfile
from importlib.metadata import version as package_version
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException
from mlflow.models import infer_signature

import anomaly_model
from anomaly_model import AnomalyDetector, fit_autoencoder, window_mse
from drift import reference_stats
from gate import MIN_AUROC_ANOMALY, TAU_ANOMALY, evaluate_anomaly_gate
from injection import INJECTION_RATE, INJECTION_SEED, KINDS, channel_sigma, inject_anomalies
from metrics import anomaly_metrics, scalar_metrics
from rpm_common.anomaly import N_CHANNELS, WINDOW_HOURS, anomaly_score_from_mse, make_windows
from rpm_common.baseline import ZSCORE_COLUMNS

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA = REPO_ROOT / "ml" / "data" / "processed" / "hourly.parquet"
EXPERIMENT = "anomaly_detection"
REGISTERED_MODEL = "anomaly_detector"
SPLITS = ("train", "validation", "test")


def normal_windows_by_split(hourly: pd.DataFrame) -> dict[str, np.ndarray]:
    """Cửa sổ 12 giờ mà cả 12 giờ đều NORMAL, tách theo nhóm chia dữ liệu của giờ cuối cửa sổ."""
    windows, meta = make_windows(hourly)
    split = hourly.loc[meta["row"], "split"].to_numpy()
    normal = meta["all_normal"].to_numpy()
    return {name: windows[normal & (split == name)] for name in SPLITS}


def evaluate_champion(client: MlflowClient, windows: np.ndarray, is_anomaly: np.ndarray, kind: np.ndarray):
    """Chấm lại champion hiện tại trên đúng tập test đã tiêm này; trả (metrics, version) hoặc (None, None)."""
    try:
        version = client.get_model_version_by_alias(REGISTERED_MODEL, "champion")
    except MlflowException:
        return None, None
    champion = mlflow.pyfunc.load_model(f"models:/{REGISTERED_MODEL}@champion")
    return anomaly_metrics(is_anomaly, champion.predict(windows), TAU_ANOMALY, kind), version.version


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    client = MlflowClient()
    hourly = pd.read_parquet(args.data)
    windows = normal_windows_by_split(hourly)
    # σ cho biên độ tiêm lấy từ nhóm train cố định, không đổi giữa các lần retrain
    sigma = channel_sigma(windows["train"])

    model, history = fit_autoencoder(windows["train"], windows["validation"], args.seed)
    mse_reference = np.sort(window_mse(model, windows["validation"]))

    def score(x: np.ndarray) -> np.ndarray:
        return anomaly_score_from_mse(window_mse(model, x), mse_reference)

    val_x, val_y, val_kind = inject_anomalies(windows["validation"], sigma)
    test_x, test_y, test_kind = inject_anomalies(windows["test"], sigma)
    evaluation = {
        "validation": anomaly_metrics(val_y, score(val_x), TAU_ANOMALY, val_kind),
        "test": anomaly_metrics(test_y, score(test_x), TAU_ANOMALY, test_kind),
        # Tỷ lệ cửa sổ NORMAL của train bị gắn cờ: kiểm tra nhanh mức quá khớp
        "train_normal_flag_rate": float((score(windows["train"]) >= TAU_ANOMALY).mean()),
    }

    champion, champion_version = evaluate_champion(client, test_x, test_y, test_kind)
    evaluation["champion_test"] = champion
    gate = evaluate_anomaly_gate(evaluation["test"], champion)
    evaluation["gate"] = {"passed": gate.passed, "reasons": gate.reasons}

    val_loss = history["val_loss"]
    best_epoch = int(np.argmin(val_loss)) + 1
    mlflow.set_experiment(EXPERIMENT)
    with mlflow.start_run(run_name="lstm_autoencoder") as run:
        mlflow.log_params(
            {
                "model": "lstm_autoencoder",
                "architecture": anomaly_model.ARCHITECTURE,
                "input_transform": anomaly_model.INPUT_TRANSFORM,
                "window_hours": WINDOW_HOURS,
                "channels": ",".join(ZSCORE_COLUMNS),
                "learning_rate": anomaly_model.LEARNING_RATE,
                "batch_size": anomaly_model.BATCH_SIZE,
                "max_epochs": anomaly_model.MAX_EPOCHS,
                "early_stopping_patience": anomaly_model.EARLY_STOPPING_PATIENCE,
                "epochs_trained": len(val_loss),
                "best_epoch": best_epoch,
                "seed": args.seed,
                "tau_anomaly": TAU_ANOMALY,
                "injection_rate": INJECTION_RATE,
                "injection_seed": INJECTION_SEED,
                "injection_kinds": ",".join(KINDS),
                **{f"n_normal_windows_{name}": len(part) for name, part in windows.items()},
                "champion_compared": champion_version or "none",
            }
        )
        for epoch, (loss, v_loss) in enumerate(zip(history["loss"], val_loss), start=1):
            mlflow.log_metrics({"loss": loss, "val_loss": v_loss}, step=epoch)
        mlflow.log_metrics(
            {"best_val_loss": float(min(val_loss)), "train_normal_flag_rate": evaluation["train_normal_flag_rate"]}
            | scalar_metrics(evaluation["validation"], "val")
            | scalar_metrics(evaluation["test"], "test")
        )
        mlflow.log_dict(evaluation, "evaluation.json")
        mlflow.log_dict(
            {
                "channels": list(ZSCORE_COLUMNS),
                "sigma": dict(zip(ZSCORE_COLUMNS, np.round(sigma, 6).tolist())),
                "rate": INJECTION_RATE,
                "seed": INJECTION_SEED,
            },
            "injection.json",
        )
        mlflow.log_dict(reference_stats(hourly[hourly["split"] == "train"], args.seed), "reference_stats.json")
        mlflow.set_tags({"gate": "passed" if gate.passed else "rejected", "gate_reasons": "; ".join(gate.reasons)})

        with tempfile.TemporaryDirectory() as tmp:
            keras_path = Path(tmp) / "autoencoder.keras"
            reference_path = Path(tmp) / "mse_reference.npy"
            model.save(keras_path)
            np.save(reference_path, mse_reference)
            example = windows["train"][:5]
            info = mlflow.pyfunc.log_model(
                name="model",
                python_model=AnomalyDetector(),
                artifacts={"autoencoder": str(keras_path), "mse_reference": str(reference_path)},
                code_paths=[anomaly_model.__file__],
                registered_model_name=REGISTERED_MODEL,
                signature=infer_signature(example, score(example)),
                input_example=example,
                # rpm_common không có trên PyPI: môi trường suy luận phải tự cài `pip install -e common`
                pip_requirements=[
                    f"{name}=={package_version(name)}" for name in ("mlflow", "tensorflow", "keras", "numpy")
                ],
            )
        version = info.registered_model_version
        tags = {
            "tau_anomaly": str(TAU_ANOMALY),
            "window_hours": str(WINDOW_HOURS),
            "n_channels": str(N_CHANNELS),
            "model_family": "lstm_autoencoder",
            "gate": "passed" if gate.passed else "rejected",
            "gate_reasons": "; ".join(gate.reasons),
            "trigger": "INITIAL" if champion is None else "MANUAL",
        }
        for key, value in tags.items():
            client.set_model_version_tag(REGISTERED_MODEL, version, key, value)
        client.set_registered_model_alias(REGISTERED_MODEL, "challenger", version)
        if gate.passed:
            client.set_registered_model_alias(REGISTERED_MODEL, "champion", version)

    def rounded(metrics: dict) -> dict:
        return {k: round(v, 3) for k, v in metrics.items() if isinstance(v, float)}

    summary = {
        "run_id": run.info.run_id,
        "normal_windows": {name: len(part) for name, part in windows.items()},
        "epochs_trained": len(val_loss),
        "best_epoch": best_epoch,
        "validation": rounded(evaluation["validation"]),
        "test": rounded(evaluation["test"]),
        "train_normal_flag_rate": round(evaluation["train_normal_flag_rate"], 4),
        "gate_threshold_auroc": MIN_AUROC_ANOMALY,
        "registered_version": version,
        "gate": evaluation["gate"],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
