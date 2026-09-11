"""Huấn luyện LSTM-Autoencoder phát hiện bất thường, đánh giá bằng tiêm bất thường, áp quality gate và đăng ký MLflow.

Cần MLflow server (docker compose up -d postgres mlflow); tracking URI lấy từ MLFLOW_TRACKING_URI,
mặc định http://localhost:5000. Chạy: python -m rpm_ml.training.train_anomaly
DAG retrain_pipeline gọi `train_anomaly_model` qua rpm_ml.pipelines.retrain với nhóm huấn luyện train + stream.
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

from rpm_ml.paths import HOURLY_FILE
import rpm_ml.models.anomaly as anomaly_model
from rpm_ml.models.anomaly import AnomalyDetector, fit_autoencoder, window_mse
from rpm_ml.drift.stats import reference_stats
from rpm_ml.evaluation.gate import MIN_AUROC_ANOMALY, TAU_ANOMALY, evaluate_anomaly_gate
from rpm_ml.evaluation.injection import INJECTION_RATE, INJECTION_SEED, KINDS, channel_sigma, inject_anomalies
from rpm_ml.evaluation.metrics import anomaly_metrics, scalar_metrics
from rpm_common.anomaly import N_CHANNELS, WINDOW_HOURS, anomaly_score_from_mse, make_windows
from rpm_common.baseline import ZSCORE_COLUMNS

DEFAULT_DATA = HOURLY_FILE
EXPERIMENT = "anomaly_detection"
REGISTERED_MODEL = "anomaly_detector"
SPLITS = ("train", "validation", "test")
INITIAL_TRAINING_GROUPS = ("train",)


def normal_windows_by_split(hourly: pd.DataFrame) -> dict[str, np.ndarray]:
    """Cửa sổ 12 giờ mà cả 12 giờ đều NORMAL, tách theo nhóm chia dữ liệu của giờ cuối cửa sổ (mọi nhóm có mặt)."""
    windows, meta = make_windows(hourly)
    split = hourly.loc[meta["row"], "split"].to_numpy()
    normal = meta["all_normal"].to_numpy()
    return {name: windows[normal & (split == name)] for name in sorted(set(hourly["split"]) | set(SPLITS))}


def evaluate_champion(client: MlflowClient, windows: np.ndarray, is_anomaly: np.ndarray, kind: np.ndarray):
    """Chấm lại champion hiện tại trên đúng tập test đã tiêm này; trả (metrics, version) hoặc (None, None)."""
    try:
        version = client.get_model_version_by_alias(REGISTERED_MODEL, "champion")
    except MlflowException:
        return None, None
    champion = mlflow.pyfunc.load_model(f"models:/{REGISTERED_MODEL}@champion")
    return anomaly_metrics(is_anomaly, champion.predict(windows), TAU_ANOMALY, kind), version.version


def log_detector(keras_path: Path, reference_path: Path, example: np.ndarray, example_scores: np.ndarray) -> str:
    """Log wrapper pyfunc (autoencoder + MSE tham chiếu + code wrapper) vào run hiện tại và đăng ký version."""
    with tempfile.TemporaryDirectory() as code_dir:
        return _log_detector(keras_path, reference_path, example, example_scores, Path(code_dir))


def _log_detector(keras_path, reference_path, example, example_scores, code_dir: Path) -> str:
    info = mlflow.pyfunc.log_model(
        name="model",
        python_model=AnomalyDetector(),
        artifacts={"autoencoder": str(keras_path), "mse_reference": str(reference_path)},
        code_paths=anomaly_model.serving_code_paths(code_dir),
        registered_model_name=REGISTERED_MODEL,
        signature=infer_signature(example, example_scores),
        input_example=example,
        # rpm_common không có trên PyPI: môi trường suy luận phải tự cài `pip install packages/common`
        pip_requirements=[f"{name}=={package_version(name)}" for name in ("mlflow", "tensorflow", "keras", "numpy")],
    )
    return info.registered_model_version


def tag_and_promote(client: MlflowClient, version: str, gate, trigger: str, extra_tags: dict | None = None) -> None:
    """Gắn tag cho version, luôn trỏ alias challenger; chỉ chuyển alias champion khi đạt gate."""
    tags = {
        "tau_anomaly": str(TAU_ANOMALY),
        "window_hours": str(WINDOW_HOURS),
        "n_channels": str(N_CHANNELS),
        "model_family": "lstm_autoencoder",
        "gate": "passed" if gate.passed else "rejected",
        "gate_reasons": "; ".join(gate.reasons),
        "trigger": trigger,
    } | (extra_tags or {})
    for key, value in tags.items():
        client.set_model_version_tag(REGISTERED_MODEL, version, key, value)
    client.set_registered_model_alias(REGISTERED_MODEL, "challenger", version)
    if gate.passed:
        client.set_registered_model_alias(REGISTERED_MODEL, "champion", version)


def rounded(metrics: dict | None) -> dict | None:
    return None if metrics is None else {k: round(v, 3) for k, v in metrics.items() if isinstance(v, float)}


def train_anomaly_model(
    hourly: pd.DataFrame,
    *,
    seed: int = 42,
    training_groups: tuple[str, ...] = INITIAL_TRAINING_GROUPS,
    trigger: str | None = None,
    tags: dict[str, str] | None = None,
) -> dict:
    """Huấn luyện trên cửa sổ NORMAL của `training_groups`, đánh giá cùng champion trên test tiêm cố định, áp gate."""
    client = MlflowClient()
    windows = normal_windows_by_split(hourly)
    train_windows = np.concatenate([windows[group] for group in training_groups])
    # σ cho biên độ tiêm lấy từ nhóm train cố định, không đổi giữa các lần retrain → cùng một tập test đã tiêm
    sigma = channel_sigma(windows["train"])

    model, history = fit_autoencoder(train_windows, windows["validation"], seed)
    mse_reference = np.sort(window_mse(model, windows["validation"]))

    def score(x: np.ndarray) -> np.ndarray:
        return anomaly_score_from_mse(window_mse(model, x), mse_reference)

    val_x, val_y, val_kind = inject_anomalies(windows["validation"], sigma)
    test_x, test_y, test_kind = inject_anomalies(windows["test"], sigma)
    evaluation = {
        "validation": anomaly_metrics(val_y, score(val_x), TAU_ANOMALY, val_kind),
        "test": anomaly_metrics(test_y, score(test_x), TAU_ANOMALY, test_kind),
        # Tỷ lệ cửa sổ NORMAL huấn luyện bị gắn cờ: kiểm tra nhanh mức quá khớp
        "train_normal_flag_rate": float((score(train_windows) >= TAU_ANOMALY).mean()),
    }

    champion, champion_version = evaluate_champion(client, test_x, test_y, test_kind)
    evaluation["champion_test"] = champion
    gate = evaluate_anomaly_gate(evaluation["test"], champion)
    evaluation["gate"] = {"passed": gate.passed, "reasons": gate.reasons}
    trigger = trigger or ("INITIAL" if champion is None else "MANUAL")

    val_loss = history["val_loss"]
    best_epoch = int(np.argmin(val_loss)) + 1
    n_windows = {"train": len(train_windows), "validation": len(windows["validation"]), "test": len(windows["test"])}
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
                "seed": seed,
                "tau_anomaly": TAU_ANOMALY,
                "injection_rate": INJECTION_RATE,
                "injection_seed": INJECTION_SEED,
                "injection_kinds": ",".join(KINDS),
                "training_groups": ",".join(training_groups),
                **{f"n_normal_windows_{name}": count for name, count in n_windows.items()},
                **{f"n_normal_windows_group_{group}": len(windows[group]) for group in training_groups},
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
        mlflow.log_dict(reference_stats(hourly[hourly["split"].isin(training_groups)], seed), "reference_stats.json")
        mlflow.set_tags(
            {"gate": "passed" if gate.passed else "rejected", "gate_reasons": "; ".join(gate.reasons), "trigger": trigger}
            | (tags or {})
        )

        with tempfile.TemporaryDirectory() as tmp:
            keras_path = Path(tmp) / "autoencoder.keras"
            reference_path = Path(tmp) / "mse_reference.npy"
            model.save(keras_path)
            np.save(reference_path, mse_reference)
            example = windows["train"][:5]
            version = log_detector(keras_path, reference_path, example, score(example))
        tag_and_promote(
            client, version, gate, trigger, {"training_groups": ",".join(training_groups)} | (tags or {})
        )

    return {
        "model_name": REGISTERED_MODEL,
        "run_id": run.info.run_id,
        "training_groups": list(training_groups),
        "normal_windows": n_windows,
        "epochs_trained": len(val_loss),
        "best_epoch": best_epoch,
        "validation": rounded(evaluation["validation"]),
        "test": rounded(evaluation["test"]),
        "train_normal_flag_rate": round(evaluation["train_normal_flag_rate"], 4),
        "gate_threshold_auroc": MIN_AUROC_ANOMALY,
        "champion_version": champion_version,
        "champion_test": rounded(champion),
        "registered_version": version,
        "trigger": trigger,
        "gate": evaluation["gate"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    summary = train_anomaly_model(pd.read_parquet(args.data), seed=args.seed)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
